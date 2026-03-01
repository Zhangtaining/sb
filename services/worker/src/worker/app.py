"""Celery application instance."""
from __future__ import annotations

from celery import Celery

from gym_shared.settings import settings

app = Celery(
    "gym_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.tasks.video_clip"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)
