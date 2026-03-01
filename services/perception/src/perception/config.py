"""Perception service configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PerceptionConfig:
    """Configuration for the perception pipeline."""

    camera_ids: list[str] = field(default_factory=list)
    redis_url: str = "redis://localhost:6379/0"

    # Model settings
    yolo_model: str = "yolo11n-pose.pt"
    device: str = "cpu"  # "cpu", "cuda", "mps"
    yolo_confidence: float = 0.5
    yolo_iou: float = 0.7

    # Stream settings
    consumer_group: str = "perception-workers"
    consumer_name: str = "perception-0"
    read_batch: int = 4
    block_ms: int = 500

    # Throughput logging interval (frames)
    log_interval: int = 100


def build_config(settings) -> PerceptionConfig:
    """Build PerceptionConfig from shared Settings."""
    import torch

    # Auto-detect best available device
    if os.environ.get("PERCEPTION_DEVICE"):
        device = os.environ["PERCEPTION_DEVICE"]
    elif torch.cuda.is_available():
        device = "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"

    consumer_name = os.environ.get("PERCEPTION_CONSUMER_NAME", "perception-0")

    return PerceptionConfig(
        camera_ids=settings.camera_id_list,
        redis_url=settings.redis_url,
        yolo_model=settings.yolo_model,
        device=device,
        consumer_name=consumer_name,
    )
