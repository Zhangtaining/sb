"""LLM tool executor — dispatches tool calls to DB queries."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from gym_shared.logging import get_logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

log = get_logger(__name__)


class ToolExecutor:
    """Executes LLM tool calls against the database."""

    def __init__(self, db: AsyncSession, person_id: uuid.UUID) -> None:
        self._db = db
        self._person_id = person_id

    async def run(self, tool_name: str, tool_input: dict) -> str:
        """Dispatch tool call and return a JSON string result."""
        import json

        handlers = {
            "get_workout_history": self._get_workout_history,
            "get_exercise_stats": self._get_exercise_stats,
            "suggest_workout_plan": self._suggest_workout_plan,
            "get_person_profile": self._get_person_profile,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            raise ValueError(f"Unknown tool: {tool_name!r}")

        result = await handler(**tool_input)
        return json.dumps(result, default=str)

    async def _get_workout_history(self, days: int = 7) -> dict:
        from gym_shared.db.models import ExerciseSet, GymSession

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self._db.execute(
            select(GymSession)
            .where(GymSession.person_id == self._person_id)
            .where(GymSession.started_at >= cutoff)
            .order_by(GymSession.started_at.desc())
        )
        sessions = result.scalars().all()

        history = []
        for s in sessions:
            sets_result = await self._db.execute(
                select(
                    ExerciseSet.exercise_type,
                    ExerciseSet.rep_count,
                    ExerciseSet.form_score,
                    ExerciseSet.started_at,
                ).where(ExerciseSet.session_id == s.id)
            )
            sets = [
                {
                    "exercise": ex,
                    "reps": reps,
                    "form_score": round(score, 1) if score else None,
                    "time": started.isoformat(),
                }
                for ex, reps, score, started in sets_result.fetchall()
            ]
            history.append(
                {
                    "session_date": s.started_at.strftime("%Y-%m-%d"),
                    "duration_minutes": (
                        int((s.ended_at - s.started_at).total_seconds() / 60)
                        if s.ended_at
                        else None
                    ),
                    "exercises": sets,
                }
            )
        return {"days": days, "sessions": history}

    async def _get_exercise_stats(self, exercise_name: str) -> dict:
        from gym_shared.db.models import ExerciseSet, GymSession

        # All sets for this exercise across all sessions
        result = await self._db.execute(
            select(ExerciseSet.rep_count, ExerciseSet.form_score, ExerciseSet.started_at)
            .join(GymSession, GymSession.id == ExerciseSet.session_id)
            .where(GymSession.person_id == self._person_id)
            .where(ExerciseSet.exercise_type == exercise_name)
            .order_by(ExerciseSet.started_at.desc())
            .limit(20)
        )
        rows = result.fetchall()

        if not rows:
            return {"exercise": exercise_name, "message": "No history found for this exercise."}

        rep_counts = [r for r, _, _ in rows]
        form_scores = [s for _, s, _ in rows if s is not None]

        # Last 5 sets for trend
        recent = [{"reps": r, "form": round(s, 1) if s else None} for r, s, _ in rows[:5]]

        return {
            "exercise": exercise_name,
            "personal_best_reps": max(rep_counts),
            "average_reps": round(sum(rep_counts) / len(rep_counts), 1),
            "average_form_score": round(sum(form_scores) / len(form_scores), 1) if form_scores else None,
            "total_sets": len(rows),
            "recent_sets": recent,
        }

    async def _suggest_workout_plan(
        self, focus_area: str, duration_minutes: int = 45
    ) -> dict:
        """Build a workout plan based on history and focus area."""
        from gym_shared.db.models import ExerciseSet, GymSession

        # Get recent exercises to avoid repeating same muscle groups
        cutoff = datetime.now(timezone.utc) - timedelta(days=3)
        result = await self._db.execute(
            select(ExerciseSet.exercise_type)
            .join(GymSession, GymSession.id == ExerciseSet.session_id)
            .where(GymSession.person_id == self._person_id)
            .where(GymSession.started_at >= cutoff)
            .distinct()
        )
        recent_exercises = {row[0] for row in result.fetchall()}

        # Simple exercise database by focus area
        exercise_db: dict[str, list[dict]] = {
            "legs": [
                {"name": "squat", "sets": 4, "reps": "8–12"},
                {"name": "lunge", "sets": 3, "reps": "10 each leg"},
                {"name": "leg_press", "sets": 3, "reps": "12–15"},
                {"name": "calf_raise", "sets": 3, "reps": "15–20"},
            ],
            "upper body": [
                {"name": "push_up", "sets": 4, "reps": "10–15"},
                {"name": "pull_up", "sets": 3, "reps": "6–10"},
                {"name": "bicep_curl", "sets": 3, "reps": "10–12"},
                {"name": "lateral_raise", "sets": 3, "reps": "12–15"},
            ],
            "chest": [
                {"name": "bench_press", "sets": 4, "reps": "8–10"},
                {"name": "push_up", "sets": 3, "reps": "15"},
                {"name": "chest_fly", "sets": 3, "reps": "12"},
            ],
            "back": [
                {"name": "pull_up", "sets": 4, "reps": "6–10"},
                {"name": "bent_over_row", "sets": 3, "reps": "10–12"},
                {"name": "lat_pulldown", "sets": 3, "reps": "12"},
            ],
            "cardio": [
                {"name": "box_jump", "sets": 3, "reps": "10"},
                {"name": "burpee", "sets": 3, "reps": "10"},
                {"name": "jump_squat", "sets": 3, "reps": "12"},
            ],
            "full body": [
                {"name": "squat", "sets": 3, "reps": "10"},
                {"name": "push_up", "sets": 3, "reps": "12"},
                {"name": "lunge", "sets": 3, "reps": "10 each"},
                {"name": "bicep_curl", "sets": 2, "reps": "12"},
            ],
        }

        # Find best matching focus area
        focus_lower = focus_area.lower()
        matched_key = next(
            (k for k in exercise_db if k in focus_lower or focus_lower in k),
            "full body",
        )
        exercises = exercise_db[matched_key]

        # Flag recently done exercises
        plan = []
        for ex in exercises:
            entry = dict(ex)
            entry["recently_done"] = ex["name"] in recent_exercises
            plan.append(entry)

        return {
            "focus_area": focus_area,
            "duration_minutes": duration_minutes,
            "exercises": plan,
            "note": "Adjust weights based on feel. Rest 60–90s between sets.",
        }

    async def _get_person_profile(self) -> dict:
        from gym_shared.db.models import Person

        person = await self._db.get(Person, self._person_id)
        if person is None:
            return {"error": "Person not found"}
        return {
            "name": person.display_name,
            "goals": person.goals if isinstance(person.goals, list) else [],
            "injury_notes": person.injury_notes or "",
            "member_since": person.created_at.strftime("%Y-%m-%d"),
        }
