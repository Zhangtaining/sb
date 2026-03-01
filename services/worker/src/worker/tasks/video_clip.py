"""Celery task: save a 5-second H.264 video clip from the rolling frame buffer to MinIO."""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import av
import redis as sync_redis
from minio import Minio
from sqlalchemy import select

from gym_shared.db.models import ExerciseSet
from gym_shared.db.session import get_db
from gym_shared.logging import get_logger

from worker.app import app
from worker.config import build_config

log = get_logger(__name__)

# A clip captures the 5 seconds of frames surrounding the alert (75 frames at 15 FPS)
_CLIP_FRAMES = 75
_CLIP_FPS = 15


def _get_minio(cfg) -> Minio:
    return Minio(
        cfg.minio_endpoint,
        access_key=cfg.minio_access_key,
        secret_key=cfg.minio_secret_key,
        secure=cfg.minio_secure,
    )


def _ensure_bucket(client: Minio, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def _build_clip(jpeg_frames: list[bytes], fps: int) -> bytes:
    """Encode a list of JPEG frames into an H.264 MP4 in memory."""
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mp4") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "23", "preset": "fast"}

        for jpeg in jpeg_frames:
            img_buf = io.BytesIO(jpeg)
            with av.open(img_buf, mode="r") as img_container:
                for frame in img_container.decode(video=0):
                    frame = frame.reformat(format="yuv420p")
                    for pkt in stream.encode(frame):
                        container.mux(pkt)

        # Flush encoder
        for pkt in stream.encode():
            container.mux(pkt)

    buf.seek(0)
    return buf.read()


@app.task(bind=True, max_retries=3, default_retry_delay=5)
def save_clip(
    self,
    camera_id: str,
    track_id: str,
    exercise_set_id: str,
    timestamp_ns: int,
) -> str | None:
    """Retrieve frame buffer from Redis, encode H.264 clip, upload to MinIO.

    Returns the presigned URL of the saved clip, or None on failure.
    """
    cfg = build_config()
    log.info(
        "save_clip_started",
        camera_id=camera_id,
        track_id=track_id,
        exercise_set_id=exercise_set_id,
    )

    # ── 1. Fetch frames from Redis buffer ─────────────────────────────────────
    buffer_key = f"buffer:{camera_id}"
    r = sync_redis.from_url(cfg.redis_url, decode_responses=False)
    try:
        total = r.llen(buffer_key)
        if total == 0:
            log.warning("save_clip_buffer_empty", camera_id=camera_id)
            return None
        # Take the most recent _CLIP_FRAMES frames
        start = max(0, total - _CLIP_FRAMES)
        jpeg_frames = r.lrange(buffer_key, start, -1)
    finally:
        r.close()

    if not jpeg_frames:
        log.warning("save_clip_no_frames", camera_id=camera_id)
        return None

    # ── 2. Encode H.264 MP4 ───────────────────────────────────────────────────
    try:
        mp4_bytes = _build_clip(jpeg_frames, _CLIP_FPS)
    except Exception as exc:
        log.error("save_clip_encode_error", error=str(exc))
        raise self.retry(exc=exc)

    # ── 3. Upload to MinIO ────────────────────────────────────────────────────
    minio = _get_minio(cfg)
    _ensure_bucket(minio, cfg.minio_bucket_clips)

    ts = datetime.fromtimestamp(timestamp_ns / 1e9, tz=timezone.utc)
    object_name = (
        f"clips/{camera_id}/{ts.strftime('%Y/%m/%d')}/"
        f"{ts.strftime('%H%M%S')}_{uuid.uuid4().hex[:8]}.mp4"
    )

    try:
        minio.put_object(
            cfg.minio_bucket_clips,
            object_name,
            io.BytesIO(mp4_bytes),
            length=len(mp4_bytes),
            content_type="video/mp4",
        )
    except Exception as exc:
        log.error("save_clip_upload_error", error=str(exc))
        raise self.retry(exc=exc)

    # Presigned URL valid for 7 days
    clip_url = minio.presigned_get_object(cfg.minio_bucket_clips, object_name)
    log.info("save_clip_uploaded", object_name=object_name, url=clip_url[:80])

    # ── 4. Update ExerciseSet.alerts in DB ───────────────────────────────────
    import asyncio

    async def _update_db() -> None:
        set_uuid = uuid.UUID(exercise_set_id)
        async with get_db() as db:
            result = await db.execute(
                select(ExerciseSet).where(ExerciseSet.id == set_uuid)
            )
            ex_set = result.scalar_one_or_none()
            if ex_set is not None:
                alerts = dict(ex_set.alerts or {})
                alerts["clip_url"] = clip_url
                ex_set.alerts = alerts
                await db.commit()
                log.info("save_clip_db_updated", exercise_set_id=exercise_set_id)

    asyncio.run(_update_db())
    return clip_url
