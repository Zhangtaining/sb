"""Rest timer — tracks rest duration between sets per track.

After a set completes, the timer counts up until the next rep is detected.
Publishes RestTimerEvent updates every REST_UPDATE_INTERVAL_S seconds.
Publishes a final event with finished=True when the next set begins.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import redis.asyncio as aioredis

from gym_shared.events.schemas import RestTimerEvent
from gym_shared.events.publisher import publish
from gym_shared.logging import get_logger

log = get_logger(__name__)

_STREAM_REST_TIMER = "rest_timer"
REST_UPDATE_INTERVAL_S = 30   # publish a rest update every 30 seconds


@dataclass
class RestState:
    exercise_set_id: str
    started_at: float = field(default_factory=time.monotonic)
    update_task: asyncio.Task | None = field(default=None, compare=False)


class RestTimerTracker:
    """Manages rest timers for multiple tracks simultaneously.

    Call start_rest() when a set completes.
    Call end_rest() when the first rep of the next set is detected.
    """

    def __init__(self, camera_id: str, redis: aioredis.Redis) -> None:
        self._camera_id = camera_id
        self._redis = redis
        self._resting: dict[int, RestState] = {}

    def start_rest(self, track_id: int, exercise_set_id: str) -> None:
        """Begin timing rest for a track after a set completes."""
        # Cancel any existing rest for this track (shouldn't happen, but safe)
        self._cancel_existing(track_id)

        state = RestState(exercise_set_id=exercise_set_id)
        task = asyncio.create_task(
            self._update_loop(track_id, state),
            name=f"rest_timer_{track_id}",
        )
        state.update_task = task
        self._resting[track_id] = state
        log.debug("rest_started", track_id=track_id, exercise_set_id=exercise_set_id)

    async def end_rest(self, track_id: int, timestamp_ns: int) -> None:
        """Finish rest for a track when the next set begins."""
        state = self._resting.pop(track_id, None)
        if state is None:
            return

        self._cancel_task(state)
        rest_s = int(time.monotonic() - state.started_at)

        await publish(
            self._redis,
            _STREAM_REST_TIMER,
            RestTimerEvent(
                camera_id=self._camera_id,
                track_id=track_id,
                exercise_set_id=state.exercise_set_id,
                rest_s=rest_s,
                finished=True,
                timestamp_ns=timestamp_ns,
            ),
        )
        log.info(
            "rest_finished",
            track_id=track_id,
            rest_s=rest_s,
            exercise_set_id=state.exercise_set_id,
        )

    def cancel(self, track_id: int) -> None:
        """Cancel rest timer (e.g. track lost) without publishing a finished event."""
        state = self._resting.pop(track_id, None)
        if state:
            self._cancel_task(state)

    def is_resting(self, track_id: int) -> bool:
        return track_id in self._resting

    async def _update_loop(self, track_id: int, state: RestState) -> None:
        """Publish periodic rest updates until cancelled."""
        try:
            while True:
                await asyncio.sleep(REST_UPDATE_INTERVAL_S)
                if track_id not in self._resting:
                    return
                rest_s = int(time.monotonic() - state.started_at)
                timestamp_ns = int(time.time() * 1e9)
                await publish(
                    self._redis,
                    _STREAM_REST_TIMER,
                    RestTimerEvent(
                        camera_id=self._camera_id,
                        track_id=track_id,
                        exercise_set_id=state.exercise_set_id,
                        rest_s=rest_s,
                        finished=False,
                        timestamp_ns=timestamp_ns,
                    ),
                )
                log.debug(
                    "rest_update",
                    track_id=track_id,
                    rest_s=rest_s,
                )
        except asyncio.CancelledError:
            pass

    def _cancel_existing(self, track_id: int) -> None:
        state = self._resting.pop(track_id, None)
        if state:
            self._cancel_task(state)

    @staticmethod
    def _cancel_task(state: RestState) -> None:
        if state.update_task and not state.update_task.done():
            state.update_task.cancel()
