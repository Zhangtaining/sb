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


# ── Phase 2: Conversations ─────────────────────────────────────────────────────

class ConversationCreateRequest(BaseModel):
    person_id: uuid.UUID
    session_id: uuid.UUID | None = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    session_id: uuid.UUID | None
    started_at: datetime

    model_config = {"from_attributes": True}


class MessageRequest(BaseModel):
    text: str


class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    user_message: str
    assistant_response: str


class TrackStatusResponse(BaseModel):
    track_id: uuid.UUID
    camera_online: bool   # camera is running and sending frames
    user_visible: bool    # this track was actively detected in the last 10s
