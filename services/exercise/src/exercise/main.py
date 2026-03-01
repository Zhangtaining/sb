"""Exercise service entry point."""
from __future__ import annotations

import asyncio
import signal

import redis.asyncio as aioredis

from gym_shared.logging import configure_logging, get_logger
from gym_shared.settings import settings

from exercise.config import build_config
from exercise.exercise_registry import ExerciseRegistry
from exercise.pipeline import ExercisePipeline

log = get_logger(__name__)


async def run() -> None:
    configure_logging(settings.log_format, settings.log_level)
    config = build_config(settings)

    registry = ExerciseRegistry(config.exercises_yaml)

    log.info(
        "exercise_service_starting",
        cameras=config.camera_ids,
        exercises=registry.list_exercises(),
    )

    redis = aioredis.from_url(config.redis_url, decode_responses=False)

    pipelines = [
        ExercisePipeline(cam_id, config, registry)
        for cam_id in config.camera_ids
    ]

    loop = asyncio.get_running_loop()

    def _shutdown(sig, frame):
        log.info("shutdown_signal_received", signal=sig)
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        await asyncio.gather(*[p.run(redis) for p in pipelines])
    except asyncio.CancelledError:
        pass
    finally:
        await redis.aclose()
        log.info("exercise_service_stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
