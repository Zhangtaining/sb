"""ReID service configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReidConfig:
    camera_ids: list[str] = field(default_factory=list)
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://gym:gympass@localhost:5432/gymdb"

    # Identity matching thresholds
    reid_similarity_threshold: float = 0.75
    face_similarity_threshold: float = 0.85

    # Number of OSNet embeddings to collect before attempting a match
    min_embeddings_before_match: int = 10

    # Gallery cache TTL in seconds (refresh from DB periodically)
    gallery_cache_ttl_seconds: int = 300

    # Spatial-temporal gating window (seconds)
    spatial_temporal_window_seconds: int = 10

    # New session threshold: if person's last session ended > N hours ago, start new session
    new_session_threshold_hours: int = 4

    consumer_group: str = "reid-workers"
    consumer_name: str = "reid-0"
    block_ms: int = 500


def build_config(settings) -> ReidConfig:
    return ReidConfig(
        camera_ids=settings.camera_id_list,
        redis_url=settings.redis_url,
        database_url=settings.database_url,
        reid_similarity_threshold=float(
            os.environ.get("REID_SIMILARITY_THRESHOLD", "0.75")
        ),
        face_similarity_threshold=float(
            os.environ.get("REID_FACE_THRESHOLD", "0.85")
        ),
        consumer_name=os.environ.get("REID_CONSUMER_NAME", "reid-0"),
    )
