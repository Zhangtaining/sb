"""Unit tests for CameraReader — uses a local video file or synthetic frames."""
from __future__ import annotations

import queue
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from ingestion.camera_reader import CameraReader, RawFrame
from ingestion.config import CameraConfig


@pytest.fixture()
def cam_cfg() -> CameraConfig:
    return CameraConfig(
        camera_id="cam-test",
        rtsp_url="test.mp4",
        fps=15,
        jpeg_quality=85,
        frame_buffer_size=30,
    )


def test_rawframe_dataclass(cam_cfg):
    raw = RawFrame(
        camera_id="cam-test",
        timestamp_ns=12345,
        frame_seq=0,
        jpeg_bytes=b"\xff\xd8\xff",
        width=640,
        height=480,
    )
    assert raw.camera_id == "cam-test"
    assert raw.frame_seq == 0


def test_reader_enqueues_frames_from_local_file(cam_cfg, tmp_path):
    """Smoke test: open a tiny synthetic video via PyAV and verify frames arrive."""
    import av
    import numpy as np

    # Create a small MP4 with 30 frames (2 seconds at 15 FPS)
    video_path = str(tmp_path / "test.mp4")
    output = av.open(video_path, mode="w")
    stream = output.add_stream("libx264", rate=15)
    stream.width = 64
    stream.height = 64
    stream.pix_fmt = "yuv420p"
    stream.options = {"crf": "23", "preset": "ultrafast"}

    for i in range(30):
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        img[:, :, i % 3] = 128  # vary color per frame
        frame = av.VideoFrame.from_ndarray(img, format="rgb24")
        frame = frame.reformat(format="yuv420p")
        for packet in stream.encode(frame):
            output.mux(packet)
    for packet in stream.encode():
        output.mux(packet)
    output.close()

    frame_queue: queue.Queue = queue.Queue(maxsize=50)
    stop_event = threading.Event()
    cfg = CameraConfig(
        camera_id="cam-test",
        rtsp_url=video_path,
        fps=15,
        jpeg_quality=85,
        frame_buffer_size=30,
    )
    reader = CameraReader(cfg, frame_queue, stop_event)

    thread = threading.Thread(target=reader.run, daemon=True)
    thread.start()
    thread.join(timeout=5)
    stop_event.set()

    # Should have received frames
    assert not frame_queue.empty(), "No frames were enqueued"
    raw = frame_queue.get_nowait()
    assert isinstance(raw, RawFrame)
    assert raw.camera_id == "cam-test"
    assert len(raw.jpeg_bytes) > 0


def test_reader_reconnects_on_error(cam_cfg):
    """Verify that _stream_loop errors trigger reconnection."""
    frame_queue: queue.Queue = queue.Queue(maxsize=10)
    stop_event = threading.Event()

    reader = CameraReader(cam_cfg, frame_queue, stop_event)
    call_count = 0

    def fake_stream_loop():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("simulated drop")
        # On 3rd call, stop cleanly
        stop_event.set()

    reader._stream_loop = fake_stream_loop

    thread = threading.Thread(target=reader.run, daemon=True)
    thread.start()
    thread.join(timeout=10)

    assert call_count == 3, f"Expected 3 calls, got {call_count}"
