"""GET /tracks/{track_id}/history and /tracks/{track_id}/replay."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from gym_shared.db.models import ExerciseSet, Track

from gym_shared.settings import settings

from api.dependencies import DbSession
from api.schemas import ClipInfo, ExerciseSetSummary, ReplayResponse, TrackHistoryResponse, TrackStatusResponse

router = APIRouter(prefix="/tracks", tags=["tracks"])
cameras_router = APIRouter(prefix="/cameras", tags=["cameras"])


async def _get_track(db: DbSession, track_id: uuid.UUID) -> Track:
    result = await db.execute(select(Track).where(Track.id == track_id))
    track = result.scalar_one_or_none()
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
    return track


@router.get("/{track_id}/history", response_model=TrackHistoryResponse)
async def get_track_history(track_id: uuid.UUID, db: DbSession) -> TrackHistoryResponse:
    await _get_track(db, track_id)

    result = await db.execute(
        select(ExerciseSet)
        .where(ExerciseSet.track_id == track_id)
        .order_by(ExerciseSet.started_at)
    )
    sets = result.scalars().all()

    return TrackHistoryResponse(
        track_id=track_id,
        sets=[
            ExerciseSetSummary(
                id=s.id,
                exercise_type=s.exercise_type,
                rep_count=s.rep_count,
                form_score=s.form_score,
                started_at=s.started_at,
                ended_at=s.ended_at,
                alerts=s.alerts or None,
            )
            for s in sets
        ],
    )


@router.get("/{track_id}/replay", response_model=ReplayResponse)
async def get_track_replay(track_id: uuid.UUID, db: DbSession) -> ReplayResponse:
    await _get_track(db, track_id)

    result = await db.execute(
        select(ExerciseSet)
        .where(ExerciseSet.track_id == track_id)
        .order_by(ExerciseSet.started_at)
    )
    sets = result.scalars().all()

    clips = [
        ClipInfo(
            exercise_set_id=s.id,
            exercise_type=s.exercise_type,
            started_at=s.started_at,
            url=s.alerts["clip_url"],
        )
        for s in sets
        if isinstance(s.alerts, dict) and s.alerts.get("clip_url")
    ]

    return ReplayResponse(track_id=track_id, clips=clips)


# ── Camera visibility status ──────────────────────────────────────────────────

@router.get("/{track_id}/status", response_model=TrackStatusResponse)
async def get_track_status(
    track_id: uuid.UUID,
    request: Request,
    db: DbSession,
) -> TrackStatusResponse:
    """Returns camera and user visibility status for this track.

    - camera_online: camera is running and sending frames (camera_alive key present)
    - user_visible: this specific track was detected within the last 10 seconds

    If the track doesn't exist in the DB yet (new user), falls back to checking
    the first configured camera so the indicator still reflects real camera state.
    """
    redis = request.app.state.redis

    result = await db.execute(select(Track).where(Track.id == track_id))
    track = result.scalar_one_or_none()

    if track is not None:
        camera_id = track.camera_id
        user_visible = await redis.exists(f"track_seen:{track_id}") > 0
    else:
        # Track not in DB yet — check the first configured camera, user not visible
        camera_id = settings.camera_id_list[0] if settings.camera_id_list else "cam-01"
        user_visible = False

    camera_online = await redis.exists(f"camera_alive:{camera_id}") > 0
    return TrackStatusResponse(
        track_id=track_id,
        camera_online=camera_online,
        user_visible=user_visible,
    )


# ── Camera status (no track_id needed) ────────────────────────────────────────

from fastapi import Request
from pydantic import BaseModel as _BaseModel


@cameras_router.get("/{camera_id}/status")
async def get_camera_status(camera_id: str, request: Request) -> dict:
    """Returns camera online/person-detected status. No track_id required."""
    redis = request.app.state.redis
    camera_online = await redis.exists(f"camera_alive:{camera_id}") > 0
    person_detected = await redis.exists(f"camera_has_person:{camera_id}") > 0
    return {"camera_id": camera_id, "camera_online": camera_online, "person_detected": person_detected}


# ── Active exercise hint ───────────────────────────────────────────────────────


class ActiveExerciseRequest(_BaseModel):
    exercise_name: str   # snake_case, e.g. "squat"
    camera_id: str = "cam-01"


@router.post("/{track_id}/active-exercise", status_code=200)
async def set_active_exercise(
    track_id: str,
    body: ActiveExerciseRequest,
    request: Request,
):
    """Pin the active exercise for a camera so the exercise service tracks it immediately."""
    redis = request.app.state.redis
    key = f"active_exercise:{body.camera_id}"
    # TTL of 10 minutes — clears automatically after a set is done
    await redis.set(key, body.exercise_name, ex=600)
    # Store the user's UUID so exercise events are routed back to this client
    await redis.set(f"active_session_track:{body.camera_id}", str(track_id), ex=600)
    return {"camera_id": body.camera_id, "active_exercise": body.exercise_name}


@router.delete("/{track_id}/active-exercise", status_code=200)
async def clear_active_exercise(
    track_id: str,
    camera_id: str = "cam-01",
    request: Request = None,
):
    """Clear the active exercise hint so the classifier takes over again."""
    redis = request.app.state.redis
    await redis.delete(f"active_exercise:{camera_id}")
    await redis.delete(f"active_session_track:{camera_id}")
    return {"cleared": True}
