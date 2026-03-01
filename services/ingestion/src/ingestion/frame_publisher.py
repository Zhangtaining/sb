"""Frame publisher — reads from the CameraReader queue and XADDs to Redis Streams."""
from __future__ import annotations

import asyncio
import base64
import queue
import threading

import redis.asyncio as aioredis

from gym_shared.events.publisher import frames_stream, publish
from gym_shared.events.schemas import FrameMessage
from gym_shared.logging import get_logger

from ingestion.camera_reader import RawFrame
from ingestion.config import CameraConfig

log = get_logger(__name__)


class FramePublisher:
    """Async publisher that drains a RawFrame queue into a Redis Stream.

    Args:
        config: Per-camera configuration.
        frame_queue: Queue populated by CameraReader.
        redis_url: Redis connection URL.
        stop_event: Set this to request a graceful shutdown.
    """

    def __init__(
        self,
        config: CameraConfig,
        frame_queue: queue.Queue,
        redis_url: str,
        stop_event: threading.Event,
    ) -> None:
        self._cfg = config
        self._queue = frame_queue
        self._redis_url = redis_url
        self._stop = stop_event
        self._stream = frames_stream(config.camera_id)

    async def run(self) -> None:
        """Main async loop — publishes frames until stop_event is set."""
        redis = aioredis.from_url(self._redis_url, decode_responses=False)

        log.info(
            "frame_publisher_starting",
            camera_id=self._cfg.camera_id,
            stream=self._stream,
        )

        try:
            while not self._stop.is_set():
                raw = await self._dequeue()
                if raw is None:
                    continue

                event = FrameMessage(
                    camera_id=raw.camera_id,
                    timestamp_ns=raw.timestamp_ns,
                    frame_seq=raw.frame_seq,
                    jpeg_b64=base64.b64encode(raw.jpeg_bytes).decode("ascii"),
                    width=raw.width,
                    height=raw.height,
                )

                try:
                    msg_id = await publish(redis, self._stream, event, maxlen=100)
                    log.debug(
                        "frame_published",
                        camera_id=self._cfg.camera_id,
                        frame_seq=raw.frame_seq,
                        msg_id=msg_id,
                    )
                except Exception as exc:
                    log.error(
                        "frame_publish_error",
                        camera_id=self._cfg.camera_id,
                        error=str(exc),
                    )
        finally:
            await redis.aclose()
            log.info("frame_publisher_stopped", camera_id=self._cfg.camera_id)

    async def _dequeue(self) -> RawFrame | None:
        """Non-blocking queue drain with a short async sleep to yield the event loop."""
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(
                None, lambda: self._queue.get(timeout=0.1)
            )
        except queue.Empty:
            return None
