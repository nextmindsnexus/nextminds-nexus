"""
Summarizer — generates document summaries using Gemini.

Summary length adapts to document length:
- Short docs (< 500 chars):  1-2 sentences
- Medium docs (< 2000 chars): 3-4 sentences
- Long docs (2000+ chars):    5-8 sentences (a short paragraph)
"""

from __future__ import annotations

import logging
import re
import time

from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, SUMMARIZER_MODEL

logger = logging.getLogger(__name__)


def _get_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    return genai.Client(api_key=GEMINI_API_KEY)


def _length_instruction(content_length: int) -> str:
    """Return length guidance based on the document size."""
    if content_length < 500:
        return "Write 2-3 sentences summarizing the content."
    elif content_length < 2000:
        return "Write 4-6 sentences summarizing the content in detail."
    elif content_length < 5000:
        return "Write a detailed paragraph (6-10 sentences) covering all key topics, activities, and learning objectives."
    else:
        return "Write a thorough summary (2-3 short paragraphs, 10-15 sentences) describing all the content, activities, materials, and learning goals in detail."


def summarize_text(
    content: str,
    activity_name: str,
    grade_band: str = "",
    stage: str = "",
) -> tuple[str, list[str]]:
    """
    Generate a teacher-friendly summary and keyword tags for a document.

    Returns (summary, keywords).
    """
    # Truncate content to stay within token limits (~12k chars ≈ ~3k tokens)
    max_chars = 12000
    truncated = content[:max_chars]
    if len(content) > max_chars:
        truncated += "\n\n[Content truncated]"

    length_guide = _length_instruction(len(content))

    prompt = f"""You are summarizing a curriculum activity resource for a teacher. Your job is to describe WHAT IS INSIDE the document(s) — what topics are covered, what activities students do, what materials are needed, and what students will learn or produce.

Activity name: {activity_name}
Grade band: {grade_band}
Stage: {stage}

{length_guide}

IMPORTANT: Do NOT just restate the title. Describe the actual content — the specific activities, exercises, discussion prompts, worksheets, or lessons contained in the resource. If there are multiple documents, summarize each one's content.

Also extract 5-8 keyword tags relevant for search (e.g., "prototyping", "engineering design", "teamwork", "worksheet", "lesson plan").

Respond in exactly this format:
SUMMARY: <your detailed summary here>
KEYWORDS: <comma-separated keywords>

Document content:
---
{truncated}
---"""

    client = _get_client()

    response = client.models.generate_content(
        model=SUMMARIZER_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=2048,
        ),
    )

    text = response.candidates[0].content.parts[0].text.strip()

    # Parse structured response (case-insensitive, strip markdown bold markers)
    clean = re.sub(r"\*\*", "", text)  # remove ** bold markers
    summary = clean
    keywords: list[str] = []

    # Case-insensitive split on SUMMARY: and KEYWORDS:
    m_sum = re.search(r"(?i)^SUMMARY:\s*", clean, re.MULTILINE)
    m_kw = re.search(r"(?i)^KEYWORDS:\s*", clean, re.MULTILINE)

    if m_sum:
        start = m_sum.end()
        end = m_kw.start() if m_kw else len(clean)
        summary = clean[start:end].strip()
    if m_kw:
        kw_text = clean[m_kw.end():].strip()
        keywords = [k.strip().strip('"').lower() for k in kw_text.split(",") if k.strip()]

    return summary, keywords


def run_summarization(limit: int | None = None) -> dict:
    """
    Summarize all unsummarized activities.

    Args:
        limit: Max number of activities to summarize (None = all).

    Returns summary dict with counts.
    """
    from rich.console import Console
    from rich.progress import Progress

    from src.db.operations import get_unsummarized_activities, update_activity_summary
    from src.summarizer.content_extractor import extract_content

    console = Console()
    console.print("\n[bold blue]Document Summarization Pipeline[/bold blue]\n")

    activities = get_unsummarized_activities(limit=limit)

    if not activities:
        console.print("[green]All activities already have summaries.[/green]")
        return {"processed": 0, "skipped": 0, "errors": 0}

    console.print(f"  Found [yellow]{len(activities)}[/yellow] activities needing summaries\n")

    processed = 0
    skipped = 0
    errors = 0

    with Progress(console=console) as progress:
        task = progress.add_task("Summarizing...", total=len(activities))

        for activity in activities:
            aid = activity["id"]
            name = activity["activity_name"]
            url = activity["resource_url"]
            rtype = activity["resource_type"]
            drive_id = activity.get("drive_id")

            progress.update(task, description=f"[dim]{name[:40]}[/dim]")

            try:
                # Step 1: Extract content from Drive
                content = extract_content(url, rtype, drive_id)

                # Step 1b: Fall back to website section description
                if not content or len(content.strip()) < 20:
                    section_desc = activity.get("section_description") or ""
                    if section_desc.strip():
                        content = section_desc

                if not content or len(content.strip()) < 20:
                    # No content available — generate a basic summary from metadata
                    content = (
                        f"Activity: {name}. "
                        f"Grade band: {activity['grade_band']}. "
                        f"Stage: {activity['stage']}. "
                        f"Resource type: {rtype}."
                    )

                # Step 2: Summarize with Gemini
                summary, keywords = summarize_text(
                    content=content,
                    activity_name=name,
                    grade_band=activity["grade_band"],
                    stage=activity["stage"],
                )

                # Step 3: Save to database
                update_activity_summary(
                    activity_id=str(aid),
                    description=summary,
                    keywords=keywords if keywords else None,
                )
                processed += 1

                # Rate limit: ~2 seconds between calls (safe for free tier)
                time.sleep(2)

            except Exception as e:
                logger.error(f"Failed to summarize {name}: {e}")
                errors += 1

            progress.advance(task)

    result = {"processed": processed, "skipped": skipped, "errors": errors}

    console.print(f"\n[green]Done![/green] Processed: {processed}, Skipped: {skipped}, Errors: {errors}")
    return result
