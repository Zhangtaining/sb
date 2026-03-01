"""Exercise registry — loads exercises.yaml and provides typed definitions."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from gym_shared.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class FormCheck:
    name: str
    joint: tuple[int, int, int]   # keypoint indices [a, b, c]
    min_angle: float
    max_angle: float
    alert_key: str
    alert_message: str
    severity: str = "warning"


@dataclass(frozen=True)
class ExerciseDefinition:
    name: str
    primary_joint: tuple[int, int, int]  # keypoint indices for rep counting
    up_angle: float
    down_angle: float
    form_checks: tuple[FormCheck, ...]


class ExerciseRegistry:
    """Loads exercise definitions from a YAML file at startup."""

    def __init__(self, yaml_path: str | Path) -> None:
        self._exercises: dict[str, ExerciseDefinition] = {}
        self._load(Path(yaml_path))
        log.info("exercise_registry_loaded", exercises=list(self._exercises.keys()))

    def _load(self, path: Path) -> None:
        with open(path) as f:
            data = yaml.safe_load(f)
        for key, entry in data["exercises"].items():
            checks = tuple(
                FormCheck(
                    name=c["name"],
                    joint=tuple(c["joint"]),
                    min_angle=float(c["min_angle"]),
                    max_angle=float(c["max_angle"]),
                    alert_key=c["alert_key"],
                    alert_message=c["alert_message"],
                    severity=c.get("severity", "warning"),
                )
                for c in entry.get("form_checks", [])
            )
            self._exercises[key] = ExerciseDefinition(
                name=entry["name"],
                primary_joint=tuple(entry["primary_joint"]),
                up_angle=float(entry["up_angle"]),
                down_angle=float(entry["down_angle"]),
                form_checks=checks,
            )

    def get_exercise(self, name: str) -> ExerciseDefinition:
        if name not in self._exercises:
            raise KeyError(
                f"Unknown exercise '{name}'. Available: {list(self._exercises.keys())}"
            )
        return self._exercises[name]

    def list_exercises(self) -> list[str]:
        return list(self._exercises.keys())
