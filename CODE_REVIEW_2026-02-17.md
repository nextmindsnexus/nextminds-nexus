# Code Review: CTIC Curriculum Recommendation Engine (Part 1)

**Reviewer:** Kenneth Kousen
**Date:** 2026-02-17
**Scope:** Part 1 — Data Pipeline (crawl → embed → store)

---

## Overall Impression

This is a well-structured Part 1. The pipeline architecture (crawl → embed → store) is clean, the module boundaries are sensible, and the test suite is thorough at 82 tests. The README is excellent — clear architecture diagram, quick start instructions, and a well-thought-out data model.

The three-part architecture (data pipeline, backend API, frontend) is a solid decomposition for a recommendation engine. Separating the data pipeline as Part 1 lets you validate that the crawled data is correct before building the conversational layer on top of it.

---

## Strengths

### 1. Clean Module Separation

`crawler/`, `embeddings/`, `db/` are properly isolated. Each has a single clear responsibility. This makes it easy to test, modify, and reason about each piece independently.

### 2. The HTML Parser (`site_crawler.py`)

Using `HTMLParser` directly instead of just BeautifulSoup is a mature choice for a GoDaddy-built site with non-standard markup. The state machine approach (tracking `_in_section_title`, `_in_card_heading`, etc.) handles the flat HTML stream well.

### 3. Upsert Strategy (`operations.py`)

The `ON CONFLICT ... DO UPDATE` with `RETURNING (xmax = 0) AS is_insert` is a clean PostgreSQL idiom. The `COALESCE` on optional fields (description, time, keywords) means re-crawls preserve manually-added metadata. That's a thoughtful design choice.

### 4. Test Coverage

Tests mock external dependencies properly (no real HTTP calls, no real DB), and cover edge cases (empty HTML, failed grade bands, broken links).

### 5. Crawl Logging (`crawl_logs` table)

Tracking each pipeline run with added/updated/removed/errors counts is excellent for operational visibility. Many projects skip observability entirely.

---

## Issues to Address

### Security / SQL Injection Risk (Medium Priority)

**File:** `src/db/operations.py`, line 206

The `search_activities` function builds SQL via f-string interpolation:

```python
query = f"""
    SELECT ...
    FROM activities
    WHERE {where_clause}
    ORDER BY embedding <=> %(embedding)s::vector
    LIMIT %(limit)s
"""
```

The `where_clause` is built from hardcoded condition strings, and the actual *values* are parameterized — so this is **not currently exploitable**. But it's fragile. If someone later adds a condition using user input directly in the string (e.g., `conditions.append(f"stage = '{stage}'")`), it becomes injectable. Add a comment warning future developers, or refactor to use a query builder.

### Bug: `normalize_stage_name` Doesn't Strip Before Regex (Low Priority)

**File:** `src/crawler/site_crawler.py`, lines 182–196

The function applies a regex anchored to `^` but doesn't strip whitespace first. If the website ever returns a section title with leading whitespace, the stage name won't be normalized:

```python
# Current behavior:
#   "  Stage 2: Identifying" → "  Stage 2: Identifying" (prefix NOT stripped)
# Expected behavior:
#   "  Stage 2: Identifying" → "Identifying"
```

**Fix:** Add `.strip()` before the regex, or change the regex to `r"^\s*(?:Stage|Step)\s+\d+:\s*"`.

Note: The test at `test_crawler.py:89-92` documents this as expected behavior, but it's actually asserting the *current* (broken) behavior, not the *correct* behavior. Update the test when you fix the function.

### Connection Management: One Connection Per Health Update (High Priority)

**File:** `src/db/operations.py`, lines 272–284
**Called from:** `src/ingest.py`, lines 187–189

`update_health_status` opens a new database connection *per URL*:

```python
def update_health_status(resource_url: str, is_accessible: bool):
    with get_connection() as conn:   # <-- new TCP connection each time
        conn.execute(...)
        conn.commit()
```

And it's called in a loop:

```python
for url, is_ok in results.items():
    update_health_status(url, is_ok)  # 100+ separate connections
```

For 100+ activities, that's 100+ separate TCP connections to Supabase.

**Fix:** Either accept a `conn` parameter (like `upsert_activity` already does), or batch the updates into a single query.

### Unused Import in Production Code (Low Priority)

**File:** `src/ingest.py`, line 151

```python
from src.db.operations import search_activities as _  # noqa: just check import
```

This import does nothing at runtime. If it was meant as a sanity check, it belongs in tests, not production code. Remove it.

### `.env.example` vs `config.py` Mismatch (Medium Priority)

The `.env.example` shows `DATABASE_URL` as the primary config variable, but `config.py` now uses `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` as primary, with `DATABASE_URL` as fallback. Update `.env.example` to show the preferred individual fields.

### `config.py` Loads at Import Time (Low Priority — Plan Ahead)

**File:** `src/config.py`, line 6

`load_dotenv()` runs at module import time. This is standard for CLI apps, but when Part 2 wraps this with FastAPI, you'll want to move to a function-based or class-based config pattern (e.g., `pydantic-settings`) so you can test with different configurations.

### No Connection Pooling (Low Priority — Plan Ahead)

**File:** `src/db/operations.py`, lines 24–41

Every `get_connection()` call creates a fresh TCP connection. This is fine for a CLI tool (Part 1), but when Part 2 adds FastAPI, you'll need a connection pool (e.g., `psycopg_pool.ConnectionPool`). Worth designing the interface now so it can accommodate pooling later.

---

## Minor Observations

| File | Line(s) | Note |
|------|---------|------|
| `src/cli.py` | 98 | `build_embedding_text` is imported but not used in `cmd_search` — `embed_text` already handles raw query text |
| `src/ingest.py` | 15 | `datetime` and `timezone` are imported but never used |
| `.gitignore` | — | Missing `.DS_Store` (macOS metadata files) |
| `pyproject.toml` | 18 | `pytest-asyncio` is in dev deps but nothing is async yet — is this planned for Part 2? |
| `src/db/schema.py` | 39 | The IVFFlat index comment is helpful — consider adding a CLI command (`python -m src create-index`) to run it after first ingestion |

---

## Test Suite Notes

The tests are well-structured overall, but a few CLI tests don't actually test behavior:

**File:** `tests/test_cli.py`, lines 78–105

`TestCmdStats.test_stats_displays` and `TestCmdInitDb.test_init_db_calls_schema` use this pattern:

```python
with patch("src.cli.init_schema", mock_init, create=True):
    pass  # Just verify importability
```

This only verifies the import path is valid — it doesn't call the function or check output. These should actually invoke `cmd_stats(args)` and `cmd_init_db(args)` with the mocked dependencies and verify the behavior.

---

## Architecture Suggestions for Parts 2 & 3

### Embedding Text vs. Natural Language Queries

`build_embedding_text` in `src/embeddings/embedder.py` concatenates fields with `" | "` separators (e.g., `"Brainstorming 101 | Grade level: K-2 | Stage: Identifying and Ideating"`). When Part 2 adds Gemini conversation, users will search with natural language like *"prototyping activity for 3rd graders"* — which has a very different structure. Consider testing with natural-language queries against your embedded data to validate that semantic similarity still works well across these different formats.

### Unique Key Consideration

The unique constraint is on `(resource_url, activity_name)`. If CTIC reorganizes their Google Drive structure (new folder URLs for the same content), you'll get duplicates rather than updates. The `drive_id` field might serve as a more stable identifier when available.

---

## Summary

| Category | Rating | Notes |
|----------|--------|-------|
| Code organization | Strong | Clean module boundaries, good separation of concerns |
| Data model design | Strong | Thoughtful schema with operational fields |
| Error handling | Good | Pipeline-level handling solid; connection-level needs work |
| Test coverage | Good | Well-structured mocks; some CLI tests need to actually test |
| Security posture | Acceptable | Fine for Part 1, needs attention before Part 2 (API) |
| Documentation | Excellent | README is clear and complete |

### Priority Fixes

1. **High:** Fix connection-per-health-update (performance issue with Supabase)
2. **Medium:** Update `.env.example` to match current `config.py` fields
3. **Medium:** Add comment or refactor `search_activities` SQL construction
4. **Low:** Fix CLI tests that don't call the functions they claim to test
5. **Low:** Remove dead import in `ingest.py:151`
6. **Low:** Fix `normalize_stage_name` to handle leading whitespace

Good work on Part 1. The foundation is solid for building Parts 2 and 3 on top of.
