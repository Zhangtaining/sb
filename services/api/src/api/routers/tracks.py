"""GET /tracks/{track_id}/history and /tracks/{track_id}/replay."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from gym_shared.db.models import ExerciseSet, Track

from api.dependencies import DbSession
from api.schemas import ClipInfo, ExerciseSetSummary, ReplayResponse, TrackHistoryResponse

router = APIRouter(prefix="/tracks", tags=["tracks"])


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
