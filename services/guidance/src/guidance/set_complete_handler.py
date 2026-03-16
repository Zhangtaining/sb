"""Set-complete handler — consumes set_complete stream and gives weight progression advice."""
from __future__ import annotations

import time
import uuid

import redis.asyncio as aioredis
from sqlalchemy import select

from gym_shared.db.session import get_db
from gym_shared.events.publisher import GROUP_GUIDANCE, ack, ensure_consumer_group, read_group
from gym_shared.events.schemas import SetCompleteEvent
from gym_shared.logging import get_logger

from guidance.config import GuidanceConfig
from guidance.llm_client import GymLLMClient
from guidance.notification_dispatcher import NotificationDispatcher
from guidance.prompt_builder import PromptBuilder

log = get_logger(__name__)

_STREAM_SET_COMPLETE = "set_complete"

# Form score thresholds for weight advice
_INCREASE_FORM_THRESHOLD = 0.85
_DECREASE_FORM_THRESHOLD = 0.60

# Rep count margin below target range minimum before suggesting decrease
_DECREASE_REP_MARGIN = 2

# Fallback templates (used if LLM is rate-limited or unavailable)
_TEMPLATES = {
    "increase": (
        "Great set — clean form across all {rep_count} reps! "
        "You're ready to bump the weight up a little next set."
    ),
    "decrease": (
        "Nice effort on {rep_count} reps of {exercise}. "
        "Focus on form before adding more weight — you'll get there."
    ),
    "maintain": (
        "Solid set — {rep_count} reps of {exercise}. "
        "Keep this weight and aim to tighten up the form next set."
    ),
}


def _determine_advice(
    rep_count: int,
    avg_form_score: float,
    target_rep_range: tuple[int, int],
) -> str:
    """Return 'increase', 'decrease', or 'maintain' based on reps + form."""
    min_reps, max_reps = target_rep_range
    if avg_form_score >= _INCREASE_FORM_THRESHOLD and rep_count >= max_reps:
        return "increase"
    if avg_form_score < _DECREASE_FORM_THRESHOLD or rep_count < min_reps - _DECREASE_REP_MARGIN:
        return "decrease"
    return "maintain"


class SetCompleteHandler:
    """Consumes set_complete stream and dispatches weight progression advice."""

    def __init__(
        self,
        config: GuidanceConfig,
        llm: GymLLMClient,
        dispatcher: NotificationDispatcher,
        prompt_builder: PromptBuilder,
    ) -> None:
        self._cfg = config
        self._llm = llm
        self._dispatcher = dispatcher
        self._pb = prompt_builder
        self._last_sent: dict[int, float] = {}

    async def run(self, redis: aioredis.Redis) -> None:
        await ensure_consumer_group(redis, _STREAM_SET_COMPLETE, GROUP_GUIDANCE)
        log.info("set_complete_handler_starting")

        while True:
            messages = await read_group(
                redis,
                _STREAM_SET_COMPLETE,
                GROUP_GUIDANCE,
                self._cfg.consumer_name,
                count=5,
                block_ms=self._cfg.block_ms,
            )
            for msg_id, msg_data in messages:
                try:
                    await self._handle(msg_data)
                except Exception as exc:
                    log.error("set_complete_handler_error", error=str(exc))
                finally:
                    await ack(redis, _STREAM_SET_COMPLETE, GROUP_GUIDANCE, msg_id)

    async def _handle(self, msg_data: dict) -> None:
        event = SetCompleteEvent.model_validate_json(msg_data.get("data", "{}"))
        track_id = event.track_id
        now = time.monotonic()

        # Rate limit — one message per set; never more than 1 per 10s per track
        if now - self._last_sent.get(track_id, 0) < 10:
            return

        # Skip if no reps actually happened
        if event.rep_count == 0:
            return

        # Resolve person_id for this track
        person_id = await self._get_person_id(track_id)

        # Determine target rep range from exercise registry
        target_rep_range = await self._get_target_rep_range(event.exercise_type)
        advice = _determine_advice(event.rep_count, event.avg_form_score, target_rep_range)

        # Try LLM, fall back to template
        try:
            async with get_db() as db:
                prompt = await self._pb.build_set_complete_prompt(
                    db=db,
                    person_id=person_id,
                    exercise=event.exercise_type,
                    rep_count=event.rep_count,
                    avg_form_score=event.avg_form_score,
                    advice_direction=advice,
                    target_rep_range=target_rep_range,
                )
            message = await self._llm.generate_guidance(prompt, "")
            if not message:
                raise ValueError("empty LLM response")
        except Exception as exc:
            log.warning("set_complete_llm_fallback", error=str(exc))
            message = _TEMPLATES[advice].format(
                rep_count=event.rep_count,
                exercise=event.exercise_type,
            )

        self._last_sent[track_id] = now

        await self._dispatcher.dispatch(
            track_id=track_id,
            message=message,
            trigger_type="set_complete",
            exercise_type=event.exercise_type,
            timestamp_ns=event.timestamp_ns,
        )
        log.info(
            "set_complete_advice_dispatched",
            track_id=track_id,
            exercise=event.exercise_type,
            reps=event.rep_count,
            form_score=event.avg_form_score,
            advice=advice,
        )

    async def _get_person_id(self, track_id: int) -> uuid.UUID | None:
        from gym_shared.db.models import Track
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(Track.global_person_id)
                    .where(Track.local_track_id == track_id)
                    .order_by(Track.first_seen_at.desc())
                    .limit(1)
                )
                val = result.scalar_one_or_none()
                return uuid.UUID(str(val)) if val else None
        except Exception:
            return None

    async def _get_target_rep_range(self, exercise_type: str) -> tuple[int, int]:
        """Load target rep range from exercise registry YAML."""
        try:
            from pathlib import Path
            import yaml
            yaml_path = Path(__file__).parents[5] / "exercise" / "data" / "exercises.yaml"
            if yaml_path.exists():
                with open(yaml_path) as f:
                    data = yaml.safe_load(f)
                entry = data.get("exercises", {}).get(exercise_type, {})
                rng = entry.get("target_rep_range", [8, 12])
                return (int(rng[0]), int(rng[1]))
        except Exception:
            pass
        return (8, 12)
