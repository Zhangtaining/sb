"""Pydantic response schemas for the API."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class SessionResponse(BaseModel):
    id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    total_reps: int
    form_score: float | None  # average form score across all sets, 0–1

    model_config = {"from_attributes": True}


class ExerciseSetSummary(BaseModel):
    id: uuid.UUID
    exercise_type: str
    rep_count: int
    form_score: float | None
    started_at: datetime
    ended_at: datetime | None
    alerts: dict | None

    model_config = {"from_attributes": True}


class TrackHistoryResponse(BaseModel):
    track_id: uuid.UUID
    sets: list[ExerciseSetSummary]


class ClipInfo(BaseModel):
    exercise_set_id: uuid.UUID
    exercise_type: str
    started_at: datetime
    url: str


class ReplayResponse(BaseModel):
    track_id: uuid.UUID
    clips: list[ClipInfo]
