from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from redis.asyncio import Redis

from gym_shared.settings import settings

_pool: aioredis.ConnectionPool | None = None


def _get_pool() -> aioredis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=20,
            decode_responses=False,  # keep bytes for binary frame data
        )
    return _pool


def get_redis() -> Redis:
    """Return a Redis client using the shared connection pool.

    The client is not a context manager — call .aclose() when done,
    or use get_redis_ctx() for automatic cleanup.
    """
    return aioredis.Redis(connection_pool=_get_pool())


@asynccontextmanager
async def get_redis_ctx() -> AsyncGenerator[Redis, None]:
    """Async context manager that yields a Redis client."""
    client = get_redis()
    try:
        yield client
    finally:
        await client.aclose()


async def close_redis() -> None:
    """Close the global connection pool. Call on application shutdown."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
