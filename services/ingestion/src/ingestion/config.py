"""Ingestion service configuration."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CameraConfig:
    """Per-camera configuration derived from shared settings."""

    camera_id: str
    rtsp_url: str
    fps: int = 15
    jpeg_quality: int = 85
    frame_buffer_size: int = 225  # 15 FPS × 15 s rolling buffer


@dataclass(frozen=True)
class IngestionConfig:
    """Top-level config assembled from shared Settings."""

    cameras: list[CameraConfig] = field(default_factory=list)
    redis_url: str = "redis://localhost:6379/0"
    stream_maxlen: int = 100  # Approximate Redis Stream MAXLEN per camera


def build_config(settings) -> IngestionConfig:
    """Build IngestionConfig from shared gym_shared.settings.Settings.

    Per-camera RTSP URLs are read from environment variables of the form:
        CAMERA_<ID>_RTSP_URL=rtsp://...
    where <ID> is the camera ID with dashes replaced by underscores, uppercased.
    Example: camera ID "cam-01" → CAMERA_CAM_01_RTSP_URL

    If the env var is not set, falls back to CAMERA_DEFAULT_RTSP_URL,
    then to "rtsp://<camera_id>/live" as a last resort.
    """
    import os

    cameras = []
    default_rtsp = os.environ.get("CAMERA_DEFAULT_RTSP_URL", "")
    for camera_id in settings.camera_id_list:
        env_key = f"CAMERA_{camera_id.upper().replace('-', '_')}_RTSP_URL"
        rtsp_url = os.environ.get(env_key) or default_rtsp or f"rtsp://{camera_id}/live"
        cameras.append(
            CameraConfig(
                camera_id=camera_id,
                rtsp_url=rtsp_url,
                fps=settings.ingest_fps,
                jpeg_quality=settings.ingest_jpeg_quality,
                frame_buffer_size=settings.frame_buffer_size,
            )
        )
    return IngestionConfig(
        cameras=cameras,
        redis_url=settings.redis_url,
    )
