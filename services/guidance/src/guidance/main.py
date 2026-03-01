"""Guidance service entry point."""
from __future__ import annotations

import asyncio
import signal

import redis.asyncio as aioredis

from gym_shared.logging import configure_logging, get_logger
from gym_shared.settings import settings

from guidance.config import build_config
from guidance.form_alert_handler import FormAlertHandler
from guidance.llm_client import GymLLMClient
from guidance.notification_dispatcher import NotificationDispatcher

log = get_logger(__name__)


async def run() -> None:
    configure_logging(settings.log_format, settings.log_level)
    config = build_config(settings)

    if config.llm_provider == "anthropic" and not config.anthropic_api_key:
        log.warning("no_anthropic_api_key", message="LLM calls will fail — set ANTHROPIC_API_KEY")
    elif config.llm_provider == "gemini" and not config.gemini_api_key:
        log.warning("no_gemini_api_key", message="LLM calls will fail — set GEMINI_API_KEY")

    log.info("guidance_service_starting", provider=config.llm_provider, model=config.llm_model)

    redis = aioredis.from_url(config.redis_url, decode_responses=False)

    llm = GymLLMClient(config)

    # One dispatcher per camera (guidance stream is global, not per-camera)
    dispatcher = NotificationDispatcher(redis, camera_id=config.camera_ids[0] if config.camera_ids else "unknown")
    handler = FormAlertHandler(config, llm, dispatcher)

    loop = asyncio.get_running_loop()

    def _shutdown(sig, frame):
        log.info("shutdown_signal_received", signal=sig)
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        await handler.run(redis)
    except asyncio.CancelledError:
        pass
    finally:
        await redis.aclose()
        log.info("guidance_service_stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
