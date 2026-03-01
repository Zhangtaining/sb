"""Heuristic exercise classifier (Phase 1).

Identifies the exercise type by measuring which joint group shows the
most angle variance over a rolling window of frames.

Will be replaced by an ONNX TCN model in Phase 3.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from exercise.exercise_registry import ExerciseRegistry
from exercise.keypoint_utils import get_joint_angle
from gym_shared.events.schemas import Keypoint
from gym_shared.logging import get_logger

log = get_logger(__name__)

_WINDOW = 30          # frames of history per track
_MIN_VARIANCE = 5.0   # minimum angle std-dev to consider a joint "active"
_MIN_CONFIDENCE = 0.5


# Joint triples that distinguish each exercise (uses primary_joint from YAML)
# Keyed to exercise names — must match exercises.yaml
_EXERCISE_JOINTS: dict[str, tuple[int, int, int]] = {
    "squat":         (11, 13, 15),   # hip-knee-ankle
    "push_up":       (5, 7, 9),      # shoulder-elbow-wrist
    "bicep_curl":    (5, 7, 9),      # shoulder-elbow-wrist (same joints, different range)
    "lateral_raise": (11, 5, 7),     # hip-shoulder-elbow
}

# Additional discriminating joints to tell apart exercises that share primary joints
_DISCRIMINATOR_JOINTS: dict[str, tuple[int, int, int]] = {
    "squat":         (12, 14, 16),   # right hip-knee-ankle (confirm lower body)
    "push_up":       (5, 11, 15),    # shoulder-hip-ankle (body plank angle)
    "bicep_curl":    (11, 7, 9),     # hip-elbow-wrist (elbow position relative to hip)
    "lateral_raise": (11, 5, 7),     # same as primary, lower range
}


class HeuristicClassifier:
    """Classifies exercise type from a rolling window of keypoint frames.

    One classifier per track; maintains its own history.
    """

    def __init__(self, registry: ExerciseRegistry) -> None:
        self._registry = registry
        # track_id → exercise_name → deque of angles
        self._histories: dict[int, dict[str, deque]] = {}

    def update(
        self,
        track_id: int,
        keypoints: list[Keypoint],
    ) -> tuple[str, float]:
        """Update history with a new frame and return current best guess.

        Returns:
            (exercise_name, confidence) where confidence ∈ [0, 1].
            Returns ("unknown", 0.0) when no exercise is dominant.
        """
        if track_id not in self._histories:
            self._histories[track_id] = {
                name: deque(maxlen=_WINDOW)
                for name in self._registry.list_exercises()
            }

        history = self._histories[track_id]

        # Record the primary joint angle for each exercise
        for name, (a, b, c) in _EXERCISE_JOINTS.items():
            angle = get_joint_angle(keypoints, a, b, c)
            if angle is not None:
                history[name].append(angle)

        return self._classify(history)

    def _classify(
        self, history: dict[str, deque]
    ) -> tuple[str, float]:
        variances: dict[str, float] = {}

        for name, angles in history.items():
            if len(angles) < _WINDOW // 2:
                continue  # not enough data yet
            std = float(np.std(list(angles)))
            variances[name] = std

        if not variances:
            return ("unknown", 0.0)

        # Push-up and bicep_curl both use elbow angle — disambiguate via
        # body position (push-up has a near-horizontal torso)
        if "push_up" in variances and "bicep_curl" in variances:
            variances = self._disambiguate_elbow_exercises(variances, history)

        best = max(variances, key=variances.get)
        best_std = variances[best]

        if best_std < _MIN_VARIANCE:
            return ("unknown", 0.0)

        # Confidence: ratio of best std to sum of all stds
        total = sum(variances.values()) or 1.0
        confidence = min(1.0, best_std / total)

        return (best, round(confidence, 2))

    def _disambiguate_elbow_exercises(
        self,
        variances: dict[str, float],
        history: dict[str, deque],
    ) -> dict[str, float]:
        """Use hip-knee angle variance to tell push-up from bicep curl.

        Push-ups have significant lower-body involvement (hip-knee-ankle angle
        stays relatively fixed at ~180°); bicep curls have standing still legs.
        """
        squat_var = variances.get("squat", 0.0)
        # If lower body is active → squat; if not → standing exercise
        # For push-up vs curl: push-up has high shoulder-hip-ankle variance
        # We use the squat joint history as a proxy for lower body involvement
        squat_hist = list(history.get("squat", []))
        if squat_hist:
            lower_body_range = max(squat_hist) - min(squat_hist) if squat_hist else 0
        else:
            lower_body_range = 0

        # If lower body barely moves → likely bicep curl (standing)
        # Push-up body is horizontal → squat joint (hip-knee) at ~180° constant
        if lower_body_range < 20:
            # Could be bicep curl (standing) or push-up (flat body, knee ~180)
            # Prefer bicep curl unless push-up variance is significantly higher
            if variances.get("push_up", 0) > variances.get("bicep_curl", 0) * 1.5:
                variances["bicep_curl"] = 0.0
            else:
                variances["push_up"] = 0.0
        return variances
