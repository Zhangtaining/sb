"""ReID service entry point.

Consumes perception events from Redis Streams, matches OSNet embeddings
against the registered person gallery, resolves identities, and publishes
identity_resolved events.
"""
from __future__ import annotations

import asyncio
import signal

from gym_shared.logging import configure_logging, get_logger
from gym_shared.settings import settings

from reid.config import build_config

configure_logging(settings.log_format, settings.log_level)
log = get_logger(__name__)


async def run() -> None:
    config = build_config(settings)
    log.info(
        "reid_service_starting",
        cameras=config.camera_ids,
        reid_threshold=config.reid_similarity_threshold,
        face_threshold=config.face_similarity_threshold,
    )

    # Import here to avoid heavy deps at import time during testing
    from reid.identity_resolver import IdentityResolver

    resolver = IdentityResolver(config)
    await resolver.start()


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _shutdown(sig, _frame):
        log.info("shutdown_signal_received", signal=sig)
        loop.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        loop.run_until_complete(run())
    finally:
        loop.close()
        log.info("reid_service_stopped")


if __name__ == "__main__":
    main()
