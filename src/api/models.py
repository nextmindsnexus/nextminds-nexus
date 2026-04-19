"""Pydantic request/response models for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field, EmailStr


# --- Search ---

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Natural language search query")
    grade_band: str | None = Field(None, pattern=r"^(K-2|3-5|6-8|9-12)$", description="Grade band filter")
    stage: str | None = Field(None, max_length=100, description="Stage name partial match")
    max_time: int | None = Field(None, gt=0, description="Max activity time in minutes")
    limit: int = Field(5, ge=1, le=20, description="Number of results to return")


class ActivityResult(BaseModel):
    activity_name: str
    grade_band: str
    stage: str
    resource_url: str
    resource_type: str
    drive_id: str | None = None
    similarity: float | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[ActivityResult]
    count: int


# --- Chat ---

class ChatMessage(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    session_id: str | None = Field(None, description="Session ID for conversation continuity")


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    activities: list[ActivityResult] = []


# --- Admin ---

class IngestResponse(BaseModel):
    status: str
    total_crawled: int = 0
    added: int = 0
    updated: int = 0
    removed: int = 0
    errors: int = 0


class StatsResponse(BaseModel):
    total: int
    active: int
    grade_bands: int
    stages: int
    oldest_crawl: str | None = None
    newest_crawl: str | None = None
    by_grade_band: dict[str, int] = {}
    by_stage: dict[str, int] = {}


class HealthResponse(BaseModel):
    status: str
    database: str
    embedding_model: str


class SummarizeResponse(BaseModel):
    status: str
    processed: int = 0
    skipped: int = 0
    errors: int = 0


# --- Auth ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class ProfileResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    date_of_birth: str | None = None
    role: str
    is_active: bool
    chat_count: int = 0
    search_count: int = 0
    last_active: str | None = None


class ProfileUpdateRequest(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    date_of_birth: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")


# --- Admin User Management ---

class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    role: str = Field("teacher", pattern=r"^(teacher|admin)$")


class AdminUpdateUserRequest(BaseModel):
    role: str | None = Field(None, pattern=r"^(teacher|admin)$")
    is_active: bool | None = None


class UserListResponse(BaseModel):
    users: list[ProfileResponse]
    count: int
