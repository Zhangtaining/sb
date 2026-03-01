"""Worker service configuration."""
from __future__ import annotations

from dataclasses import dataclass

from gym_shared.settings import settings


@dataclass(frozen=True)
class WorkerConfig:
    redis_url: str
    database_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket_clips: str
    minio_secure: bool
    # Frames stored in ingestion buffer per camera
    frame_buffer_size: int


def build_config() -> WorkerConfig:
    return WorkerConfig(
        redis_url=settings.redis_url,
        database_url=settings.database_url,
        minio_endpoint=settings.minio_endpoint,
        minio_access_key=settings.minio_access_key,
        minio_secret_key=settings.minio_secret_key,
        minio_bucket_clips=settings.minio_bucket_clips,
        minio_secure=settings.minio_secure,
        frame_buffer_size=settings.frame_buffer_size,
    )
