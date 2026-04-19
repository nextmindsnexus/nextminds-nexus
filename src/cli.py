#!/usr/bin/env python3
"""
CLI entry point for the CTIC Curriculum Engine data pipeline.

Usage:
    # Run the full crawl → embed → store pipeline
    python -m src.cli ingest

    # Crawl only (no database) — test the crawler
    python -m src.cli crawl

    # Run a health check on stored Drive links
    python -m src.cli health

    # Search the catalog (test pgvector similarity search)
    python -m src.cli search "prototyping activity for 3rd graders"

    # Show catalog statistics
    python -m src.cli stats

    # Initialize the database schema only
    python -m src.cli init-db
"""

from __future__ import annotations

import sys
import logging
import argparse

from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

console = Console()


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )


def cmd_crawl(args):
    """Crawl the CTIC site and print results (no database)."""
    from src.crawler.site_crawler import crawl_all

    activities = crawl_all()

    table = Table(title=f"Crawled Activities ({len(activities)} total)")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Grade", style="cyan", width=5)
    table.add_column("Stage", style="green", width=30)
    table.add_column("Activity", style="white", width=30)
    table.add_column("Type", style="yellow", width=12)
    table.add_column("Drive ID", style="dim", width=20)

    for i, a in enumerate(activities, 1):
        table.add_row(
            str(i),
            a.grade_band,
            a.stage[:30],
            a.activity_name[:30],
            a.resource_type,
            (a.drive_id or "")[:20],
        )

    console.print(table)

    # Summary
    from collections import Counter

    grades = Counter(a.grade_band for a in activities)
    types = Counter(a.resource_type for a in activities)
    console.print(f"\n[bold]By grade:[/bold] {dict(grades)}")
    console.print(f"[bold]By type:[/bold]  {dict(types)}")


def cmd_ingest(args):
    """Run the full ingestion pipeline."""
    from src.ingest import run_full_ingestion

    run_full_ingestion(triggered_by="cli")


def cmd_health(args):
    """Run a health check on Drive links."""
    from src.ingest import run_health_check

    run_health_check()


def cmd_search(args):
    """Search the catalog using natural language."""
    from src.embeddings.embedder import embed_text, build_embedding_text
    from src.db.operations import search_activities

    query = args.query
    console.print(f"\n[bold]Searching for:[/bold] {query}")

    if args.grade:
        console.print(f"  [dim]Grade filter: {args.grade}[/dim]")
    if args.stage:
        console.print(f"  [dim]Stage filter: {args.stage}[/dim]")

    # Build embedding for the search query
    query_embedding = embed_text(query)

    results = search_activities(
        query_embedding=query_embedding,
        grade_band=args.grade,
        stage=args.stage,
        max_time=args.max_time,
        limit=args.limit,
    )

    if not results:
        console.print("\n[yellow]No results found.[/yellow]")
        return

    console.print(f"\n[green]Top {len(results)} results:[/green]\n")

    table = Table()
    table.add_column("#", justify="right", style="dim")
    table.add_column("Score", justify="right", style="cyan")
    table.add_column("Activity", style="white", width=25)
    table.add_column("Grade", style="yellow", width=5)
    table.add_column("Stage", style="green", width=25)
    table.add_column("URL", style="dim", max_width=50)

    for i, r in enumerate(results, 1):
        score = f"{r['similarity']:.3f}" if r.get('similarity') is not None else "?"
        table.add_row(
            str(i),
            score,
            r["activity_name"][:25],
            r["grade_band"],
            r["stage"][:25],
            r["resource_url"][:50],
        )

    console.print(table)


def cmd_stats(args):
    """Show catalog statistics."""
    from src.db.operations import get_activity_stats

    stats = get_activity_stats()

    console.print("\n[bold blue]Catalog Statistics[/bold blue]\n")
    console.print(f"  Total activities: [green]{stats['total']}[/green]")
    console.print(f"  Active: [green]{stats['active']}[/green]")
    console.print(f"  Grade bands: {stats['grade_bands']}")
    console.print(f"  Unique stages: {stats['stages']}")
    console.print(f"  Oldest crawl: {stats['oldest_crawl']}")
    console.print(f"  Newest crawl: {stats['newest_crawl']}")

    if stats.get("by_grade_band"):
        console.print("\n  [bold]By Grade Band:[/bold]")
        for gb, count in stats["by_grade_band"].items():
            console.print(f"    {gb}: {count}")

    if stats.get("by_stage"):
        console.print("\n  [bold]By Stage:[/bold]")
        for stage, count in stats["by_stage"].items():
            console.print(f"    {stage}: {count}")


def cmd_init_db(args):
    """Initialize the database schema."""
    from src.db.operations import init_schema

    init_schema()
    console.print("[green]Database schema initialized successfully.[/green]")


def cmd_summarize(args):
    """Summarize unsummarized activities using Gemini."""
    from src.summarizer.summarizer import run_summarization

    limit = getattr(args, "limit", None)
    run_summarization(limit=limit)


def cmd_create_admin(args):
    """Create an admin user via Supabase Admin API + local profile."""
    from src.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        console.print("[red]SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env[/red]")
        return

    from supabase import create_client
    from src.db.operations import create_user_profile

    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    console.print(f"Creating admin user: [cyan]{args.email}[/cyan]")

    try:
        auth_response = sb.auth.admin.create_user(
            {"email": args.email, "password": args.password, "email_confirm": True}
        )
    except Exception as e:
        console.print(f"[red]Supabase error: {e}[/red]")
        return

    supabase_user = auth_response.user
    if not supabase_user:
        console.print("[red]Failed to create Supabase auth user.[/red]")
        return

    try:
        create_user_profile(
            supabase_id=str(supabase_user.id),
            email=args.email,
            first_name=args.first_name,
            last_name=args.last_name,
            date_of_birth=None,
            role="admin",
        )
    except Exception as e:
        console.print(f"[red]Profile creation failed: {e}[/red]")
        try:
            sb.auth.admin.delete_user(str(supabase_user.id))
        except Exception:
            pass
        return

    console.print(f"[green]Admin user created successfully![/green]")
    console.print(f"  ID: {supabase_user.id}")
    console.print(f"  Email: {args.email}")
    console.print(f"  Role: admin")


def main():
    parser = argparse.ArgumentParser(
        description="CTIC Curriculum Engine - Data Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # crawl
    subparsers.add_parser("crawl", help="Crawl CTIC site (no database)")

    # ingest
    subparsers.add_parser("ingest", help="Full pipeline: crawl → embed → store")

    # health
    subparsers.add_parser("health", help="Health check on Drive links")

    # search
    search_parser = subparsers.add_parser("search", help="Search the catalog")
    search_parser.add_argument("query", help="Natural language search query")
    search_parser.add_argument("--grade", "-g", help="Filter by grade band (K-2, 3-5, 6-8, 9-12)")
    search_parser.add_argument("--stage", "-s", help="Filter by stage name (partial match)")
    search_parser.add_argument("--max-time", "-t", type=int, help="Max activity time in minutes")
    search_parser.add_argument("--limit", "-l", type=int, default=5, help="Number of results")

    # stats
    subparsers.add_parser("stats", help="Show catalog statistics")

    # init-db
    subparsers.add_parser("init-db", help="Initialize database schema")

    # summarize
    summarize_parser = subparsers.add_parser("summarize", help="Summarize unsummarized activities")
    summarize_parser.add_argument("--limit", "-l", type=int, default=None, help="Max activities to summarize")

    # create-admin
    admin_parser = subparsers.add_parser("create-admin", help="Create an admin user")
    admin_parser.add_argument("--email", required=True, help="Admin email address")
    admin_parser.add_argument("--password", required=True, help="Admin password (min 8 chars)")
    admin_parser.add_argument("--first-name", default="Admin", help="First name")
    admin_parser.add_argument("--last-name", default="User", help="Last name")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        return

    commands = {
        "crawl": cmd_crawl,
        "ingest": cmd_ingest,
        "health": cmd_health,
        "search": cmd_search,
        "stats": cmd_stats,
        "init-db": cmd_init_db,
        "summarize": cmd_summarize,
        "create-admin": cmd_create_admin,
    }

    try:
        commands[args.command](args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        if args.verbose:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
