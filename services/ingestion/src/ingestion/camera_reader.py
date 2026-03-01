"""RTSP camera reader — one thread per camera.

Reads frames from an RTSP stream (or local video file) via PyAV,
downsamples to the configured FPS, compresses to JPEG via OpenCV,
and pushes raw bytes + metadata into an in-memory queue for the
FramePublisher.
"""
from __future__ import annotations

import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque

import av
import cv2
import numpy as np

from gym_shared.logging import get_logger

from ingestion.config import CameraConfig

log = get_logger(__name__)

# Exponential backoff parameters for stream reconnection
_BACKOFF_BASE = 1.0
_BACKOFF_MAX = 30.0


@dataclass
class RawFrame:
    """A single JPEG-compressed frame ready for publishing."""

    camera_id: str
    timestamp_ns: int
    frame_seq: int
    jpeg_bytes: bytes
    width: int
    height: int


def _is_rtsp(url: str) -> bool:
    return url.lower().startswith("rtsp://") or url.lower().startswith("rtsps://")


class CameraReader:
    """Reads frames from a single camera and enqueues them.

    Also maintains a rolling deque (``frame_buffer``) of the last
    ``frame_buffer_size`` raw frames — used by the video clip worker.

    Args:
        config: Per-camera configuration.
        frame_queue: Shared queue consumed by FramePublisher.
        stop_event: Set this to request a graceful shutdown.
    """

    def __init__(
        self,
        config: CameraConfig,
        frame_queue: queue.Queue,
        stop_event: threading.Event,
    ) -> None:
        self._cfg = config
        self._queue = frame_queue
        self._stop = stop_event
        self._frame_seq = 0
        # Rolling buffer for clip generation (T39)
        self.frame_buffer: Deque[RawFrame] = deque(maxlen=config.frame_buffer_size)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main loop — reconnects on failure until stop_event is set."""
        backoff = _BACKOFF_BASE
        while not self._stop.is_set():
            try:
                self._stream_loop()
                backoff = _BACKOFF_BASE  # reset on clean exit
            except Exception as exc:
                if self._stop.is_set():
                    break
                log.warning(
                    "camera_reader_error",
                    camera_id=self._cfg.camera_id,
                    error=str(exc),
                    retry_in=backoff,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, _BACKOFF_MAX)

        log.info("camera_reader_stopped", camera_id=self._cfg.camera_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _stream_loop(self) -> None:
        """Open the stream and read frames until stopped or an error occurs."""
        log.info(
            "camera_reader_connecting",
            camera_id=self._cfg.camera_id,
            url=self._cfg.rtsp_url,
        )

        # Only apply RTSP-specific options for real RTSP streams
        options = {}
        if _is_rtsp(self._cfg.rtsp_url):
            options = {
                "rtsp_transport": "tcp",
                "fflags": "nobuffer",
                "flags": "low_delay",
            }

        container = av.open(self._cfg.rtsp_url, options=options)

        try:
            video_stream = container.streams.video[0]
            video_stream.thread_type = "AUTO"

            src_fps = float(video_stream.average_rate or self._cfg.fps)
            frame_step = max(1, round(src_fps / self._cfg.fps))

            log.info(
                "camera_reader_connected",
                camera_id=self._cfg.camera_id,
                src_fps=src_fps,
                frame_step=frame_step,
                target_fps=self._cfg.fps,
            )

            raw_frame_idx = 0
            for packet in container.demux(video_stream):
                if self._stop.is_set():
                    break
                for frame in packet.decode():
                    if self._stop.is_set():
                        break
                    raw_frame_idx += 1
                    if raw_frame_idx % frame_step != 0:
                        continue
                    self._process_frame(frame)
        finally:
            container.close()

    def _process_frame(self, av_frame: av.VideoFrame) -> None:
        """Compress frame to JPEG and push to queue + rolling buffer."""
        img: np.ndarray = av_frame.to_ndarray(format="rgb24")
        height, width = img.shape[:2]

        jpeg_bytes = _encode_jpeg(img, self._cfg.jpeg_quality)

        raw = RawFrame(
            camera_id=self._cfg.camera_id,
            timestamp_ns=time.monotonic_ns(),
            frame_seq=self._frame_seq,
            jpeg_bytes=jpeg_bytes,
            width=width,
            height=height,
        )
        self._frame_seq += 1

        self.frame_buffer.append(raw)

        try:
            self._queue.put_nowait(raw)
        except queue.Full:
            # Drop the oldest item and retry once — publisher is lagging
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(raw)
            except queue.Full:
                pass  # Still full — drop this frame


def _encode_jpeg(img: np.ndarray, quality: int = 85) -> bytes:
    """Encode an RGB numpy array to JPEG bytes using OpenCV."""
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    success, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise RuntimeError("JPEG encoding failed")
    return bytes(buf)
