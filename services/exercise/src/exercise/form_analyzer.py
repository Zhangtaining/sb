"""Form analyzer — checks joint angles against thresholds and emits FormAlertEvents.

Debouncing: an alert must persist for 3+ consecutive frames before firing,
and the same alert_key won't fire again within 10 seconds for the same track.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from gym_shared.events.schemas import FormAlertEvent
from gym_shared.logging import get_logger

from exercise.exercise_registry import ExerciseDefinition, FormCheck
from exercise.keypoint_utils import get_joint_angle
from gym_shared.events.schemas import Keypoint

log = get_logger(__name__)

_DEBOUNCE_FRAMES = 3       # consecutive frames out of range before alert fires
_COOLDOWN_SECONDS = 10.0   # minimum seconds between repeat alerts of the same type


@dataclass
class AlertState:
    consecutive_frames: int = 0
    last_fired_at: float = 0.0


class FormAnalyzer:
    """Checks per-track joint angles against exercise form criteria.

    One FormAnalyzer per exercise type; handles multiple tracks internally.
    """

    def __init__(self, exercise_def: ExerciseDefinition) -> None:
        self._def = exercise_def
        # track_id → alert_key → AlertState
        self._states: dict[int, dict[str, AlertState]] = defaultdict(
            lambda: defaultdict(AlertState)
        )

    def check(
        self,
        track_id: int,
        keypoints: list[Keypoint],
        exercise_set_id: str,
        rep_count: int,
        timestamp_ns: int,
    ) -> list[FormAlertEvent]:
        """Evaluate all form checks for a track and return any triggered alerts."""
        alerts: list[FormAlertEvent] = []
        now = time.monotonic()
        joint_angles: dict[str, float] = {}

        for check in self._def.form_checks:
            a, b, c = check.joint
            angle = get_joint_angle(keypoints, a, b, c)
            if angle is None:
                # Reset counter — can't evaluate without visible keypoints
                self._states[track_id][check.alert_key].consecutive_frames = 0
                continue

            key = f"{a}-{b}-{c}"
            joint_angles[key] = angle

            out_of_range = not (check.min_angle <= angle <= check.max_angle)
            state = self._states[track_id][check.alert_key]

            if out_of_range:
                state.consecutive_frames += 1
            else:
                state.consecutive_frames = 0
                continue

            # Must persist for DEBOUNCE_FRAMES consecutive frames
            if state.consecutive_frames < _DEBOUNCE_FRAMES:
                continue

            # Cooldown: don't re-fire within COOLDOWN_SECONDS
            if now - state.last_fired_at < _COOLDOWN_SECONDS:
                continue

            state.last_fired_at = now
            log.debug(
                "form_alert_fired",
                track_id=track_id,
                alert_key=check.alert_key,
                angle=round(angle, 1),
                check_range=[check.min_angle, check.max_angle],
            )
            alerts.append(
                FormAlertEvent(
                    camera_id="",  # filled in by caller
                    track_id=track_id,
                    exercise_set_id=exercise_set_id,
                    exercise_type=self._def.name,
                    rep_count=rep_count,
                    alert_key=check.alert_key,
                    alert_message=check.alert_message,
                    severity=check.severity,
                    joint_angles={k: round(v, 1) for k, v in joint_angles.items()},
                    timestamp_ns=timestamp_ns,
                )
            )

        return alerts
