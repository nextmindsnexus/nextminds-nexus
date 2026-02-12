"""
CTIC Website Crawler

Scrapes the CTIC curriculum pages to extract:
- Grade band → Stage → Activity taxonomy
- Google Drive folder/file URLs for each activity
- Activity names and descriptions

The site is a GoDaddy website builder site. Each grade band page
(K-2, 3-5, 6-8, 9-12) has sections for each invention stage, and
each section contains ContentCards with activity names and Drive links.
"""

from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs

import requests

from src.config import BASE_URL, GRADE_BAND_PAGES

logger = logging.getLogger(__name__)


@dataclass
class CrawledActivity:
    """A single activity extracted from the CTIC website."""

    activity_name: str
    grade_band: str
    stage: str
    resource_url: str  # Google Drive folder/file URL or YouTube URL
    resource_type: str  # 'drive_folder', 'drive_file', 'google_doc', 'youtube', 'other'
    drive_id: str | None = None  # Extracted Drive folder/file ID

    def __post_init__(self):
        if not self.drive_id:
            self.drive_id = extract_drive_id(self.resource_url)


def extract_drive_id(url: str) -> str | None:
    """Extract Google Drive folder or file ID from a URL."""
    # Drive folder: https://drive.google.com/drive/folders/FOLDER_ID?...
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)

    # Drive file: https://drive.google.com/file/d/FILE_ID/...
    match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)

    # Google Docs/Slides/Sheets: https://docs.google.com/document/d/DOC_ID/...
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)

    return None


def classify_url(url: str) -> str:
    """Classify a URL into its resource type."""
    if "drive.google.com/drive/folders" in url:
        return "drive_folder"
    if "drive.google.com/file" in url:
        return "drive_file"
    if "docs.google.com" in url:
        return "google_doc"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    return "other"


class CTICSectionParser(HTMLParser):
    """
    Parses a CTIC grade-band curriculum page.

    The GoDaddy site builder uses this structure:
    - Section titles (data-aid contains "SECTION" and "TITLE") mark stage boundaries
      e.g., "Stage 1: Introduction To Inventing"
    - ContentCards contain:
      - h4 with data-ux="ContentCardHeading" → activity name
      - <a> with href to Drive/YouTube → resource URL

    We parse the flat HTML stream and track which section (stage) we're in.
    """

    def __init__(self):
        super().__init__()
        self.activities: list[dict] = []
        self.current_stage: str = ""

        # State machine
        self._in_section_title = False
        self._section_title_buf = ""
        self._in_card_heading = False
        self._heading_buf = ""
        self._current_activity_name = ""
        self._pending_activities: list[dict] = []

        # Track data-aid for headline numbering per section
        self._seen_headlines: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr_dict = dict(attrs)
        data_aid = attr_dict.get("data-aid", "")
        data_ux = attr_dict.get("data-ux", "")

        # Detect section title (stage boundary)
        if "SECTION" in data_aid and "TITLE" in data_aid:
            self._in_section_title = True
            self._section_title_buf = ""
            return

        # Detect content card heading (activity name)
        # Only capture the FIRST rendering of each headline (data-aid includes "RENDERED")
        if data_ux == "ContentCardHeading" and "RENDERED" in data_aid:
            if data_aid not in self._seen_headlines:
                self._seen_headlines.add(data_aid)
                self._in_card_heading = True
                self._heading_buf = ""
            return

        # Detect links inside content cards
        if tag == "a" and self._current_activity_name:
            href = attr_dict.get("href", "")
            if href and ("drive.google.com" in href or "docs.google.com" in href or "youtube.com" in href):
                # Clean up HTML entities in href
                href = href.replace("&amp;", "&")
                resource_type = classify_url(href)
                self._pending_activities.append(
                    {
                        "activity_name": self._current_activity_name,
                        "stage": self.current_stage,
                        "resource_url": href,
                        "resource_type": resource_type,
                    }
                )

    def handle_data(self, data: str):
        if self._in_section_title:
            self._section_title_buf += data
        if self._in_card_heading:
            self._heading_buf += data

    def handle_endtag(self, tag: str):
        if self._in_section_title and self._section_title_buf.strip():
            raw = self._section_title_buf.strip()
            self.current_stage = normalize_stage_name(raw)
            self._in_section_title = False
            self._section_title_buf = ""
            # Reset headline tracking for new section
            self._seen_headlines.clear()
            # Flush pending activities from previous section
            self._flush_pending()

        if self._in_card_heading and tag == "h4":
            name = self._heading_buf.strip()
            if name:
                # Flush previous activity if there was one
                self._flush_pending()
                self._current_activity_name = name
            self._in_card_heading = False
            self._heading_buf = ""

    def _flush_pending(self):
        """Move pending activities to the final list."""
        self.activities.extend(self._pending_activities)
        self._pending_activities.clear()

    def close(self):
        """Override close to flush remaining activities."""
        self._flush_pending()
        super().close()


def normalize_stage_name(raw: str) -> str:
    """
    Normalize stage names from section titles.

    Input examples:
        "Stage 1: Introduction To Inventing"
        "Step 4: Engineering Design Process"
        "Supporting Materials"
        "Activities (No Lesson Plans)"

    Output: cleaned stage name like "Introduction To Inventing"
    """
    # Remove "Stage X:" or "Step X:" prefix
    cleaned = re.sub(r"^(?:Stage|Step)\s+\d+:\s*", "", raw, flags=re.IGNORECASE)
    return cleaned.strip()


def crawl_grade_band(grade_band: str, path: str) -> list[CrawledActivity]:
    """Crawl a single grade band page and extract all activities."""
    url = f"{BASE_URL}{path}"
    logger.info(f"Crawling {grade_band} curriculum: {url}")

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    parser = CTICSectionParser()
    parser.feed(response.text)
    parser.close()

    activities = []
    seen = set()  # Deduplicate by (name, url)

    for item in parser.activities:
        key = (item["activity_name"], item["resource_url"])
        if key in seen:
            continue
        seen.add(key)

        activity = CrawledActivity(
            activity_name=item["activity_name"],
            grade_band=grade_band,
            stage=item["stage"],
            resource_url=item["resource_url"],
            resource_type=item["resource_type"],
        )
        activities.append(activity)

    logger.info(f"  Found {len(activities)} unique activities for {grade_band}")
    return activities


def crawl_all() -> list[CrawledActivity]:
    """Crawl all grade band pages and return all activities."""
    all_activities = []

    for grade_band, path in GRADE_BAND_PAGES.items():
        try:
            activities = crawl_grade_band(grade_band, path)
            all_activities.extend(activities)
        except requests.RequestException as e:
            logger.error(f"Failed to crawl {grade_band}: {e}")
        # Be polite to the server
        time.sleep(1)

    logger.info(f"Total activities crawled: {len(all_activities)}")
    return all_activities


def verify_drive_links(activities: list[CrawledActivity]) -> dict[str, bool]:
    """
    Quick health check: verify each Drive folder/file URL is accessible.
    Returns a dict of {resource_url: is_accessible}.
    """
    results = {}
    for activity in activities:
        if activity.resource_type not in ("drive_folder", "drive_file", "google_doc"):
            results[activity.resource_url] = True  # Skip non-Drive URLs
            continue

        try:
            resp = requests.head(activity.resource_url, timeout=10, allow_redirects=True)
            is_ok = resp.status_code < 400
            results[activity.resource_url] = is_ok
            if not is_ok:
                logger.warning(
                    f"Inaccessible: {activity.activity_name} -> {activity.resource_url} (HTTP {resp.status_code})"
                )
        except requests.RequestException as e:
            results[activity.resource_url] = False
            logger.warning(f"Error checking {activity.activity_name}: {e}")

        time.sleep(0.5)  # Rate limit

    accessible = sum(1 for v in results.values() if v)
    logger.info(f"Health check: {accessible}/{len(results)} links accessible")
    return results
