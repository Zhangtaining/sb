"""Notification dispatcher — routes guidance messages to the correct WebSocket session.

Phase 1: Publishes messages to the `guidance` Redis Stream.
         The API gateway subscribes and forwards to the correct WebSocket client.
Phase 2: Will add push notification fallback via FCM.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis

from gym_shared.db.models import Notification
from gym_shared.db.session import get_db
from gym_shared.events.publisher import publish
from gym_shared.events.schemas import GuidanceMessage
from gym_shared.logging import get_logger

log = get_logger(__name__)

_STREAM_GUIDANCE = "guidance"
_WS_SESSION_KEY = "track:{track_id}:ws_session"


class NotificationDispatcher:
    """Dispatches guidance messages to the right channel.

    Args:
        redis: Async Redis client (shared).
        camera_id: Current camera context.
    """

    def __init__(self, redis: aioredis.Redis, camera_id: str) -> None:
        self._redis = redis
        self._camera_id = camera_id

    async def dispatch(
        self,
        track_id: int,
        message: str,
        trigger_type: str,
        exercise_type: str | None = None,
        timestamp_ns: int = 0,
    ) -> None:
        """Send a guidance message for a tracked person.

        Publishes a GuidanceMessage to the `guidance` Redis Stream.
        Also persists to the notifications table.
        Logs at INFO if no WS session is active (Phase 1 behaviour).
        """
        # Check if there is an active WebSocket session for this track
        ws_key = _WS_SESSION_KEY.format(track_id=track_id)
        ws_session = await self._redis.get(ws_key)

        if ws_session is None:
            log.info(
                "no_active_ws_session",
                track_id=track_id,
                message_preview=message[:60],
            )
        else:
            log.info(
                "guidance_dispatched",
                track_id=track_id,
                ws_session=ws_session,
                trigger=trigger_type,
            )

        event = GuidanceMessage(
            camera_id=self._camera_id,
            track_id=track_id,
            person_id=None,
            message=message,
            trigger_type=trigger_type,
            exercise_type=exercise_type,
            timestamp_ns=timestamp_ns,
        )
        await publish(self._redis, _STREAM_GUIDANCE, event)
        await self._persist(track_id, message)

    async def _persist(self, track_id: int, message: str) -> None:
        try:
            async with get_db() as db:
                notification = Notification(
                    id=uuid.uuid4(),
                    channel="websocket",
                    content=message,
                    sent_at=datetime.now(timezone.utc),
                )
                db.add(notification)
        except Exception as exc:
            # Non-fatal — guidance delivery succeeds even if DB write fails
            log.warning("notification_persist_failed", error=str(exc))
