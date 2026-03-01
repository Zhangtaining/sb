"""Form alert handler — subscribes to form_alerts stream and generates LLM guidance."""
from __future__ import annotations

import time

import redis.asyncio as aioredis

from gym_shared.events.publisher import GROUP_GUIDANCE, ack, ensure_consumer_group, read_group
from gym_shared.events.schemas import FormAlertEvent
from gym_shared.logging import get_logger

from guidance.config import GuidanceConfig
from guidance.llm_client import GymLLMClient
from guidance.notification_dispatcher import NotificationDispatcher

log = get_logger(__name__)

_STREAM_FORM_ALERTS = "form_alerts"

_SYSTEM_PROMPT = """\
You are a personal gym coach providing real-time exercise form corrections.
A computer vision system has detected a form issue while someone is exercising.
Give a single concise correction (1-2 sentences, max 30 words).
Be encouraging, direct, and specific. No greetings or filler words.
"""


class FormAlertHandler:
    """Consumes form_alerts stream and generates LLM coaching messages.

    Rate-limited: at most 1 LLM call per track_id per `rate_limit_seconds`.
    """

    def __init__(
        self,
        config: GuidanceConfig,
        llm: GymLLMClient,
        dispatcher: NotificationDispatcher,
    ) -> None:
        self._cfg = config
        self._llm = llm
        self._dispatcher = dispatcher
        # track_id → timestamp of last guidance sent
        self._last_sent: dict[int, float] = {}

    async def run(self, redis: aioredis.Redis) -> None:
        """Main loop consuming form_alerts."""
        await ensure_consumer_group(redis, _STREAM_FORM_ALERTS, GROUP_GUIDANCE)
        log.info("form_alert_handler_starting", rate_limit_s=self._cfg.rate_limit_seconds)

        while True:
            messages = await read_group(
                redis,
                _STREAM_FORM_ALERTS,
                GROUP_GUIDANCE,
                self._cfg.consumer_name,
                count=5,
                block_ms=self._cfg.block_ms,
            )
            for msg_id, msg_data in messages:
                try:
                    await self._handle(msg_data)
                except Exception as exc:
                    log.error("form_alert_handler_error", error=str(exc))
                finally:
                    await ack(redis, _STREAM_FORM_ALERTS, GROUP_GUIDANCE, msg_id)

    async def _handle(self, msg_data: dict) -> None:
        alert = FormAlertEvent.model_validate_json(msg_data.get("data", "{}"))
        track_id = alert.track_id
        now = time.monotonic()

        # Rate limit: skip if we sent guidance recently for this track
        if now - self._last_sent.get(track_id, 0) < self._cfg.rate_limit_seconds:
            log.debug("guidance_rate_limited", track_id=track_id, alert_key=alert.alert_key)
            return

        user_message = (
            f"Exercise: {alert.exercise_type}\n"
            f"Reps completed: {alert.rep_count}\n"
            f"Form issue detected: {alert.alert_message}\n"
            f"Severity: {alert.severity}\n"
            "Provide a brief, encouraging correction."
        )

        guidance_text = await self._llm.generate_guidance(_SYSTEM_PROMPT, user_message)
        if not guidance_text:
            return

        self._last_sent[track_id] = now

        await self._dispatcher.dispatch(
            track_id=track_id,
            message=guidance_text,
            trigger_type="form_alert",
            exercise_type=alert.exercise_type,
            timestamp_ns=alert.timestamp_ns,
        )
        log.info(
            "guidance_generated",
            track_id=track_id,
            alert_key=alert.alert_key,
            guidance=guidance_text[:80],
        )
