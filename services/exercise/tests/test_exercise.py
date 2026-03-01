"""Unit tests for exercise service modules."""
from __future__ import annotations

import math
from collections import deque
from pathlib import Path

import pytest

from exercise.exercise_registry import ExerciseRegistry
from exercise.keypoint_utils import compute_angle, smooth_signal, get_joint_angle
from exercise.rep_counter import RepCounter, Phase
from exercise.form_analyzer import FormAnalyzer
from gym_shared.events.schemas import Keypoint

_YAML = Path(__file__).parent.parent / "data" / "exercises.yaml"


# ── Registry ──────────────────────────────────────────────────────────────────

def test_registry_loads_all_exercises():
    registry = ExerciseRegistry(_YAML)
    exercises = registry.list_exercises()
    assert set(exercises) == {"squat", "push_up", "bicep_curl", "lateral_raise"}


def test_registry_get_known_exercise():
    registry = ExerciseRegistry(_YAML)
    squat = registry.get_exercise("squat")
    assert squat.name == "squat"
    assert squat.up_angle == 160
    assert squat.down_angle == 100
    assert len(squat.form_checks) >= 2


def test_registry_unknown_raises():
    registry = ExerciseRegistry(_YAML)
    with pytest.raises(KeyError, match="unknown_exercise"):
        registry.get_exercise("unknown_exercise")


# ── Keypoint utils ────────────────────────────────────────────────────────────

def test_compute_angle_90_degrees():
    # L-shape: (1,0)–(0,0)–(0,1) → 90°
    assert abs(compute_angle((1, 0), (0, 0), (0, 1)) - 90.0) < 0.01


def test_compute_angle_180_degrees():
    # Straight line: (0,0)–(1,0)–(2,0) → 180°
    assert abs(compute_angle((0, 0), (1, 0), (2, 0)) - 180.0) < 0.01


def test_compute_angle_45_degrees():
    assert abs(compute_angle((1, 0), (0, 0), (1, 1)) - 45.0) < 0.5


def test_smooth_signal_median():
    d = deque([10, 90, 20, 30, 40])
    assert smooth_signal(d) == 30.0


def test_smooth_signal_single():
    d = deque([42.0])
    assert smooth_signal(d) == 42.0


def test_get_joint_angle_low_visibility_returns_none():
    kps = [
        Keypoint(x=0.5, y=0.5, visibility=0.1),  # low visibility
        Keypoint(x=0.6, y=0.5, visibility=0.9),
        Keypoint(x=0.6, y=0.6, visibility=0.9),
    ]
    assert get_joint_angle(kps, 0, 1, 2) is None


def test_get_joint_angle_computes_correctly():
    # Approximate 90° at keypoint index 1
    kps = [
        Keypoint(x=0.0, y=0.5, visibility=0.9),
        Keypoint(x=0.5, y=0.5, visibility=0.9),
        Keypoint(x=0.5, y=0.0, visibility=0.9),
    ]
    angle = get_joint_angle(kps, 0, 1, 2)
    assert angle is not None
    assert abs(angle - 90.0) < 0.5


# ── Rep counter ───────────────────────────────────────────────────────────────

def _make_squat_counter() -> RepCounter:
    registry = ExerciseRegistry(_YAML)
    return RepCounter(registry.get_exercise("squat"))


def test_rep_counter_counts_full_cycles():
    counter = _make_squat_counter()
    # Squat: up=160, down=100.
    # The median filter delays transitions, so we use enough frames per phase
    # and collect events from ALL calls (not just the last UP block).
    reps_counted = 0
    ts = 0

    def feed(angle: float, n: int) -> int:
        nonlocal reps_counted, ts
        count = 0
        for _ in range(n):
            ev = counter.update(1, angle, ts)
            ts += 1
            if ev is not None:
                count += 1
        return count

    # Prime the UP phase (needs enough frames to lock in)
    feed(165.0, 6)

    for _ in range(5):
        # DOWN phase — enough frames to overcome median filter lag
        feed(95.0, 8)
        # UP phase — rep fires once UP phase confirms after DOWN
        reps_counted += feed(165.0, 8)

    assert reps_counted == 5


def test_rep_counter_no_count_without_down_phase():
    counter = _make_squat_counter()
    # Only UP angles — no rep should be counted
    for _ in range(20):
        ev = counter.update(1, 165.0, 0)
        assert ev is None


def test_rep_counter_noise_does_not_cause_false_counts():
    counter = _make_squat_counter()
    # Jitter around up threshold — should not trigger a rep
    import random
    random.seed(42)
    reps = 0
    for _ in range(50):
        angle = 160.0 + random.uniform(-3, 3)  # noise around threshold
        ev = counter.update(1, angle, 0)
        if ev is not None:
            reps += 1
    assert reps == 0


# ── Form analyzer ─────────────────────────────────────────────────────────────

def _make_squat_analyzer() -> FormAnalyzer:
    registry = ExerciseRegistry(_YAML)
    return FormAnalyzer(registry.get_exercise("squat"))


def _make_kps_with_angle(a_idx, b_idx, c_idx, target_angle_deg, n=17) -> list[Keypoint]:
    """Construct a minimal keypoint list that produces roughly target_angle at b."""
    kps = [Keypoint(x=float(i) * 0.05, y=0.5, visibility=0.9) for i in range(n)]
    # Place a, b, c to produce the desired angle
    rad = math.radians(target_angle_deg)
    kps[b_idx] = Keypoint(x=0.5, y=0.5, visibility=0.9)
    kps[a_idx] = Keypoint(x=0.5 + 0.2, y=0.5, visibility=0.9)
    kps[c_idx] = Keypoint(x=0.5 + 0.2 * math.cos(rad), y=0.5 + 0.2 * math.sin(rad), visibility=0.9)
    return kps


def test_form_alert_fires_after_debounce():
    analyzer = _make_squat_analyzer()
    # Construct keypoints where knee_cave check (joint 11-13-15, min=80) is violated
    # Give angle = 60 (below min_angle=80) for shallow_depth check (min=0,max=115 → angle must be >115)
    # Easier: use the shallow_depth check (angle > max=115 → no alert)
    # Actually let's make the knee angle VERY small to trigger min_angle=80 for knee_cave
    kps = _make_kps_with_angle(11, 13, 15, 50.0)  # 50° < min_angle=80 → out of range

    alerts_fired = 0
    for i in range(5):
        alerts = analyzer.check(
            track_id=1,
            keypoints=kps,
            exercise_set_id="test-set-id",
            rep_count=3,
            timestamp_ns=i * 1_000_000,
        )
        alerts_fired += len(alerts)

    assert alerts_fired >= 1, "Expected at least 1 alert after 3+ out-of-range frames"


def test_form_alert_not_fired_for_2_frames():
    analyzer = _make_squat_analyzer()
    kps = _make_kps_with_angle(11, 13, 15, 50.0)

    for i in range(2):
        alerts = analyzer.check(
            track_id=2,
            keypoints=kps,
            exercise_set_id="test-set-id",
            rep_count=1,
            timestamp_ns=i * 1_000_000,
        )
        assert len(alerts) == 0, "Alert should not fire after only 2 frames"
