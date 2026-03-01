"""GET /sessions/{session_id} — session summary."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from gym_shared.db.models import ExerciseSet, GymSession

from api.dependencies import DbSession
from api.schemas import SessionResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: uuid.UUID, db: DbSession) -> SessionResponse:
    result = await db.execute(select(GymSession).where(GymSession.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    sets_result = await db.execute(
        select(ExerciseSet).where(ExerciseSet.session_id == session_id)
    )
    sets = sets_result.scalars().all()

    total_reps = sum(s.rep_count for s in sets)
    scored = [s.form_score for s in sets if s.form_score is not None]
    form_score = sum(scored) / len(scored) if scored else None

    return SessionResponse(
        id=session.id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        total_reps=total_reps,
        form_score=form_score,
    )
