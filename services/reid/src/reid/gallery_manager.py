"""Person embedding gallery — DB-backed with Redis hot cache."""
from __future__ import annotations

import json
import uuid
from typing import Any

import numpy as np
from gym_shared.logging import get_logger
from gym_shared.redis_client import get_redis_ctx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

log = get_logger(__name__)

_GALLERY_REDIS_KEY = "reid:gallery"


class GalleryManager:
    """Manages the OSNet ReID embedding gallery.

    Each person has a list of appearance embeddings stored in
    persons.reid_gallery (JSONB). The gallery is hot-cached in Redis
    for sub-ms in-memory cosine matching.
    """

    def __init__(self, config) -> None:
        self._config = config

    # ── DB operations ─────────────────────────────────────────────────────────

    async def upsert_embedding(
        self, db: AsyncSession, person_id: uuid.UUID, reid_embedding: list[float]
    ) -> None:
        """Append a new OSNet embedding to a person's gallery in the DB."""
        from gym_shared.db.models import Person

        person = await db.get(Person, person_id)
        if person is None:
            log.warning("upsert_embedding_person_not_found", person_id=str(person_id))
            return

        gallery: list[list[float]] = person.reid_gallery if isinstance(person.reid_gallery, list) else []
        gallery.append(reid_embedding)
        # Keep at most 50 embeddings per person
        if len(gallery) > 50:
            gallery = gallery[-50:]

        await db.execute(
            update(Person.__table__)
            .where(Person.__table__.c.id == person_id)
            .values(reid_gallery=gallery)
        )
        log.debug("embedding_upserted", person_id=str(person_id), gallery_size=len(gallery))

    async def search_gallery(
        self, db: AsyncSession, query_embedding: list[float], top_k: int = 5
    ) -> list[tuple[uuid.UUID, float]]:
        """Cosine similarity search against all persons in DB.

        Returns list of (person_id, similarity) sorted descending.
        """
        from gym_shared.db.models import Person

        result = await db.execute(select(Person.id, Person.reid_gallery))
        rows = result.fetchall()

        if not rows:
            return []

        q = np.array(query_embedding, dtype=np.float32)
        q_norm = q / (np.linalg.norm(q) + 1e-8)

        matches: list[tuple[uuid.UUID, float]] = []
        for person_id, gallery in rows:
            if not gallery:
                continue
            embeddings = np.array(gallery, dtype=np.float32)
            # Average gallery embeddings
            avg = np.mean(embeddings, axis=0)
            avg = avg / (np.linalg.norm(avg) + 1e-8)
            similarity = float(np.dot(q_norm, avg))
            matches.append((person_id, similarity))

        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:top_k]

    # ── Redis cache operations ─────────────────────────────────────────────────

    async def refresh_cache(self, db: AsyncSession) -> None:
        """Load all person embeddings into Redis for fast lookup."""
        from gym_shared.db.models import Person

        result = await db.execute(select(Person.id, Person.reid_gallery, Person.face_embedding))
        rows = result.fetchall()

        async with get_redis_ctx(self._config.redis_url) as redis:
            pipe = redis.pipeline()
            pipe.delete(_GALLERY_REDIS_KEY)
            for person_id, gallery, _ in rows:
                if not gallery:
                    continue
                embeddings = np.array(gallery, dtype=np.float32)
                avg = np.mean(embeddings, axis=0)
                avg = avg / (np.linalg.norm(avg) + 1e-8)
                pipe.hset(_GALLERY_REDIS_KEY, str(person_id), json.dumps(avg.tolist()))
            await pipe.execute()

        log.info("gallery_cache_refreshed", person_count=len(rows))

    async def get_from_cache(
        self, query_embedding: list[float]
    ) -> uuid.UUID | None:
        """Cosine similarity against Redis cache. Returns person_id or None."""
        q = np.array(query_embedding, dtype=np.float32)
        q_norm = q / (np.linalg.norm(q) + 1e-8)

        async with get_redis_ctx(self._config.redis_url) as redis:
            all_entries: dict[bytes, bytes] = await redis.hgetall(_GALLERY_REDIS_KEY)

        if not all_entries:
            return None

        best_person_id: uuid.UUID | None = None
        best_similarity = -1.0

        for person_id_bytes, embedding_bytes in all_entries.items():
            person_id_str = (
                person_id_bytes.decode() if isinstance(person_id_bytes, bytes) else person_id_bytes
            )
            embedding = json.loads(
                embedding_bytes.decode() if isinstance(embedding_bytes, bytes) else embedding_bytes
            )
            g = np.array(embedding, dtype=np.float32)
            similarity = float(np.dot(q_norm, g))
            if similarity > best_similarity:
                best_similarity = similarity
                best_person_id = uuid.UUID(person_id_str)

        if best_similarity >= self._config.reid_similarity_threshold:
            log.debug(
                "cache_match_found",
                person_id=str(best_person_id),
                similarity=round(best_similarity, 4),
            )
            return best_person_id

        return None
