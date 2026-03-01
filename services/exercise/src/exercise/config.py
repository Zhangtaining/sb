"""Exercise service configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ExerciseConfig:
    camera_ids: list[str] = field(default_factory=list)
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://gym:gympass@localhost:5432/gymdb"

    exercises_yaml: str = str(
        Path(__file__).parent.parent.parent / "data" / "exercises.yaml"
    )

    consumer_group: str = "exercise-workers"
    consumer_name: str = "exercise-0"
    read_batch: int = 10
    block_ms: int = 500

    # Rep counter: time (seconds) of inactivity before a set is closed
    set_idle_timeout_s: float = 60.0


def build_config(settings) -> ExerciseConfig:
    consumer_name = os.environ.get("EXERCISE_CONSUMER_NAME", "exercise-0")
    return ExerciseConfig(
        camera_ids=settings.camera_id_list,
        redis_url=settings.redis_url,
        database_url=settings.database_url,
        consumer_name=consumer_name,
    )
