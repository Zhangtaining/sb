"""Pydantic v2 event schemas for all Redis Streams messages.

Stream naming convention: {domain}:{camera_id}
  frames:cam-01         — raw compressed frames from ingestion
  perceptions:cam-01    — enriched detections from perception
  rep_counted           — rep completion events from exercise service
  form_alerts           — form issue events from exercise service
  guidance              — LLM guidance messages from guidance service
  identity_resolved     — ReID match results from reid service (Phase 2)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


# ── Ingestion → Perception ────────────────────────────────────────────────────

class FrameMessage(_FrozenModel):
    """A single compressed video frame published by the ingestion service.

    Stream: frames:{camera_id}
    """

    camera_id: str
    timestamp_ns: int = Field(description="Monotonic nanosecond timestamp")
    frame_seq: int = Field(description="Monotonically increasing frame counter per camera")
    jpeg_b64: str = Field(description="Base64-encoded JPEG bytes")
    width: int
    height: int


# ── Perception → Exercise / ReID ──────────────────────────────────────────────

class Keypoint(_FrozenModel):
    """Single body keypoint (YOLO 17-point or MediaPipe 33-point convention)."""

    x: float = Field(description="Normalized [0,1] horizontal coordinate")
    y: float = Field(description="Normalized [0,1] vertical coordinate")
    z: float = Field(default=0.0, description="Depth estimate (0 if not available)")
    visibility: float = Field(description="Confidence score [0,1]")


class BoundingBox(_FrozenModel):
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


class PerceptionEvent(_FrozenModel):
    """Enriched detection for one tracked person in one frame.

    Stream: perceptions:{camera_id}
    Published once per tracked person per processed frame.
    """

    camera_id: str
    timestamp_ns: int
    frame_seq: int
    track_id: int = Field(description="ByteTrack local integer track ID within this camera")
    bbox: BoundingBox
    keypoints: list[Keypoint] = Field(description="17 keypoints (YOLO pose convention)")
    reid_embedding: list[float] = Field(
        description="OSNet 256-d L2-normalized ReID feature vector"
    )


# ── Exercise → Guidance / API ─────────────────────────────────────────────────

class RepCountedEvent(_FrozenModel):
    """Fired each time a rep is completed for a tracked person.

    Stream: rep_counted
    """

    camera_id: str
    track_id: int
    exercise_set_id: str = Field(description="UUID of the current ExerciseSet")
    exercise_type: str
    rep_number: int = Field(description="1-based rep index within the current set")
    rep_count: int = Field(description="Total reps in the current set so far")
    duration_ms: int = Field(description="Time to complete this rep in milliseconds")
    phase: str = Field(description="'concentric' or 'eccentric'")
    timestamp_ns: int


class FormAlertEvent(_FrozenModel):
    """Fired when a form issue is detected and has persisted for 3+ frames.

    Stream: form_alerts
    """

    camera_id: str
    track_id: int
    exercise_set_id: str
    exercise_type: str
    rep_count: int
    alert_key: str = Field(description="Stable identifier for this alert type, e.g. 'knee_cave'")
    alert_message: str = Field(description="Human-readable description of the form issue")
    severity: str = Field(default="warning", description="'info' | 'warning' | 'critical'")
    joint_angles: dict[str, float] = Field(
        default_factory=dict,
        description="Relevant joint angle values at time of alert",
    )
    timestamp_ns: int


# ── Guidance → API / Mobile ───────────────────────────────────────────────────

class GuidanceMessage(_FrozenModel):
    """LLM-generated coaching message for a specific tracked person.

    Stream: guidance
    """

    camera_id: str
    track_id: int
    person_id: str | None = Field(
        default=None,
        description="UUID of the registered Person if identity resolved, else None",
    )
    message: str = Field(description="1-2 sentence coaching guidance text")
    trigger_type: str = Field(
        description="'form_alert' | 'rep_milestone' | 'set_complete' | 'encouragement'"
    )
    exercise_type: str | None = None
    timestamp_ns: int
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── ReID → Exercise / Guidance (Phase 2) ─────────────────────────────────────

class IdentityResolvedEvent(_FrozenModel):
    """Published when a track is linked to a registered Person.

    Stream: identity_resolved
    """

    camera_id: str
    track_id: int
    person_id: str = Field(description="UUID of the matched Person")
    confidence: float = Field(description="Match confidence [0,1]")
    method: str = Field(description="'face' | 'reid' | 'qr'")
    timestamp_ns: int
