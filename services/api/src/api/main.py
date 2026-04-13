"""FastAPI application factory for the Smart Gym API Gateway."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gym_shared.logging import configure_logging, get_logger
from gym_shared.settings import settings

from api.routers import chat, conversations, persons, sessions, tracks
from api.routers.tracks import cameras_router
from api.routers import websocket as ws_router
from api.websocket_manager import WebSocketManager

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_format, settings.log_level)
    log.info("api_service_starting")

    # Shared Redis connection
    redis = aioredis.from_url(settings.redis_url, decode_responses=False)
    app.state.redis = redis

    # WebSocket manager — start background reader
    manager = WebSocketManager()
    ws_router.set_manager(manager)
    reader_task = asyncio.create_task(manager.run_reader(redis))

    log.info("api_service_ready", host=settings.api_host, port=settings.api_port)

    yield

    reader_task.cancel()
    try:
        await reader_task
    except asyncio.CancelledError:
        pass
    await redis.aclose()
    log.info("api_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Gym API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat.router)
    app.include_router(sessions.router)
    app.include_router(tracks.router)
    app.include_router(cameras_router)
    app.include_router(ws_router.router)
    app.include_router(conversations.router)
    app.include_router(persons.router)

    @app.get("/healthz", tags=["health"])
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()
