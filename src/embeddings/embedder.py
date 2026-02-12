"""
Embedding pipeline using sentence-transformers (all-MiniLM-L6-v2).

Generates 384-dimensional embeddings for activity records
to enable semantic search via pgvector.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from src.config import EMBEDDING_MODEL, EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    """Load and cache the embedding model. First call downloads if needed."""
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    return model


def embed_text(text: str) -> list[float]:
    """Generate an embedding vector for a single text string."""
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts. More efficient than one-by-one."""
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    return [e.tolist() for e in embeddings]


def build_embedding_text(
    activity_name: str,
    stage: str,
    grade_band: str,
    description: str | None = None,
    keywords: list[str] | None = None,
) -> str:
    """
    Build the text string that gets embedded for an activity.

    Combines key fields into a single string optimized for semantic matching.
    A teacher asking "prototyping activity for 3rd graders" should match
    activities in the "Engineering Design Process" stage for grade band "3-5".
    """
    parts = [
        activity_name,
        f"Grade level: {grade_band}",
        f"Stage: {stage}",
    ]
    if description:
        parts.append(description)
    if keywords:
        parts.append(f"Keywords: {', '.join(keywords)}")

    return " | ".join(parts)
