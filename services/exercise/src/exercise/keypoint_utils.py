"""Keypoint geometry utilities for joint angle computation and signal smoothing."""
from __future__ import annotations

import math
from collections import deque
from typing import Sequence

from gym_shared.events.schemas import Keypoint

# Minimum keypoint visibility to treat as valid
_VIS_THRESHOLD = 0.3


def compute_angle(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    """Compute the angle (degrees) at joint b formed by points a-b-c.

    Args:
        a, b, c: (x, y) coordinate pairs in any consistent unit.

    Returns:
        Angle in degrees [0, 180].
    """
    ax, ay = a[0] - b[0], a[1] - b[1]
    cx, cy = c[0] - b[0], c[1] - b[1]
    dot = ax * cx + ay * cy
    mag_a = math.hypot(ax, ay)
    mag_c = math.hypot(cx, cy)
    if mag_a < 1e-9 or mag_c < 1e-9:
        return 0.0
    cos_angle = max(-1.0, min(1.0, dot / (mag_a * mag_c)))
    return math.degrees(math.acos(cos_angle))


def smooth_signal(values: deque, window: int = 5) -> float:
    """Return the median of the last `window` values in the deque."""
    recent = list(values)[-window:]
    if not recent:
        return 0.0
    sorted_vals = sorted(recent)
    mid = len(sorted_vals) // 2
    if len(sorted_vals) % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
    return float(sorted_vals[mid])


def get_joint_angle(
    keypoints: list[Keypoint],
    a_idx: int,
    b_idx: int,
    c_idx: int,
) -> float | None:
    """Compute angle at keypoint b_idx given three keypoint indices.

    Returns None if any of the three keypoints have visibility below threshold.
    """
    if max(a_idx, b_idx, c_idx) >= len(keypoints):
        return None
    ka, kb, kc = keypoints[a_idx], keypoints[b_idx], keypoints[c_idx]
    if ka.visibility < _VIS_THRESHOLD or kb.visibility < _VIS_THRESHOLD or kc.visibility < _VIS_THRESHOLD:
        return None
    return compute_angle((ka.x, ka.y), (kb.x, kb.y), (kc.x, kc.y))


def keypoints_to_joint_angles(
    keypoints: list[Keypoint],
    joint_triples: list[tuple[int, int, int]],
) -> dict[str, float]:
    """Compute a dict of angles for a list of (a, b, c) joint index triples.

    Keys are formatted as "{a}-{b}-{c}". Missing keypoints are omitted.
    """
    angles: dict[str, float] = {}
    for a, b, c in joint_triples:
        angle = get_joint_angle(keypoints, a, b, c)
        if angle is not None:
            angles[f"{a}-{b}-{c}"] = angle
    return angles
