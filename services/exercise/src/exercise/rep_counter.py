"""Per-track rep counting state machine.

State: UP → DOWN → UP = 1 rep.
Uses a median-filtered angle signal to avoid noise-induced false counts.
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from gym_shared.events.schemas import RepCountedEvent
from gym_shared.logging import get_logger

from exercise.exercise_registry import ExerciseDefinition
from exercise.keypoint_utils import smooth_signal

log = get_logger(__name__)

_ANGLE_HISTORY = 7     # frames of history for median filter
_PHASE_LOCK = 3        # frames an angle must stay in a zone before phase change


class Phase(str, Enum):
    UNKNOWN = "unknown"
    UP = "up"
    DOWN = "down"


@dataclass
class TrackState:
    exercise_type: str
    set_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rep_count: int = 0
    phase: Phase = Phase.UNKNOWN
    angle_history: deque = field(default_factory=lambda: deque(maxlen=_ANGLE_HISTORY))
    phase_frame_count: int = 0   # consecutive frames in candidate phase
    last_seen_at: float = field(default_factory=time.monotonic)


class RepCounter:
    """Counts reps for multiple tracks simultaneously.

    One TrackState per track_id is maintained internally.
    Call update() on every frame for each tracked person.
    """

    def __init__(
        self,
        exercise_def: ExerciseDefinition,
        set_idle_timeout_s: float = 60.0,
    ) -> None:
        self._def = exercise_def
        self._idle_timeout = set_idle_timeout_s
        self._tracks: dict[int, TrackState] = {}

    def update(
        self,
        track_id: int,
        angle: float | None,
        timestamp_ns: int,
    ) -> RepCountedEvent | None:
        """Process one frame for a track. Returns a RepCountedEvent if a rep completed.

        Args:
            track_id: ByteTrack local track ID.
            angle: Primary joint angle (degrees), or None if keypoints invisible.
            timestamp_ns: Frame timestamp in nanoseconds.
        """
        now = time.monotonic()

        state = self._get_or_create(track_id)
        state.last_seen_at = now

        if angle is None:
            return None

        state.angle_history.append(angle)
        smoothed = smooth_signal(state.angle_history)

        up_thresh = self._def.up_angle
        down_thresh = self._def.down_angle

        # Determine candidate phase from smoothed angle
        # For exercises where "up" > "down" (squat, push-up):
        if up_thresh > down_thresh:
            in_up = smoothed >= up_thresh
            in_down = smoothed <= down_thresh
        else:
            # For bicep curl, lateral raise: "up" < "down"
            in_up = smoothed <= up_thresh
            in_down = smoothed >= down_thresh

        candidate = None
        if in_up:
            candidate = Phase.UP
        elif in_down:
            candidate = Phase.DOWN

        if candidate is None or candidate == state.phase:
            state.phase_frame_count = 0
            return None

        # Require _PHASE_LOCK consecutive frames in new zone before committing
        if candidate != state.phase:
            state.phase_frame_count += 1
            if state.phase_frame_count < _PHASE_LOCK:
                return None

        # Phase transition confirmed
        prev_phase = state.phase
        state.phase = candidate
        state.phase_frame_count = 0

        # Rep counted on DOWN → UP transition
        if prev_phase == Phase.DOWN and candidate == Phase.UP:
            state.rep_count += 1
            rep_number = state.rep_count
            log.debug(
                "rep_counted",
                track_id=track_id,
                exercise=self._def.name,
                rep=rep_number,
                angle=round(smoothed, 1),
            )
            return RepCountedEvent(
                camera_id="",  # filled in by caller who knows camera_id
                track_id=track_id,
                exercise_set_id=state.set_id,
                exercise_type=self._def.name,
                rep_number=rep_number,
                rep_count=rep_number,
                duration_ms=0,  # TODO: track rep start time
                phase=candidate.value,
                timestamp_ns=timestamp_ns,
            )
        return None

    def _get_or_create(self, track_id: int) -> TrackState:
        now = time.monotonic()
        if track_id in self._tracks:
            state = self._tracks[track_id]
            # Reset set if track was idle too long (person left and came back)
            if now - state.last_seen_at > self._idle_timeout:
                log.info(
                    "new_set_started",
                    track_id=track_id,
                    reason="idle_timeout",
                    prev_reps=state.rep_count,
                )
                self._tracks[track_id] = TrackState(exercise_type=self._def.name)
        else:
            self._tracks[track_id] = TrackState(exercise_type=self._def.name)
        return self._tracks[track_id]

    def get_set_id(self, track_id: int) -> str:
        return self._get_or_create(track_id).set_id

    def get_rep_count(self, track_id: int) -> int:
        return self._tracks.get(track_id, TrackState(exercise_type=self._def.name)).rep_count
