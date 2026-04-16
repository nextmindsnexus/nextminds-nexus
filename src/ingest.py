"""
Ingestion orchestrator: ties crawling, embedding, and database together.

This is the main entry point for the data pipeline:
1. Crawl the CTIC website for activities
2. Generate embeddings for each activity
3. Upsert into Supabase/pgvector
4. Mark removed activities as inactive
5. Log the crawl run
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table
from rich.progress import Progress

from src.crawler.site_crawler import crawl_all, CrawledActivity, verify_drive_links
from src.embeddings.embedder import embed_batch, build_embedding_text
from src.db.operations import (
    get_connection,
    init_schema,
    upsert_activity,
    mark_missing_inactive,
    create_crawl_log,
    complete_crawl_log,
    get_activity_stats,
    update_health_status,
)
from src.summarizer.summarizer import run_summarization

logger = logging.getLogger(__name__)
console = Console()


def run_full_ingestion(triggered_by: str = "manual") -> dict:
    """
    Run the complete ingestion pipeline:
    crawl → embed → upsert → cleanup → log.

    Returns a summary dict with counts.
    """
    console.print("\n[bold blue]CTIC Curriculum Ingestion Pipeline[/bold blue]\n")

    # Step 1: Initialize schema (idempotent)
    console.print("[dim]Step 1/5:[/dim] Initializing database schema...")
    init_schema()

    # Step 2: Crawl all grade band pages
    console.print("[dim]Step 2/5:[/dim] Crawling CTIC website...")
    activities = crawl_all()

    if not activities:
        console.print("[red]No activities found! Check the website structure.[/red]")
        return {"error": "No activities crawled"}

    console.print(f"  Found [green]{len(activities)}[/green] activities across all grade bands\n")

    # Display crawled activities summary
    _print_crawl_summary(activities)

    # Step 3: Generate embeddings
    console.print("\n[dim]Step 3/5:[/dim] Generating embeddings...")
    texts = [
        build_embedding_text(
            activity_name=a.activity_name,
            stage=a.stage,
            grade_band=a.grade_band,
        )
        for a in activities
    ]
    embeddings = embed_batch(texts)
    console.print(f"  Generated [green]{len(embeddings)}[/green] embeddings ({len(embeddings[0])}d)\n")

    # Step 4: Upsert into database
    console.print("[dim]Step 4/5:[/dim] Upserting into database...")
    added = 0
    updated = 0
    errors = []

    with get_connection() as conn:
        log_id = create_crawl_log(conn, triggered_by)
        conn.commit()

        for activity, embedding in zip(activities, embeddings):
            try:
                result = upsert_activity(
                    conn=conn,
                    activity_name=activity.activity_name,
                    grade_band=activity.grade_band,
                    stage=activity.stage,
                    resource_url=activity.resource_url,
                    resource_type=activity.resource_type,
                    drive_id=activity.drive_id,
                    embedding=embedding,
                )
                if result == "inserted":
                    added += 1
                else:
                    updated += 1
            except Exception as e:
                error_msg = f"{activity.activity_name}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)

        # Step 5: Mark missing activities as inactive
        console.print("[dim]Step 5/5:[/dim] Cleaning up removed activities...")
        active_urls = {a.resource_url for a in activities}
        removed = mark_missing_inactive(conn, active_urls)

        # Log the crawl
        complete_crawl_log(
            conn=conn,
            log_id=log_id,
            added=added,
            updated=updated,
            removed=removed,
            errors=errors if errors else None,
        )
        conn.commit()

    # Print results
    summary = {
        "total_crawled": len(activities),
        "added": added,
        "updated": updated,
        "removed": removed,
        "errors": len(errors),
    }

    console.print()
    _print_results(summary)

    if errors:
        console.print("\n[yellow]Errors:[/yellow]")
        for e in errors:
            console.print(f"  [red]• {e}[/red]")

    # Step 6: Summarize new activities (description IS NULL)
    console.print("\n[dim]Step 6:[/dim] Summarizing new activities...")
    try:
        sum_result = run_summarization()
        summary["summarized"] = sum_result.get("processed", 0)
        summary["summary_errors"] = sum_result.get("errors", 0)
    except Exception as e:
        logger.warning(f"Summarization step failed: {e}")
        summary["summarized"] = 0
        summary["summary_errors"] = 1

    return summary


def run_health_check() -> dict:
    """
    Verify all active Drive/Docs links are still accessible.
    Updates the database with results.
    """
    console.print("\n[bold blue]Drive Link Health Check[/bold blue]\n")

    from src.db.operations import search_activities as _  # noqa: just check import
    from src.db.operations import get_connection

    with get_connection() as conn:
        result = conn.execute(
            """
            SELECT resource_url, activity_name, resource_type
            FROM activities
            WHERE is_active = TRUE
              AND resource_type IN ('drive_folder', 'drive_file', 'google_doc')
            """
        )
        rows = result.fetchall()

    if not rows:
        console.print("[yellow]No active Drive links to check.[/yellow]")
        return {"checked": 0}

    console.print(f"Checking {len(rows)} Drive links...\n")

    # Build CrawledActivity objects for the health checker
    check_activities = [
        CrawledActivity(
            activity_name=row[1],
            grade_band="",
            stage="",
            resource_url=row[0],
            resource_type=row[2],
        )
        for row in rows
    ]

    results = verify_drive_links(check_activities)

    # Update database
    broken = 0
    for url, is_ok in results.items():
        update_health_status(url, is_ok)
        if not is_ok:
            broken += 1

    console.print(f"\n[green]✓[/green] {len(results) - broken}/{len(results)} links accessible")
    if broken:
        console.print(f"[red]✗[/red] {broken} links broken (marked inactive)")

    return {"checked": len(results), "broken": broken}


def _print_crawl_summary(activities: list[CrawledActivity]):
    """Print a summary table of crawled activities by grade band and stage."""
    table = Table(title="Crawled Activities")
    table.add_column("Grade Band", style="cyan")
    table.add_column("Stage", style="green")
    table.add_column("Activities", justify="right")

    # Group by grade_band, then stage
    from collections import Counter

    groups: dict[str, Counter] = {}
    for a in activities:
        if a.grade_band not in groups:
            groups[a.grade_band] = Counter()
        groups[a.grade_band][a.stage] += 1

    for gb in sorted(groups.keys()):
        first = True
        for stage, count in sorted(groups[gb].items()):
            table.add_row(
                gb if first else "",
                stage,
                str(count),
            )
            first = False
        table.add_row("", "", "", style="dim")

    console.print(table)


def _print_results(summary: dict):
    """Print the final ingestion results."""
    table = Table(title="Ingestion Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="green")

    table.add_row("Total crawled", str(summary["total_crawled"]))
    table.add_row("New activities added", str(summary["added"]))
    table.add_row("Existing updated", str(summary["updated"]))
    table.add_row("Removed (inactive)", str(summary["removed"]))
    table.add_row(
        "Errors",
        f"[red]{summary['errors']}[/red]" if summary["errors"] else "0",
    )

    console.print(table)
