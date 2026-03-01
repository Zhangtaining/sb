"""FastAPI dependency injectors — DB session, Redis connection."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from gym_shared.db.session import get_db as _get_db


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with _get_db() as session:
        yield session


async def get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
Redis = Annotated[aioredis.Redis, Depends(get_redis)]
