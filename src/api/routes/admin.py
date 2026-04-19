"""Admin routes — trigger re-crawl, view stats, health check, user management."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import get_current_user, require_role
from src.api.models import (
    IngestResponse, StatsResponse, HealthResponse, SummarizeResponse,
    AdminCreateUserRequest, AdminUpdateUserRequest, UserListResponse, ProfileResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

_admin_dep = Depends(require_role("admin"))


@router.post("/ingest", response_model=IngestResponse, dependencies=[_admin_dep])
async def api_ingest():
    """Trigger a full re-crawl and ingestion pipeline."""
    try:
        from src.ingest import run_full_ingestion
        from src.summarizer.summarizer import run_summarization
        
        # 1. Run crawler/embedder
        summary = run_full_ingestion(triggered_by="api")
        
        # 2. Automatically summarize new items
        run_summarization(limit=None)
        
    except Exception as e:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    if "error" in summary:
        return IngestResponse(status="error")

    return IngestResponse(
        status="completed",
        total_crawled=summary.get("total_crawled", 0),
        added=summary.get("added", 0),
        updated=summary.get("updated", 0),
        removed=summary.get("removed", 0),
        errors=summary.get("errors", 0),
    )


@router.get("/stats", response_model=StatsResponse, dependencies=[_admin_dep])
async def api_stats():
    """Get catalog statistics."""
    try:
        from src.db.operations import get_activity_stats
        stats = get_activity_stats()
    except Exception as e:
        logger.exception("Stats query failed")
        raise HTTPException(status_code=500, detail="Could not retrieve stats.")

    return StatsResponse(
        total=stats["total"],
        active=stats["active"],
        grade_bands=stats["grade_bands"],
        stages=stats["stages"],
        oldest_crawl=str(stats.get("oldest_crawl", "")),
        newest_crawl=str(stats.get("newest_crawl", "")),
        by_grade_band=stats.get("by_grade_band", {}),
        by_stage=stats.get("by_stage", {}),
    )


@router.get("/health", response_model=HealthResponse)
async def api_health():
    """Check API health: database connectivity and embedding model."""
    db_status = "unknown"
    model_status = "unknown"

    # Check database
    try:
        from src.db.operations import get_connection
        with get_connection() as conn:
            conn.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    # Check embedding model
    try:
        from src.embeddings.embedder import get_model
        get_model()
        model_status = "loaded"
    except Exception as e:
        model_status = f"error: {e}"

    overall = "healthy" if db_status == "connected" and model_status == "loaded" else "degraded"

    return HealthResponse(
        status=overall,
        database=db_status,
        embedding_model=model_status,
    )


@router.post("/summarize", response_model=SummarizeResponse, dependencies=[_admin_dep])
async def api_summarize(limit: int | None = None):
    """Trigger summarization for unsummarized activities."""
    try:
        from src.summarizer.summarizer import run_summarization
        result = run_summarization(limit=limit)
    except Exception as e:
        logger.exception("Summarization failed")
        raise HTTPException(status_code=500, detail=f"Summarization failed: {e}")

    return SummarizeResponse(
        status="completed",
        processed=result.get("processed", 0),
        skipped=result.get("skipped", 0),
        errors=result.get("errors", 0),
    )


# ============================================
# User management endpoints (admin only)
# ============================================

@router.get("/users", response_model=UserListResponse, dependencies=[_admin_dep])
async def api_list_users(limit: int = 50, offset: int = 0):
    """List all users with usage statistics."""
    from src.db.operations import list_users_with_usage

    users = list_users_with_usage(limit=limit, offset=offset)
    return UserListResponse(
        users=[
            ProfileResponse(
                id=str(u["id"]),
                email=u["email"],
                first_name=u["first_name"],
                last_name=u["last_name"],
                date_of_birth=str(u["date_of_birth"]) if u.get("date_of_birth") else None,
                role=u["role"],
                is_active=u["is_active"],
                chat_count=u.get("chat_count", 0) or 0,
                search_count=u.get("search_count", 0) or 0,
                last_active=str(u["last_active"]) if u.get("last_active") else None,
            )
            for u in users
        ],
        count=len(users),
    )


@router.post("/users", dependencies=[_admin_dep])
async def api_create_user(req: AdminCreateUserRequest):
    """Admin creates a new user (can set role to admin)."""
    from src.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
    from src.db.operations import create_user_profile

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="Supabase not configured.")

    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    try:
        auth_response = sb.auth.admin.create_user(
            {"email": req.email, "password": req.password, "email_confirm": True}
        )
    except Exception as e:
        error_msg = str(e)
        if "already" in error_msg.lower() or "duplicate" in error_msg.lower():
            raise HTTPException(status_code=409, detail="User with this email already exists.")
        logger.exception("Failed to create Supabase user")
        raise HTTPException(status_code=500, detail="Failed to create user.")

    supabase_user = auth_response.user
    if not supabase_user:
        raise HTTPException(status_code=500, detail="Failed to create user.")

    try:
        create_user_profile(
            supabase_id=str(supabase_user.id),
            email=req.email,
            first_name=req.first_name,
            last_name=req.last_name,
            date_of_birth=req.date_of_birth,
            role=req.role,
        )
    except Exception:
        try:
            sb.auth.admin.delete_user(str(supabase_user.id))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to create user profile.")

    return {"status": "created", "user_id": str(supabase_user.id), "email": req.email, "role": req.role}


@router.put("/users/{user_id}", dependencies=[_admin_dep])
async def api_update_user(user_id: str, req: AdminUpdateUserRequest):
    """Update a user's role or active status."""
    from src.db.operations import set_user_role, set_user_active

    if req.role is not None:
        if not set_user_role(user_id, req.role):
            raise HTTPException(status_code=404, detail="User not found.")

    if req.is_active is not None:
        if not set_user_active(user_id, req.is_active):
            raise HTTPException(status_code=404, detail="User not found.")

    return {"status": "updated", "user_id": user_id}


@router.delete("/users/{user_id}", dependencies=[_admin_dep])
async def api_delete_user(user_id: str):
    """Delete a user from both our DB and Supabase Auth."""
    from src.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
    from src.db.operations import delete_user_profile

    if not delete_user_profile(user_id):
        raise HTTPException(status_code=404, detail="User not found.")

    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        try:
            from supabase import create_client
            sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            sb.auth.admin.delete_user(user_id)
        except Exception as e:
            logger.warning(f"Failed to delete Supabase auth user {user_id}: {e}")

    return {"status": "deleted", "user_id": user_id}
