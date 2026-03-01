"""YOLOv11-pose person detector with integrated ByteTrack tracking.

Wraps ultralytics YOLO to return structured Detection / TrackedDetection
objects with bounding boxes and 17 normalized keypoints per person.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from ultralytics import YOLO

from gym_shared.events.schemas import BoundingBox, Keypoint
from gym_shared.logging import get_logger

log = get_logger(__name__)

# COCO class index for "person"
_PERSON_CLASS = 0
# Number of keypoints in YOLO pose model (COCO 17-point convention)
_NUM_KEYPOINTS = 17


@dataclass
class Detection:
    """One detected person in a frame (no track ID)."""

    bbox: BoundingBox
    keypoints: list[Keypoint]  # 17 keypoints, coordinates normalized to [0,1]
    confidence: float


@dataclass
class TrackedDetection:
    """A Detection with a stable track ID assigned by ByteTrack."""

    track_id: int
    bbox: BoundingBox
    keypoints: list[Keypoint]
    confidence: float


def _parse_result(result, width: int, height: int) -> list[Detection]:
    """Parse a single YOLO result into Detection objects."""
    detections: list[Detection] = []

    if result.boxes is None or len(result.boxes) == 0:
        return detections

    boxes_xyxy = result.boxes.xyxy.cpu().numpy()
    confidences = result.boxes.conf.cpu().numpy()

    kps_data = None
    if result.keypoints is not None:
        kps_data = result.keypoints.data.cpu().numpy()  # (N, 17, 3) — pixel coords

    for i in range(len(boxes_xyxy)):
        x1, y1, x2, y2 = boxes_xyxy[i]
        bbox = BoundingBox(
            x1=float(x1) / width,
            y1=float(y1) / height,
            x2=float(x2) / width,
            y2=float(y2) / height,
            confidence=float(confidences[i]),
        )
        keypoints = _parse_keypoints(kps_data, i, width, height)
        detections.append(
            Detection(bbox=bbox, keypoints=keypoints, confidence=float(confidences[i]))
        )
    return detections


def _parse_tracked_result(result, width: int, height: int) -> list[TrackedDetection]:
    """Parse a YOLO track() result into TrackedDetection objects."""
    tracked: list[TrackedDetection] = []

    if result.boxes is None or len(result.boxes) == 0:
        return tracked

    boxes_xyxy = result.boxes.xyxy.cpu().numpy()
    confidences = result.boxes.conf.cpu().numpy()
    track_ids = result.boxes.id

    kps_data = None
    if result.keypoints is not None:
        kps_data = result.keypoints.data.cpu().numpy()

    for i in range(len(boxes_xyxy)):
        if track_ids is None:
            track_id = i  # fallback if tracking lost
        else:
            track_id = int(track_ids[i].item())

        x1, y1, x2, y2 = boxes_xyxy[i]
        bbox = BoundingBox(
            x1=float(x1) / width,
            y1=float(y1) / height,
            x2=float(x2) / width,
            y2=float(y2) / height,
            confidence=float(confidences[i]),
        )
        keypoints = _parse_keypoints(kps_data, i, width, height)
        tracked.append(
            TrackedDetection(
                track_id=track_id,
                bbox=bbox,
                keypoints=keypoints,
                confidence=float(confidences[i]),
            )
        )
    return tracked


def _parse_keypoints(
    kps_data: np.ndarray | None, idx: int, width: int, height: int
) -> list[Keypoint]:
    if kps_data is None or idx >= len(kps_data):
        return [Keypoint(x=0.0, y=0.0, visibility=0.0) for _ in range(_NUM_KEYPOINTS)]
    return [
        Keypoint(x=float(kx) / width, y=float(ky) / height, visibility=float(kv))
        for kx, ky, kv in kps_data[idx]
    ]


class Detector:
    """Loads a YOLOv11-pose model; supports detect-only and detect+track modes.

    Args:
        model_name: Model filename/path (e.g. "yolo11n-pose.pt").
            ultralytics auto-downloads if not found locally.
        device: Torch device string ("cpu", "cuda", "mps").
        confidence: Minimum detection confidence threshold.
        iou: NMS IOU threshold.
    """

    def __init__(
        self,
        model_name: str = "yolo11n-pose.pt",
        device: str = "cpu",
        confidence: float = 0.5,
        iou: float = 0.7,
    ) -> None:
        log.info("detector_loading", model=model_name, device=device)
        self._model = YOLO(model_name)
        self._device = device
        self._confidence = confidence
        self._iou = iou
        log.info("detector_ready", model=model_name, device=device)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Run detection + pose on a single RGB frame. No tracking.

        Args:
            frame: HxWx3 uint8 RGB numpy array.
        Returns:
            List of Detection objects per detected person.
        """
        h, w = frame.shape[:2]
        results = self._model.predict(
            frame,
            classes=[_PERSON_CLASS],
            conf=self._confidence,
            iou=self._iou,
            device=self._device,
            verbose=False,
        )
        detections: list[Detection] = []
        for result in results:
            detections.extend(_parse_result(result, w, h))
        return detections

    def track(self, frame: np.ndarray) -> list[TrackedDetection]:
        """Run detection + ByteTrack on a single RGB frame.

        Tracking state is preserved across calls (persist=True).

        Args:
            frame: HxWx3 uint8 RGB numpy array.
        Returns:
            List of TrackedDetection objects with stable track_id.
        """
        h, w = frame.shape[:2]
        results = self._model.track(
            frame,
            classes=[_PERSON_CLASS],
            conf=self._confidence,
            iou=self._iou,
            device=self._device,
            persist=True,   # keep ByteTracker state across calls
            verbose=False,
        )
        tracked: list[TrackedDetection] = []
        for result in results:
            tracked.extend(_parse_tracked_result(result, w, h))
        return tracked
