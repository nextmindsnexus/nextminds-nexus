"""
Content extractor — reads document content from Google Drive resources.

Supports Google Docs (exported as plain text), Drive files, and Drive folders.
Uses a service account for authentication when configured, otherwise
falls back to public access via requests.
"""

from __future__ import annotations

import logging
import re

import requests

from src.config import GOOGLE_SERVICE_ACCOUNT_KEY

logger = logging.getLogger(__name__)

_drive_service = None


def _get_drive_service():
    """Lazily build and cache a Google Drive API service client."""
    global _drive_service
    if _drive_service is not None:
        return _drive_service

    if not GOOGLE_SERVICE_ACCOUNT_KEY:
        logger.warning("GOOGLE_SERVICE_ACCOUNT_KEY not set — Drive content extraction disabled")
        return None

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_KEY,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    _drive_service = build("drive", "v3", credentials=creds)
    return _drive_service


def _extract_drive_id(url: str) -> str | None:
    """Extract a Google Drive file/folder ID from a URL."""
    patterns = [
        r"/folders/([a-zA-Z0-9_-]+)",
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"/document/d/([a-zA-Z0-9_-]+)",
        r"/spreadsheets/d/([a-zA-Z0-9_-]+)",
        r"/presentation/d/([a-zA-Z0-9_-]+)",
        r"[?&]id=([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def _export_google_doc(file_id: str) -> str | None:
    """Export a Google Doc/Sheet/Slides as plain text via Drive API."""
    service = _get_drive_service()
    if not service:
        return None
    try:
        content = service.files().export(fileId=file_id, mimeType="text/plain").execute()
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        return str(content)
    except Exception as e:
        logger.warning(f"Failed to export doc {file_id}: {e}")
        return None


def _extract_pdf_text(raw_bytes: bytes) -> str | None:
    """Extract text from PDF bytes using pdfplumber."""
    import io

    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed — cannot extract PDF text")
        return None

    try:
        with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages) if pages else None
    except Exception as e:
        logger.warning(f"pdfplumber failed: {e}")
        return None


def _download_file_content(file_id: str) -> str | None:
    """Download a Drive file and return its text content."""
    service = _get_drive_service()
    if not service:
        return None
    try:
        # Get file metadata to check MIME type
        meta = service.files().get(fileId=file_id, fields="mimeType,name,size").execute()
        mime = meta.get("mimeType", "")

        # Google Workspace files → export as plain text
        if mime.startswith("application/vnd.google-apps."):
            return _export_google_doc(file_id)

        # Size limits: 10 MB for PDFs, 5 MB for other files
        size = int(meta.get("size", 0))
        is_pdf = mime == "application/pdf"
        max_size = 10_000_000 if is_pdf else 5_000_000
        if size > max_size:
            logger.info(f"Skipping large file {file_id} ({size} bytes)")
            return None

        raw = service.files().get_media(fileId=file_id).execute()
        if not isinstance(raw, bytes):
            raw = str(raw).encode("utf-8")

        # PDFs need pdfplumber for real text extraction
        if is_pdf:
            return _extract_pdf_text(raw)

        # Other text-based files
        return raw.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Failed to download file {file_id}: {e}")
        return None


def _list_folder_files(folder_id: str, max_files: int = 10) -> list[str]:
    """List file IDs in a Drive folder (top-level only)."""
    service = _get_drive_service()
    if not service:
        return []
    try:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id,name,mimeType)",
            pageSize=max_files,
        ).execute()
        return [f["id"] for f in resp.get("files", [])]
    except Exception as e:
        logger.warning(f"Failed to list folder {folder_id}: {e}")
        return []


def extract_content(
    resource_url: str,
    resource_type: str,
    drive_id: str | None = None,
) -> str | None:
    """
    Extract text content from a resource URL.

    Returns the document text or None if extraction fails or is unsupported.
    """
    if not drive_id:
        drive_id = _extract_drive_id(resource_url)

    if not drive_id:
        logger.debug(f"No drive_id for {resource_url}")
        return None

    if resource_type == "google_doc":
        return _export_google_doc(drive_id)

    elif resource_type == "drive_file":
        return _download_file_content(drive_id)

    elif resource_type == "drive_folder":
        # Read up to 10 files in the folder, concatenate
        file_ids = _list_folder_files(drive_id, max_files=10)
        if not file_ids:
            return None
        parts = []
        for fid in file_ids:
            text = _download_file_content(fid)
            if text:
                parts.append(text[:8000])  # Cap each file
        return "\n\n---\n\n".join(parts) if parts else None

    elif resource_type == "youtube":
        # YouTube transcript extraction (best-effort, no API key needed)
        return _extract_youtube_transcript(resource_url)

    return None


def _extract_youtube_transcript(url: str) -> str | None:
    """Try to fetch a YouTube video transcript. Returns None if unavailable."""
    video_id = None
    m = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    if m:
        video_id = m.group(1)
    if not video_id:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(entry["text"] for entry in transcript)
    except Exception:
        logger.debug(f"No transcript available for {video_id}")
        return None
