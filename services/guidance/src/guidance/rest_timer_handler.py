"""Rest timer handler — advises on rest duration between sets."""
from __future__ import annotations

import redis.asyncio as aioredis

from gym_shared.events.publisher import GROUP_GUIDANCE, ack, ensure_consumer_group, read_group
from gym_shared.events.schemas import RestTimerEvent
from gym_shared.logging import get_logger

from guidance.config import GuidanceConfig
from guidance.notification_dispatcher import NotificationDispatcher

log = get_logger(__name__)

_STREAM_REST_TIMER = "rest_timer"

# Nudge when rest exceeds this (seconds)
_LONG_REST_NUDGE_S = 120

# Warn if rest was shorter than this for strength exercises (seconds)
_SHORT_REST_WARN_S = 60

# Templates (no LLM needed — rest advice is time-sensitive and templated)
_NUDGE_TEMPLATE = (
    "You've been resting for {rest_s_str} — ready when you are! "
    "Take your time, but aim to keep rest under {max_rest_s_str} for best results."
)
_SHORT_REST_TEMPLATE = (
    "Quick note: you only rested {rest_s_str} between sets. "
    "For {exercise}, aim for at least {min_rest_s_str} to recover properly — "
    "it'll improve your performance next set."
)
_GOOD_REST_TEMPLATE = (
    "Good rest — {rest_s_str}. Time to get back at it!"
)


def _fmt_seconds(s: int) -> str:
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60}s" if s % 60 else f"{s // 60}m"


class RestTimerHandler:
    """Consumes rest_timer stream and dispatches rest duration advice.

    Sends a nudge when rest exceeds 2 minutes.
    Sends a warning when rest was too short for the exercise type.
    """

    def __init__(
        self,
        config: GuidanceConfig,
        dispatcher: NotificationDispatcher,
    ) -> None:
        self._cfg = config
        self._dispatcher = dispatcher
        # track_id → True if nudge already sent for this rest period
        self._nudge_sent: dict[int, bool] = {}

    async def run(self, redis: aioredis.Redis) -> None:
        await ensure_consumer_group(redis, _STREAM_REST_TIMER, GROUP_GUIDANCE)
        log.info("rest_timer_handler_starting")

        while True:
            messages = await read_group(
                redis,
                _STREAM_REST_TIMER,
                GROUP_GUIDANCE,
                self._cfg.consumer_name,
                count=10,
                block_ms=self._cfg.block_ms,
            )
            for msg_id, msg_data in messages:
                try:
                    await self._handle(msg_data)
                except Exception as exc:
                    log.error("rest_timer_handler_error", error=str(exc))
                finally:
                    await ack(redis, _STREAM_REST_TIMER, GROUP_GUIDANCE, msg_id)

    async def _handle(self, msg_data: dict) -> None:
        event = RestTimerEvent.model_validate_json(msg_data.get("data", "{}"))
        track_id = event.track_id
        rest_s = event.rest_s

        if event.finished:
            # Rest ended — check if it was too short
            self._nudge_sent.pop(track_id, None)
            optimal_range = await self._get_optimal_rest_range(event.exercise_set_id)
            min_rest_s = optimal_range[0]

            if rest_s < _SHORT_REST_WARN_S and min_rest_s > _SHORT_REST_WARN_S:
                exercise = await self._get_exercise_for_set(event.exercise_set_id)
                message = _SHORT_REST_TEMPLATE.format(
                    rest_s_str=_fmt_seconds(rest_s),
                    exercise=exercise or "this exercise",
                    min_rest_s_str=_fmt_seconds(min_rest_s),
                )
                await self._dispatcher.dispatch(
                    track_id=track_id,
                    message=message,
                    trigger_type="rest_advice",
                    exercise_type=exercise,
                    timestamp_ns=event.timestamp_ns,
                )
                log.info(
                    "short_rest_warning_sent",
                    track_id=track_id,
                    rest_s=rest_s,
                    min_rest_s=min_rest_s,
                )
        else:
            # Ongoing rest — nudge if over threshold and not already nudged
            if rest_s >= _LONG_REST_NUDGE_S and not self._nudge_sent.get(track_id):
                self._nudge_sent[track_id] = True
                optimal_range = await self._get_optimal_rest_range(event.exercise_set_id)
                max_rest_s = optimal_range[1]
                message = _NUDGE_TEMPLATE.format(
                    rest_s_str=_fmt_seconds(rest_s),
                    max_rest_s_str=_fmt_seconds(max_rest_s),
                )
                await self._dispatcher.dispatch(
                    track_id=track_id,
                    message=message,
                    trigger_type="rest_advice",
                    exercise_type=None,
                    timestamp_ns=event.timestamp_ns,
                )
                log.info(
                    "long_rest_nudge_sent",
                    track_id=track_id,
                    rest_s=rest_s,
                )

    async def _get_optimal_rest_range(self, exercise_set_id: str) -> tuple[int, int]:
        """Look up optimal_rest_range_s for the exercise of this set."""
        try:
            from gym_shared.db.models import ExerciseSet
            from gym_shared.db.session import get_db
            import uuid
            async with get_db() as db:
                result = await db.execute(
                    __import__("sqlalchemy", fromlist=["select"]).select(
                        ExerciseSet.exercise_type
                    ).where(ExerciseSet.id == uuid.UUID(exercise_set_id))
                )
                exercise_type = result.scalar_one_or_none()
            if exercise_type:
                return await self._get_rest_range_for_exercise(exercise_type)
        except Exception:
            pass
        return (60, 180)

    async def _get_exercise_for_set(self, exercise_set_id: str) -> str | None:
        try:
            from gym_shared.db.models import ExerciseSet
            from gym_shared.db.session import get_db
            import uuid
            async with get_db() as db:
                result = await db.execute(
                    __import__("sqlalchemy", fromlist=["select"]).select(
                        ExerciseSet.exercise_type
                    ).where(ExerciseSet.id == uuid.UUID(exercise_set_id))
                )
                return result.scalar_one_or_none()
        except Exception:
            return None

    async def _get_rest_range_for_exercise(self, exercise_type: str) -> tuple[int, int]:
        try:
            from pathlib import Path
            import yaml
            yaml_path = Path(__file__).parents[5] / "exercise" / "data" / "exercises.yaml"
            if yaml_path.exists():
                with open(yaml_path) as f:
                    data = yaml.safe_load(f)
                entry = data.get("exercises", {}).get(exercise_type, {})
                rng = entry.get("optimal_rest_range_s", [60, 180])
                return (int(rng[0]), int(rng[1]))
        except Exception:
            pass
        return (60, 180)
