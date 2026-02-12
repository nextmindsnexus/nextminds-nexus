# CTIC Curriculum Recommendation Engine

A conversational recommendation engine that helps teachers discover and share CTIC (Connecticut Invention Convention) curriculum resources via Google Classroom.

## Architecture

```
Part 1: Data Pipeline (this)     Part 2: Backend API        Part 3: Frontend
┌─────────────────────┐     ┌──────────────────────┐    ┌──────────────────┐
│ Website Crawler      │     │ FastAPI              │    │ React Chat UI    │
│   ↓                  │     │ Gemini Conversation  │    │ Share to         │
│ Embedding Pipeline   │     │ Search Endpoint      │    │   Classroom      │
│   ↓                  │     │ Admin Endpoints      │    │ Admin Dashboard  │
│ Supabase/pgvector    │     │                      │    │                  │
└─────────────────────┘     └──────────────────────┘    └──────────────────┘
```

## Part 1: Data Pipeline

### What it does

1. **Crawls** the CTIC website (`ctinventionconvention.org`) to extract the curriculum taxonomy:
   - 4 grade bands: K-2, 3-5, 6-8, 9-12
   - 6 stages per grade band (Introduction to Inventing, Identifying & Ideating, Understanding, Engineering Design, Communication, Entrepreneurship)
   - Activities within each stage, linked to Google Drive folders

2. **Generates embeddings** using `all-MiniLM-L6-v2` (open source, 384 dimensions, runs locally)

3. **Stores everything** in Supabase PostgreSQL with pgvector for semantic search

### Quick Start

#### 1. Install dependencies

```bash
cd ctic-curriculum-engine
pip install -e ".[dev]"
```

Or install manually:
```bash
pip install beautifulsoup4 requests psycopg[binary] pgvector sentence-transformers python-dotenv rich
```

#### 2. Test the crawler (no database needed)

```bash
python -m src crawl
```

This hits the live CTIC site and prints all 109 discovered activities with their grade bands, stages, and Drive links. No database, no API keys, no setup required.

#### 3. Set up Supabase

1. Create a free project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run the schema from `src/db/schema.py` (the `SCHEMA_SQL` constant)
3. Copy your database URL from **Settings → Database → Connection string (URI)**
4. Create `.env`:

```bash
cp .env.example .env
# Edit .env and add your DATABASE_URL
```

#### 4. Run the full pipeline

```bash
python -m src ingest
```

This will:
- Crawl all 4 grade band pages
- Generate 384-dim embeddings for each activity
- Upsert everything into your Supabase database
- Print a summary of what was added/updated

#### 5. Test search

```bash
# Semantic search
python -m src search "prototyping activity for 3rd graders"

# With filters
python -m src search "brainstorming ideas" --grade "K-2"
python -m src search "presenting inventions" --stage "Communication"

# Catalog stats
python -m src stats
```

### CLI Commands

| Command | Description | Needs DB? |
|---------|-------------|-----------|
| `python -m src crawl` | Crawl site, print results | No |
| `python -m src ingest` | Full pipeline: crawl → embed → store | Yes |
| `python -m src search "query"` | Semantic search with optional filters | Yes |
| `python -m src stats` | Show catalog statistics | Yes |
| `python -m src health` | Check Drive link accessibility | Yes |
| `python -m src init-db` | Initialize schema only | Yes |

### Project Structure

```
ctic-curriculum-engine/
├── src/
│   ├── __init__.py
│   ├── __main__.py          # python -m src entry point
│   ├── cli.py               # CLI commands
│   ├── config.py            # Environment config
│   ├── ingest.py            # Orchestrates crawl → embed → store
│   ├── crawler/
│   │   ├── __init__.py
│   │   └── site_crawler.py  # CTIC website parser + Drive link extractor
│   ├── embeddings/
│   │   ├── __init__.py
│   │   └── embedder.py      # sentence-transformers embedding pipeline
│   ├── db/
│   │   ├── __init__.py
│   │   ├── schema.py        # SQL schema for pgvector
│   │   └── operations.py    # CRUD + vector search queries
│   └── utils/
│       └── __init__.py
├── tests/
├── .env.example
├── .gitignore
└── pyproject.toml
```

### Tech Stack (Part 1)

| Component | Technology |
|-----------|-----------|
| Crawler | BeautifulSoup + requests |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (open source, local) |
| Database | Supabase PostgreSQL + pgvector |
| DB Driver | psycopg3 + pgvector-python |
| CLI | argparse + rich |

### Data Model

Each **activity** record contains:
- `activity_name` — "Survival Challenge", "Brainstorming 101", etc.
- `grade_band` — K-2, 3-5, 6-8, 9-12
- `stage` — "Introduction To Inventing", "Engineering Design Process", etc.
- `resource_url` — Google Drive folder/file URL (the recommendation unit)
- `resource_type` — drive_folder, drive_file, google_doc, youtube
- `drive_id` — Extracted Drive ID (stable even if folder is moved)
- `embedding` — 384-dim vector for semantic search
- `is_active` — Health check flag

### What's Next

**Part 2: Backend API** will add:
- FastAPI with `/chat` and `/search` endpoints
- Gemini conversation engine with function calling
- Admin endpoints for triggering re-crawl and health checks

**Part 3: Frontend** will add:
- React chat interface
- Google Classroom Share buttons on each result
- Admin dashboard
