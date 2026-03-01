"""Placeholder JWT auth — Phase 1.

Any non-empty Bearer token is accepted and used as the track_id.
This will be replaced with real JWT validation in Phase 2.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from gym_shared.logging import get_logger

log = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_track_id(token: str = oauth2_scheme) -> str:  # type: ignore[assignment]
    """Return token as track_id.  Any non-empty Bearer token is accepted."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing auth token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    log.debug("auth_placeholder", track_id=token)
    return token
