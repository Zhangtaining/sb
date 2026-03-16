"""Identity resolver — consumes perception stream, resolves identities, publishes events."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from gym_shared.db.session import get_db
from gym_shared.events.publisher import ensure_consumer_group, read_group, ack
from gym_shared.events.schemas import IdentityResolvedEvent
from gym_shared.logging import get_logger
from gym_shared.redis_client import get_redis_ctx
from sqlalchemy import select, update

from reid.config import ReidConfig
from reid.gallery_manager import GalleryManager
from reid.matcher import IdentityMatcher

log = get_logger(__name__)

_GALLERY_REFRESH_INTERVAL = 300  # seconds


class IdentityResolver:
    """Consumes perception events per camera, resolves identities, publishes results."""

    def __init__(self, config: ReidConfig) -> None:
        self._config = config
        self._gallery = GalleryManager(config)
        self._matcher = IdentityMatcher(config, self._gallery)

    async def start(self) -> None:
        async with get_db() as db:
            await self._gallery.refresh_cache(db)

        # Start gallery refresh loop + per-camera consumer tasks
        tasks = [asyncio.create_task(self._gallery_refresh_loop())]
        for camera_id in self._config.camera_ids:
            tasks.append(asyncio.create_task(self._consume_camera(camera_id)))

        log.info("identity_resolver_started", camera_count=len(self._config.camera_ids))
        await asyncio.gather(*tasks)

    async def _gallery_refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(_GALLERY_REFRESH_INTERVAL)
            try:
                async with get_db() as db:
                    await self._gallery.refresh_cache(db)
                self._matcher.prune_recent_exits()
            except Exception as exc:
                log.error("gallery_refresh_failed", error=str(exc))

    async def _consume_camera(self, camera_id: str) -> None:
        stream_key = f"perceptions:{camera_id}"
        group = self._config.consumer_group
        consumer = self._config.consumer_name

        async with get_redis_ctx(self._config.redis_url) as redis:
            await ensure_consumer_group(redis, stream_key, group)

        log.info("consuming_perceptions", camera_id=camera_id, stream=stream_key)

        while True:
            try:
                async with get_redis_ctx(self._config.redis_url) as redis:
                    messages = await read_group(
                        redis, stream_key, group, consumer,
                        count=10, block_ms=self._config.block_ms,
                    )

                for msg_id, data in messages:
                    await self._handle_perception(camera_id, msg_id, data)
                    async with get_redis_ctx(self._config.redis_url) as redis:
                        await ack(redis, stream_key, group, msg_id)

            except Exception as exc:
                log.error("perception_consume_error", camera_id=camera_id, error=str(exc))
                await asyncio.sleep(1)

    async def _handle_perception(
        self, camera_id: str, msg_id: str, data: dict
    ) -> None:
        local_track_id_raw = data.get("track_id")
        reid_embedding_raw = data.get("reid_embedding")

        if local_track_id_raw is None or not reid_embedding_raw:
            return

        local_track_id = int(local_track_id_raw)

        # Deserialize embedding (may be JSON string or list)
        import json
        if isinstance(reid_embedding_raw, (str, bytes)):
            reid_embedding: list[float] = json.loads(reid_embedding_raw)
        else:
            reid_embedding = reid_embedding_raw

        # Use "{camera_id}:{local_track_id}" as the buffer key
        buffer_key = f"{camera_id}:{local_track_id}"

        person_id = await self._matcher.update(
            track_id=buffer_key,
            reid_embedding=reid_embedding,
            camera_id=camera_id,
        )

        if person_id is None:
            return

        # Look up DB Track UUID from camera + local_track_id
        track_uuid = await self._get_track_uuid(camera_id, local_track_id)
        if track_uuid is None:
            return

        # Update Track.global_person_id in DB
        await self._link_track(track_uuid, person_id, camera_id)

        # Check if a new session should be created
        session_id = await self._ensure_session(person_id)

        # Publish identity_resolved event
        await self._publish_identity_resolved(
            camera_id=camera_id,
            local_track_id=local_track_id,
            person_id=person_id,
            session_id=session_id,
        )

    async def _get_track_uuid(self, camera_id: str, local_track_id: int) -> uuid.UUID | None:
        from gym_shared.db.models import Track
        async with get_db() as db:
            result = await db.execute(
                select(Track.id)
                .where(Track.camera_id == camera_id)
                .where(Track.local_track_id == local_track_id)
                .where(Track.is_active == True)  # noqa: E712
                .order_by(Track.first_seen_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
        return row

    async def _link_track(
        self, track_uuid: uuid.UUID, person_id: uuid.UUID, camera_id: str
    ) -> None:
        from gym_shared.db.models import Track
        async with get_db() as db:
            await db.execute(
                update(Track.__table__)
                .where(Track.__table__.c.id == track_uuid)
                .values(global_person_id=person_id)
            )
        log.info("track_linked", track_id=str(track_uuid), person_id=str(person_id))

    async def _ensure_session(self, person_id: uuid.UUID) -> uuid.UUID | None:
        """Return existing active session or create a new one for the person."""
        from gym_shared.db.models import GymSession
        threshold = datetime.now(timezone.utc) - timedelta(
            hours=self._config.new_session_threshold_hours
        )
        async with get_db() as db:
            result = await db.execute(
                select(GymSession)
                .where(GymSession.person_id == person_id)
                .where(GymSession.started_at >= threshold)
                .where(GymSession.ended_at == None)  # noqa: E711
                .order_by(GymSession.started_at.desc())
                .limit(1)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing.id

            # Create new session
            session = GymSession(
                person_id=person_id,
                started_at=datetime.now(timezone.utc),
                primary_track_ids=[],
            )
            db.add(session)
            await db.flush()
            log.info("new_session_created", person_id=str(person_id), session_id=str(session.id))
            return session.id

    async def _publish_identity_resolved(
        self,
        camera_id: str,
        local_track_id: int,
        person_id: uuid.UUID,
        session_id: uuid.UUID | None,
    ) -> None:
        from gym_shared.events.publisher import publish

        event = IdentityResolvedEvent(
            camera_id=camera_id,
            track_id=local_track_id,
            person_id=str(person_id),
            confidence=1.0,
            method="reid",
        )
        # Publish identity event; include session_id as extra metadata in the raw dict
        payload = event.model_dump()
        payload["session_id"] = str(session_id) if session_id else ""

        stream_key = f"identity_resolved:{camera_id}"
        async with get_redis_ctx(self._config.redis_url) as redis:
            await publish(redis, stream_key, payload, maxlen=500)
        log.debug(
            "identity_resolved_published",
            track_id=local_track_id,
            person_id=str(person_id),
        )
