"""
FastAPI application for the CTIC Curriculum Recommendation Engine.

Part 2: Backend API
- POST /api/search   — Semantic search with optional filters
- POST /api/chat     — Conversational Gemini assistant with function calling
- DELETE /api/chat/{session_id} — Clear chat session
- POST /api/admin/ingest  — Trigger re-crawl + ingestion
- GET  /api/admin/stats   — Catalog statistics
- GET  /api/admin/health  — System health check

Run with:
    python -m src.api.app
    # or
    uvicorn src.api.app:app --reload --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(level=logging.INFO)

# Setup scheduler for background tasks
scheduler = BackgroundScheduler()

def scheduled_monthly_recrawl():
    """Background job to run the pipeline automatically every month."""
    logging.info("Starting scheduled monthly re-crawl and summarization...")
    try:
        from src.ingest import run_full_ingestion
        from src.summarizer.summarizer import run_summarization
        run_full_ingestion(triggered_by="cron")
        run_summarization(limit=None)
        logging.info("Monthly scheduled job completed successfully.")
    except Exception as e:
        logging.error(f"Monthly scheduled job failed: {e}")

try:
    from src.api.routes.search import router as search_router
    from src.api.routes.chat import router as chat_router
    from src.api.routes.admin import router as admin_router
    from src.api.routes.auth_routes import router as auth_router
    logging.info("Routes imported successfully")
except Exception as e:
    logging.exception("Failed to import routes")
    raise


app = FastAPI(
    title="Nexus Curriculum Engine API",
    description="Conversational recommendation engine for NextMinds curriculum activities. "
                "Helps teachers discover and share invention-based learning resources.",
    version="0.2.0",
)

@app.on_event("startup")
async def startup_event():
    # Schedule the job to run automatically every month (on the 1st at midnight)
    if not scheduler.running:
        scheduler.add_job(scheduled_monthly_recrawl, 'cron', day=1, hour=0, minute=0)
        scheduler.start()
        logging.info("APScheduler started: Monthly recrawl scheduled on the 1st day of every month at midnight.")

@app.on_event("shutdown")
async def shutdown_event():
    if scheduler.running:
        scheduler.shutdown()
        logging.info("APScheduler shutdown.")

# CORS setup for frontend on Render and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://nextminds-nexus-frontend.onrender.com",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
try:
    app.include_router(search_router)
    app.include_router(chat_router)
    app.include_router(admin_router)
    app.include_router(auth_router)
    logging.info("Routers registered successfully")
except Exception as e:
    logging.exception("Failed to register routers")
    raise


@app.get("/")
async def root():
    return {
        "name": "Nexus Curriculum Engine API",
        "version": "0.2.0",
        "docs": "/docs",
        "endpoints": {
            "search": "POST /api/search",
            "chat": "POST /api/chat",
            "stats": "GET /api/admin/stats",
            "health": "GET /api/admin/health",
            "ingest": "POST /api/admin/ingest",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=True)
