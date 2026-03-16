"""Personalized LLM prompt builder for Phase 2."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from gym_shared.logging import get_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

log = get_logger(__name__)

_TRAINER_PERSONA = (
    "You are an expert personal trainer AI for a smart gym system. "
    "You are encouraging, knowledgeable, and give concise, actionable advice. "
    "Keep responses brief (1–3 sentences) unless the user asks for detail."
)


class PromptBuilder:
    """Builds personalized system prompts for LLM guidance."""

    async def build_system_prompt(self, db: AsyncSession, person_id: uuid.UUID) -> str:
        """Full system prompt for mid-workout guidance — includes name, goals, history."""
        from gym_shared.db.models import ExerciseSet, GymSession, Person

        person = await db.get(Person, person_id)
        if person is None:
            return _TRAINER_PERSONA

        name = person.display_name
        goals = person.goals if isinstance(person.goals, list) else []
        injury = person.injury_notes or ""

        # Fetch last 5 sessions summary
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        result = await db.execute(
            select(GymSession)
            .where(GymSession.person_id == person_id)
            .where(GymSession.started_at >= cutoff)
            .order_by(GymSession.started_at.desc())
            .limit(5)
        )
        sessions = result.scalars().all()

        history_lines = []
        for s in sessions:
            date_str = s.started_at.strftime("%Y-%m-%d")
            sets_result = await db.execute(
                select(ExerciseSet.exercise_type, ExerciseSet.rep_count, ExerciseSet.form_score)
                .where(ExerciseSet.session_id == s.id)
            )
            sets = sets_result.fetchall()
            if sets:
                summary = ", ".join(
                    f"{ex}×{reps} (form {score:.0f}%)" if score else f"{ex}×{reps}"
                    for ex, reps, score in sets
                )
                history_lines.append(f"  {date_str}: {summary}")

        parts = [
            _TRAINER_PERSONA,
            f"\nYou are working with {name}.",
        ]
        if goals:
            parts.append(f"Their fitness goals: {', '.join(goals)}.")
        if injury:
            parts.append(f"Injury/limitation notes: {injury}.")
        if history_lines:
            parts.append(
                "Recent workout history (last 30 days):\n" + "\n".join(history_lines)
            )
        parts.append(
            "\nWhen giving form corrections, address them by name and be specific. "
            "When asked about their progress, reference their actual history above."
        )
        return "\n".join(parts)

    async def build_form_alert_prompt(
        self,
        db: AsyncSession,
        person_id: uuid.UUID | None,
        exercise: str,
        rep_count: int,
        alert_message: str,
    ) -> str:
        """Prompt for a real-time form correction during a set."""
        from gym_shared.db.models import Person

        if person_id:
            person = await db.get(Person, person_id)
            name = person.display_name if person else "there"
        else:
            name = "there"

        return (
            f"{_TRAINER_PERSONA}\n\n"
            f"The person you are coaching (call them '{name}') is doing {exercise} "
            f"and is on rep {rep_count}. "
            f"A form issue was detected: {alert_message}. "
            "Give a short (1–2 sentence) correction cue, as if speaking aloud through their earpiece."
        )

    async def build_set_complete_prompt(
        self,
        db: AsyncSession,
        person_id: uuid.UUID | None,
        exercise: str,
        rep_count: int,
        avg_form_score: float,
        advice_direction: str,  # "increase" | "decrease" | "maintain"
        target_rep_range: tuple[int, int],
    ) -> str:
        """Post-set prompt for weight progression advice."""
        from gym_shared.db.models import Person

        if person_id:
            person = await db.get(Person, person_id)
            name = person.display_name if person else "there"
        else:
            name = "there"

        form_pct = int(avg_form_score * 100)
        return (
            f"{_TRAINER_PERSONA}\n\n"
            f"The person you're coaching (call them '{name}') just finished a set of "
            f"{exercise}: {rep_count} reps with {form_pct}% form quality. "
            f"Target rep range: {target_rep_range[0]}–{target_rep_range[1]}. "
            f"Based on their performance, the recommendation is to {advice_direction} the weight. "
            "Give a short (1–2 sentence) post-set message: acknowledge their effort, then give the "
            "weight recommendation with a specific reason. Be direct and motivating."
        )

    async def build_milestone_prompt(
        self,
        db: AsyncSession,
        person_id: uuid.UUID | None,
        exercise: str,
        rep_count: int,
        is_personal_best: bool = False,
        previous_best: int | None = None,
    ) -> str:
        """Encouragement prompt for rep milestones and personal bests."""
        from gym_shared.db.models import Person

        if person_id:
            person = await db.get(Person, person_id)
            name = person.display_name if person else "there"
        else:
            name = "there"

        if is_personal_best and previous_best:
            context = (
                f"'{name}' just achieved a new personal best: {rep_count} reps of {exercise} "
                f"(previous best was {previous_best}). "
                "Celebrate this achievement with genuine excitement — mention the exact numbers. "
                "Keep it to 1–2 sentences."
            )
        else:
            context = (
                f"'{name}' just completed rep {rep_count} of {exercise}. "
                "Give a short (1 sentence) mid-set encouragement. "
                "Be energetic. Vary the language — don't always say 'great job'."
            )

        return f"{_TRAINER_PERSONA}\n\n{context}"

    async def build_onboarding_prompt(
        self, db: AsyncSession, person_id: uuid.UUID
    ) -> str:
        """Session-start prompt: greet user, ask what they want to work on."""
        from gym_shared.db.models import ExerciseSet, GymSession, Person

        person = await db.get(Person, person_id)
        if person is None:
            return (
                f"{_TRAINER_PERSONA}\n\n"
                "A new gym session has just started. Greet the member and ask what "
                "they would like to work on today. Be brief and warm."
            )

        name = person.display_name
        goals = person.goals if isinstance(person.goals, list) else []

        # Find last session
        result = await db.execute(
            select(GymSession)
            .where(GymSession.person_id == person_id)
            .where(GymSession.ended_at != None)  # noqa: E711
            .order_by(GymSession.started_at.desc())
            .limit(1)
        )
        last_session = result.scalar_one_or_none()

        last_session_info = ""
        if last_session:
            days_ago = (datetime.now(timezone.utc) - last_session.started_at).days
            sets_result = await db.execute(
                select(ExerciseSet.exercise_type)
                .where(ExerciseSet.session_id == last_session.id)
                .distinct()
            )
            exercises = [row[0] for row in sets_result.fetchall()]
            if exercises:
                last_session_info = (
                    f"{name}'s last workout was {days_ago} day(s) ago and included: "
                    f"{', '.join(exercises)}. "
                )

        return (
            f"{_TRAINER_PERSONA}\n\n"
            f"A new gym session just started for {name}. "
            + (f"Their goals: {', '.join(goals)}. " if goals else "")
            + last_session_info
            + f"Greet {name} warmly by name, briefly reference what they last worked on "
            "if applicable, and ask what they'd like to focus on today. "
            "Keep it to 2–3 sentences. Be energetic and motivating."
        )
