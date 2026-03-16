"""Rep milestone handler — encouragement at every 5th rep + personal best detection."""
from __future__ import annotations

import time
import uuid

import redis.asyncio as aioredis
from sqlalchemy import func, select

from gym_shared.db.session import get_db
from gym_shared.events.publisher import GROUP_GUIDANCE, ack, ensure_consumer_group, read_group
from gym_shared.events.schemas import RepCountedEvent, SetCompleteEvent
from gym_shared.logging import get_logger

from guidance.config import GuidanceConfig
from guidance.llm_client import GymLLMClient
from guidance.notification_dispatcher import NotificationDispatcher
from guidance.prompt_builder import PromptBuilder

log = get_logger(__name__)

_STREAM_REP_COUNTED = "rep_counted"
_STREAM_SET_COMPLETE = "set_complete"

# Fire LLM encouragement on these rep milestones (every 5th rep)
_MILESTONE_INTERVAL = 5

# Rate limit: never fire more than 1 encouragement per N seconds per track
_RATE_LIMIT_S = 25

# Fallback mid-set encouragements (rotated to avoid repetition)
_MID_SET_PHRASES = [
    "Keep it up — {rep_count} reps in!",
    "Strong work — {rep_count} reps!",
    "{rep_count} reps — stay focused!",
    "Halfway there — keep that form tight!",
    "{rep_count} reps and counting — push through!",
]


class RepMilestoneHandler:
    """Subscribes to rep_counted and set_complete, fires encouragement messages.

    Fires encouragement on every 5th rep mid-set.
    Fires a personal best celebration after set_complete if a new PB is achieved.
    """

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
        # track_id → last encouragement timestamp
        self._last_sent: dict[int, float] = {}
        # track_id → last milestone rep fired (to avoid double-fire)
        self._last_milestone: dict[int, int] = {}
        # track_id → (exercise_type, rep_count) for PB checking after set_complete
        self._last_set: dict[int, tuple[str, int]] = {}
        # rolling phrase index per track
        self._phrase_idx: dict[int, int] = {}

    async def run_rep_stream(self, redis: aioredis.Redis) -> None:
        """Loop consuming rep_counted stream for mid-set encouragement."""
        await ensure_consumer_group(redis, _STREAM_REP_COUNTED, GROUP_GUIDANCE)
        log.info("rep_milestone_handler_starting")

        while True:
            messages = await read_group(
                redis,
                _STREAM_REP_COUNTED,
                GROUP_GUIDANCE,
                f"{self._cfg.consumer_name}-milestones",
                count=10,
                block_ms=self._cfg.block_ms,
            )
            for msg_id, msg_data in messages:
                try:
                    await self._handle_rep(msg_data)
                except Exception as exc:
                    log.error("rep_milestone_error", error=str(exc))
                finally:
                    await ack(redis, _STREAM_REP_COUNTED, GROUP_GUIDANCE, msg_id)

    async def run_set_stream(self, redis: aioredis.Redis) -> None:
        """Loop consuming set_complete stream for personal best detection."""
        await ensure_consumer_group(redis, _STREAM_SET_COMPLETE, GROUP_GUIDANCE)

        while True:
            messages = await read_group(
                redis,
                _STREAM_SET_COMPLETE,
                GROUP_GUIDANCE,
                f"{self._cfg.consumer_name}-pb",
                count=5,
                block_ms=self._cfg.block_ms,
            )
            for msg_id, msg_data in messages:
                try:
                    await self._handle_set_complete(msg_data)
                except Exception as exc:
                    log.error("personal_best_error", error=str(exc))
                finally:
                    await ack(redis, _STREAM_SET_COMPLETE, GROUP_GUIDANCE, msg_id)

    async def _handle_rep(self, msg_data: dict) -> None:
        event = RepCountedEvent.model_validate_json(msg_data.get("data", "{}"))
        track_id = event.track_id
        rep_count = event.rep_count
        now = time.monotonic()

        # Only fire on milestone reps
        if rep_count % _MILESTONE_INTERVAL != 0:
            return

        # Avoid double-firing the same milestone
        if self._last_milestone.get(track_id) == rep_count:
            return

        # Rate limit
        if now - self._last_sent.get(track_id, 0) < _RATE_LIMIT_S:
            return

        self._last_milestone[track_id] = rep_count

        person_id = await self._get_person_id(track_id)

        # Use LLM for round-number milestones, template for others
        use_llm = rep_count % 10 == 0
        if use_llm:
            try:
                async with get_db() as db:
                    prompt = await self._pb.build_milestone_prompt(
                        db=db,
                        person_id=person_id,
                        exercise=event.exercise_type,
                        rep_count=rep_count,
                    )
                message = await self._llm.generate_guidance(prompt, "")
                if not message:
                    raise ValueError("empty response")
            except Exception:
                message = self._fallback_phrase(track_id, rep_count)
        else:
            message = self._fallback_phrase(track_id, rep_count)

        self._last_sent[track_id] = now
        await self._dispatcher.dispatch(
            track_id=track_id,
            message=message,
            trigger_type="encouragement",
            exercise_type=event.exercise_type,
            timestamp_ns=event.timestamp_ns,
        )
        log.debug(
            "milestone_encouragement_sent",
            track_id=track_id,
            rep_count=rep_count,
            exercise=event.exercise_type,
        )

    async def _handle_set_complete(self, msg_data: dict) -> None:
        event = SetCompleteEvent.model_validate_json(msg_data.get("data", "{}"))
        track_id = event.track_id

        if event.rep_count == 0:
            return

        person_id = await self._get_person_id(track_id)
        if not person_id:
            return

        prev_best = await self._get_personal_best(person_id, event.exercise_type)
        if prev_best is None or event.rep_count <= prev_best:
            return

        # Personal best achieved!
        try:
            async with get_db() as db:
                prompt = await self._pb.build_milestone_prompt(
                    db=db,
                    person_id=person_id,
                    exercise=event.exercise_type,
                    rep_count=event.rep_count,
                    is_personal_best=True,
                    previous_best=prev_best,
                )
            message = await self._llm.generate_guidance(prompt, "")
            if not message:
                raise ValueError("empty")
        except Exception:
            message = (
                f"New personal best — {event.rep_count} reps of {event.exercise_type}! "
                f"That's {event.rep_count - prev_best} more than your previous record. Outstanding!"
            )

        await self._dispatcher.dispatch(
            track_id=track_id,
            message=message,
            trigger_type="encouragement",
            exercise_type=event.exercise_type,
            timestamp_ns=event.timestamp_ns,
        )
        log.info(
            "personal_best_sent",
            track_id=track_id,
            exercise=event.exercise_type,
            new_best=event.rep_count,
            prev_best=prev_best,
        )

    def _fallback_phrase(self, track_id: int, rep_count: int) -> str:
        idx = self._phrase_idx.get(track_id, 0)
        phrase = _MID_SET_PHRASES[idx % len(_MID_SET_PHRASES)]
        self._phrase_idx[track_id] = idx + 1
        return phrase.format(rep_count=rep_count)

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

    async def _get_personal_best(
        self, person_id: uuid.UUID, exercise_type: str
    ) -> int | None:
        from gym_shared.db.models import ExerciseSet, GymSession
        try:
            async with get_db() as db:
                result = await db.execute(
                    select(func.max(ExerciseSet.rep_count))
                    .join(GymSession, ExerciseSet.session_id == GymSession.id)
                    .where(GymSession.person_id == person_id)
                    .where(ExerciseSet.exercise_type == exercise_type)
                    .where(ExerciseSet.rep_count > 0)
                )
                return result.scalar_one_or_none()
        except Exception:
            return None
