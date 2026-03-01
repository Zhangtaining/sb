"""Ingestion service entry point."""
from __future__ import annotations

import asyncio
import queue
import signal
import threading

from gym_shared.logging import configure_logging, get_logger
from gym_shared.settings import settings

from ingestion.camera_reader import CameraReader
from ingestion.config import build_config
from ingestion.frame_publisher import FramePublisher

log = get_logger(__name__)


async def run() -> None:
    configure_logging(settings.log_format, settings.log_level)
    config = build_config(settings)

    log.info("ingestion_service_starting", cameras=[c.camera_id for c in config.cameras])

    readers: list[CameraReader] = []
    publishers: list[FramePublisher] = []
    threads: list[threading.Thread] = []

    stop_event = threading.Event()

    def _handle_signal(sig, frame):
        log.info("shutdown_signal_received", signal=sig)
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    for cam_cfg in config.cameras:
        frame_queue: queue.Queue = queue.Queue(maxsize=cam_cfg.frame_buffer_size)

        reader = CameraReader(cam_cfg, frame_queue, stop_event)
        publisher = FramePublisher(cam_cfg, frame_queue, config.redis_url, stop_event)

        readers.append(reader)
        publishers.append(publisher)

        reader_thread = threading.Thread(
            target=reader.run, name=f"reader-{cam_cfg.camera_id}", daemon=True
        )
        publisher_thread = threading.Thread(
            target=asyncio.run,
            args=(publisher.run(),),
            name=f"publisher-{cam_cfg.camera_id}",
            daemon=True,
        )

        threads.append(reader_thread)
        threads.append(publisher_thread)
        reader_thread.start()
        publisher_thread.start()

    log.info("ingestion_service_running", thread_count=len(threads))

    # Block until shutdown signal
    while not stop_event.is_set():
        await asyncio.sleep(1)

    log.info("ingestion_service_stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
