"""Auth routes — registration, login, profile management."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import get_current_user
from src.api.models import (
    RegisterRequest,
    ProfileResponse,
    ProfileUpdateRequest,
)
from src.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
from src.db.operations import (
    create_user_profile,
    get_user_profile,
    update_user_profile,
    get_user_usage_stats,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _get_supabase_admin():
    """Get a Supabase client with service-role privileges."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="Supabase not configured on server.")
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


@router.post("/register")
async def api_register(req: RegisterRequest):
    """
    Register a new user.

    Creates user in Supabase Auth + profile row in our DB.
    Frontend then signs in directly via Supabase client SDK.
    """
    supabase = _get_supabase_admin()

    try:
        auth_response = supabase.auth.admin.create_user(
            {
                "email": req.email,
                "password": req.password,
                "email_confirm": True,
            }
        )
    except Exception as e:
        error_msg = str(e)
        if "already" in error_msg.lower() or "duplicate" in error_msg.lower():
            raise HTTPException(status_code=409, detail="A user with this email already exists.")
        logger.exception("Supabase user creation failed")
        raise HTTPException(status_code=500, detail="Failed to create account.")

    supabase_user = auth_response.user
    if not supabase_user:
        raise HTTPException(status_code=500, detail="Failed to create account.")

    try:
        profile = create_user_profile(
            supabase_id=str(supabase_user.id),
            email=req.email,
            first_name=req.first_name,
            last_name=req.last_name,
            date_of_birth=req.date_of_birth,
            role="teacher",
        )
    except Exception as e:
        # Rollback: delete the Supabase user if profile creation fails
        try:
            supabase.auth.admin.delete_user(str(supabase_user.id))
        except Exception:
            logger.error(f"Failed to rollback Supabase user {supabase_user.id}")
        logger.exception("Profile creation failed")
        raise HTTPException(status_code=500, detail="Failed to create user profile.")

    return {
        "status": "created",
        "user_id": str(supabase_user.id),
        "email": req.email,
        "role": "teacher",
    }


@router.get("/me", response_model=ProfileResponse)
async def api_me(user: Annotated[dict, Depends(get_current_user)]):
    """Get current user's profile and usage stats."""
    user_id = str(user["id"])
    usage = get_user_usage_stats(user_id)

    return ProfileResponse(
        id=user_id,
        email=user["email"],
        first_name=user["first_name"],
        last_name=user["last_name"],
        date_of_birth=str(user["date_of_birth"]) if user.get("date_of_birth") else None,
        role=user["role"],
        is_active=user["is_active"],
        chat_count=usage.get("chat_count", 0) or 0,
        search_count=usage.get("search_count", 0) or 0,
        last_active=str(usage["last_active"]) if usage.get("last_active") else None,
    )


@router.put("/me", response_model=ProfileResponse)
async def api_update_me(
    req: ProfileUpdateRequest,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Update current user's profile (name, DOB). Password changes go through Supabase."""
    user_id = str(user["id"])

    updated = update_user_profile(
        user_id,
        first_name=req.first_name,
        last_name=req.last_name,
        date_of_birth=req.date_of_birth,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Profile not found.")

    usage = get_user_usage_stats(user_id)

    return ProfileResponse(
        id=str(updated["id"]),
        email=updated["email"],
        first_name=updated["first_name"],
        last_name=updated["last_name"],
        date_of_birth=str(updated["date_of_birth"]) if updated.get("date_of_birth") else None,
        role=updated["role"],
        is_active=updated["is_active"],
        chat_count=usage.get("chat_count", 0) or 0,
        search_count=usage.get("search_count", 0) or 0,
        last_active=str(usage["last_active"]) if usage.get("last_active") else None,
    )
