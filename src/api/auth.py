"""
Supabase JWT verification and FastAPI auth dependencies.

Decodes Supabase-issued JWTs, looks up user_profiles for role info.
Supports both HS256 (legacy) and ES256 (newer Supabase projects via JWKS).
"""

from __future__ import annotations

import logging
from typing import Annotated

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import SUPABASE_JWT_SECRET, SUPABASE_URL
from src.db.operations import get_user_profile

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

# JWKS client for ES256 verification (lazy-loaded, cached)
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> dict:
    """
    FastAPI dependency: decode Supabase JWT and return user profile dict.

    Raises 401 if token missing/invalid/expired, 403 if account disabled.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        # Check token header to determine algorithm
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg == "HS256":
            # Legacy symmetric verification
            if not SUPABASE_JWT_SECRET:
                logger.error("SUPABASE_JWT_SECRET not configured")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Auth not configured on server.",
                )
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            # Asymmetric (ES256) verification via JWKS
            if not SUPABASE_URL:
                logger.error("SUPABASE_URL not configured for JWKS")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Auth not configured on server.",
                )
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )

    profile = get_user_profile(user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User profile not found. Please register.",
        )

    if not profile.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Contact an administrator.",
        )

    return profile


def require_role(role: str):
    """
    FastAPI dependency factory: require a specific role.

    Usage:
        @router.get("/admin/thing", dependencies=[Depends(require_role("admin"))])
    """

    async def _check_role(
        user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        if user.get("role") != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{role}' role.",
            )
        return user

    return _check_role
