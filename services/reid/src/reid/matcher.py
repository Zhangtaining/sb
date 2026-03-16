"""Identity matcher — fuses OSNet appearance embeddings and ArcFace face embeddings."""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

import numpy as np
from gym_shared.logging import get_logger

from reid.config import ReidConfig
from reid.gallery_manager import GalleryManager

log = get_logger(__name__)


class IdentityMatcher:
    """Per-track embedding buffer with OSNet + ArcFace identity fusion.

    For each active track, collects up to `min_embeddings_before_match`
    OSNet embeddings, averages them, then queries the gallery. If a face
    crop is also available, ArcFace similarity is used as a higher-confidence
    override.
    """

    def __init__(self, config: ReidConfig, gallery: GalleryManager) -> None:
        self._config = config
        self._gallery = gallery
        # track_id -> deque of (timestamp, embedding)
        self._buffers: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=config.min_embeddings_before_match * 2)
        )
        # track_id -> resolved person_id (cached to avoid re-querying)
        self._resolved: dict[str, uuid.UUID] = {}
        # camera_id -> list of (track_id, last_seen_ts) for spatial-temporal gating
        self._recent_exits: dict[str, list[tuple[str, float]]] = defaultdict(list)

    def _average_embedding(self, track_id: str) -> list[float] | None:
        buf = self._buffers.get(track_id)
        if not buf or len(buf) < self._config.min_embeddings_before_match:
            return None
        embeddings = np.array([e for _, e in buf], dtype=np.float32)
        avg = np.mean(embeddings, axis=0)
        avg = avg / (np.linalg.norm(avg) + 1e-8)
        return avg.tolist()

    def _extract_face_embedding(self, face_crop) -> list[float] | None:
        """Extract ArcFace embedding from a face crop image (numpy BGR array)."""
        if face_crop is None:
            return None
        try:
            import insightface

            app = insightface.app.FaceAnalysis(providers=["CPUExecutionProvider"])
            app.prepare(ctx_id=-1)
            faces = app.get(face_crop)
            if not faces:
                return None
            face = max(
                faces,
                key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
            )
            return face.normed_embedding.tolist()
        except Exception as exc:
            log.warning("face_embedding_failed", error=str(exc))
            return None

    async def update(
        self,
        track_id: str,
        reid_embedding: list[float],
        camera_id: str = "",
        face_crop=None,
    ) -> uuid.UUID | None:
        """Add a new OSNet embedding for a track and attempt identity resolution.

        Returns resolved person_id if match found, None otherwise.
        """
        # Already resolved — return cached result
        if track_id in self._resolved:
            return self._resolved[track_id]

        # Buffer the new embedding
        self._buffers[track_id].append((time.monotonic(), reid_embedding))

        # Not enough embeddings yet
        avg = self._average_embedding(track_id)
        if avg is None:
            return None

        # Try ArcFace first (higher confidence)
        if face_crop is not None:
            face_emb = self._extract_face_embedding(face_crop)
            if face_emb is not None:
                person_id = await self._match_face(face_emb, track_id, camera_id)
                if person_id:
                    return person_id

        # Fall back to OSNet gallery cache
        person_id = await self._gallery.get_from_cache(avg)
        if person_id:
            self._resolved[track_id] = person_id
            log.info(
                "identity_resolved_reid",
                track_id=track_id,
                person_id=str(person_id),
                camera_id=camera_id,
            )
            return person_id

        return None

    async def _match_face(
        self, face_emb: list[float], track_id: str, camera_id: str
    ) -> uuid.UUID | None:
        """Match against gallery using ArcFace similarity."""
        # For ArcFace we still use the same gallery cache mechanism
        # but with a higher threshold
        q = np.array(face_emb, dtype=np.float32)
        q_norm = q / (np.linalg.norm(q) + 1e-8)

        import json

        from gym_shared.redis_client import get_redis_ctx

        async with get_redis_ctx(self._config.redis_url) as redis:
            all_entries = await redis.hgetall("reid:gallery")

        best_person_id = None
        best_sim = -1.0
        for pid_bytes, emb_bytes in all_entries.items():
            pid = pid_bytes.decode() if isinstance(pid_bytes, bytes) else pid_bytes
            emb = json.loads(emb_bytes.decode() if isinstance(emb_bytes, bytes) else emb_bytes)
            g = np.array(emb, dtype=np.float32)
            sim = float(np.dot(q_norm, g))
            if sim > best_sim:
                best_sim = sim
                best_person_id = pid

        if best_sim >= self._config.face_similarity_threshold and best_person_id:
            person_id = uuid.UUID(best_person_id)
            self._resolved[track_id] = person_id
            log.info(
                "identity_resolved_face",
                track_id=track_id,
                person_id=str(person_id),
                camera_id=camera_id,
                similarity=round(best_sim, 4),
            )
            return person_id

        return None

    def clear_track(self, track_id: str, camera_id: str = "") -> None:
        """Remove track from all buffers when it goes inactive."""
        self._buffers.pop(track_id, None)
        if track_id in self._resolved:
            self._recent_exits[camera_id].append((track_id, time.monotonic()))
            del self._resolved[track_id]
        log.debug("track_cleared", track_id=track_id, camera_id=camera_id)

    def prune_recent_exits(self) -> None:
        """Remove exits older than spatial_temporal_window_seconds."""
        cutoff = time.monotonic() - self._config.spatial_temporal_window_seconds
        for camera_id in list(self._recent_exits.keys()):
            self._recent_exits[camera_id] = [
                (tid, ts) for tid, ts in self._recent_exits[camera_id] if ts > cutoff
            ]
