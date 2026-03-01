"""Perception service entry point."""
from __future__ import annotations

import asyncio
import signal

import redis.asyncio as aioredis

from gym_shared.logging import configure_logging, get_logger
from gym_shared.settings import settings

from perception.config import build_config
from perception.detector import Detector
from perception.pipeline import PerceptionPipeline
from perception.reid_extractor import ReIDExtractor

log = get_logger(__name__)


async def run() -> None:
    configure_logging(settings.log_format, settings.log_level)
    config = build_config(settings)

    log.info(
        "perception_service_starting",
        cameras=config.camera_ids,
        device=config.device,
        model=config.yolo_model,
    )

    # Load models once — shared across all camera pipelines
    detector = Detector(
        model_name=config.yolo_model,
        device=config.device,
        confidence=config.yolo_confidence,
        iou=config.yolo_iou,
    )
    reid = ReIDExtractor(device=config.device)

    redis = aioredis.from_url(config.redis_url, decode_responses=False)

    # Create one pipeline per camera; run them concurrently
    pipelines = [
        PerceptionPipeline(cam_id, config, detector, reid)
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
        log.info("perception_service_stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
