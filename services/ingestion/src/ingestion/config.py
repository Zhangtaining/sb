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
    """Build IngestionConfig from shared gym_shared.settings.Settings."""
    cameras = []
    for camera_id in settings.camera_id_list:
        rtsp_env_key = f"CAMERA_{camera_id.upper().replace('-', '_')}_RTSP"
        # Cameras without an explicit RTSP URL will use a placeholder
        rtsp_url = getattr(settings, rtsp_env_key.lower(), f"rtsp://{camera_id}/live")
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
