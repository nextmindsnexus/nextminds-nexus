"""Chat route — conversational Gemini endpoint with function calling."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from google.genai.errors import ClientError

from src.api.auth import get_current_user
from src.api.models import ChatRequest, ChatResponse, ActivityResult
from src.api.chat_engine import chat, clear_session
from src.db.operations import log_usage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def api_chat(req: ChatRequest, user: Annotated[dict, Depends(get_current_user)]):
    """Send a message to the CTIC Curriculum Assistant."""
    try:
        log_usage(str(user["id"]), "chat_message", req.session_id)
    except Exception:
        pass  # Don't block chat on usage logging failure

    try:
        reply, session_id, activities = chat(
            message=req.message,
            session_id=req.session_id,
        )
    except ClientError as e:
        if e.code == 429:
            raise HTTPException(
                status_code=429,
                detail="Gemini API rate limit reached. Please wait a moment and try again.",
                headers={"Retry-After": "60"},
            )
        logger.exception("Gemini API error")
        raise HTTPException(status_code=502, detail=f"Gemini API error: {e}")
    except RuntimeError as e:
        # Missing API key, config errors
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail="Chat request failed.")

    activity_results = [
        ActivityResult(
            activity_name=a["activity_name"],
            grade_band=a["grade_band"],
            stage=a["stage"],
            resource_url=a["resource_url"],
            resource_type=a["resource_type"],
            drive_id=a.get("drive_id"),
            similarity=a.get("similarity"),
        )
        for a in activities
    ]

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        activities=activity_results,
    )


@router.delete("/chat/{session_id}")
async def api_clear_chat(session_id: str):
    """Clear conversation history for a session."""
    clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}
