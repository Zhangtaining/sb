"""Perception pipeline: consume frames → detect → track → publish.

For each camera:
1. XREADGROUP from `frames:{camera_id}` (consumer group: perception-workers)
2. Decode FrameMessage → numpy array
3. Run Detector → Tracker → ReIDExtractor
4. Publish one PerceptionEvent per tracked person to `perceptions:{camera_id}`
5. XACK the processed message
"""
from __future__ import annotations

import asyncio
import base64
import time
from io import BytesIO

import cv2
import numpy as np
from PIL import Image

import redis.asyncio as aioredis

from gym_shared.events.publisher import (
    GROUP_PERCEPTION,
    ack,
    ensure_consumer_group,
    frames_stream,
    perceptions_stream,
    publish,
    read_group,
)
from gym_shared.events.schemas import FrameMessage, PerceptionEvent
from gym_shared.logging import get_logger

from perception.config import PerceptionConfig
from perception.detector import Detector
from perception.reid_extractor import ReIDExtractor

log = get_logger(__name__)


def _decode_frame(msg_data: dict) -> tuple[np.ndarray, FrameMessage]:
    """Parse a Redis Stream message dict into a numpy frame + FrameMessage."""
    raw_json = msg_data.get("data", "")
    event = FrameMessage.model_validate_json(raw_json)
    jpeg_bytes = base64.b64decode(event.jpeg_b64)
    img = Image.open(BytesIO(jpeg_bytes)).convert("RGB")
    frame = np.array(img)
    return frame, event


class PerceptionPipeline:
    """Runs the full perception pipeline for a single camera.

    Args:
        camera_id: Camera identifier (used for stream names).
        config: Perception configuration.
        detector: Shared YOLO detector instance.
        reid: Shared ReID extractor instance.
    """

    def __init__(
        self,
        camera_id: str,
        config: PerceptionConfig,
        detector: Detector,
        reid: ReIDExtractor,
    ) -> None:
        self._camera_id = camera_id
        self._cfg = config
        self._detector = detector
        self._reid = reid
        self._in_stream = frames_stream(camera_id)
        self._out_stream = perceptions_stream(camera_id)
        self._frame_count = 0
        self._t_start = time.monotonic()

    async def run(self, redis: aioredis.Redis) -> None:
        """Main loop — processes frames until cancelled."""
        await ensure_consumer_group(redis, self._in_stream, GROUP_PERCEPTION)

        log.info(
            "pipeline_starting",
            camera_id=self._camera_id,
            device=self._cfg.device,
            in_stream=self._in_stream,
            out_stream=self._out_stream,
        )

        while True:
            messages = await read_group(
                redis,
                self._in_stream,
                GROUP_PERCEPTION,
                self._cfg.consumer_name,
                count=self._cfg.read_batch,
                block_ms=self._cfg.block_ms,
            )

            for msg_id, msg_data in messages:
                try:
                    await self._process_message(redis, msg_id, msg_data)
                except Exception as exc:
                    log.error(
                        "pipeline_frame_error",
                        camera_id=self._camera_id,
                        msg_id=msg_id,
                        error=str(exc),
                    )
                    # Still ACK to avoid re-processing corrupted frames
                    await ack(redis, self._in_stream, GROUP_PERCEPTION, msg_id)

    async def _process_message(
        self, redis: aioredis.Redis, msg_id: str, msg_data: dict
    ) -> None:
        loop = asyncio.get_running_loop()

        # Decode in executor to avoid blocking the event loop
        frame, event = await loop.run_in_executor(None, _decode_frame, msg_data)

        # Run CPU-heavy inference in executor
        tracked = await loop.run_in_executor(
            None, self._detector.track, frame
        )

        # Publish one event per tracked person
        for td in tracked:
            # Extract ReID embedding from person crop
            h, w = frame.shape[:2]
            x1 = int(td.bbox.x1 * w)
            y1 = int(td.bbox.y1 * h)
            x2 = int(td.bbox.x2 * w)
            y2 = int(td.bbox.y2 * h)
            crop = frame[max(0, y1):y2, max(0, x1):x2]

            embedding = await loop.run_in_executor(
                None, self._reid.extract, crop if crop.size > 0 else frame
            )

            perception_event = PerceptionEvent(
                camera_id=self._camera_id,
                timestamp_ns=event.timestamp_ns,
                frame_seq=event.frame_seq,
                track_id=td.track_id,
                bbox=td.bbox,
                keypoints=td.keypoints,
                reid_embedding=embedding.tolist(),
            )
            await publish(redis, self._out_stream, perception_event)

        await ack(redis, self._in_stream, GROUP_PERCEPTION, msg_id)

        self._frame_count += 1
        if self._frame_count % self._cfg.log_interval == 0:
            elapsed = time.monotonic() - self._t_start
            fps = self._frame_count / elapsed if elapsed > 0 else 0
            log.info(
                "pipeline_throughput",
                camera_id=self._camera_id,
                frames=self._frame_count,
                fps=round(fps, 1),
                persons_this_frame=len(tracked),
            )

