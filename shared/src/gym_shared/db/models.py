"""SQLAlchemy 2.0 ORM models for the Smart Gym System.

All models use the modern Mapped[T] / mapped_column() style.
TimescaleDB hypertable conversion is handled in Alembic migrations (T04),
not here — these are standard SQLAlchemy table definitions.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.utcnow()


# ── Camera ────────────────────────────────────────────────────────────────────

class Camera(Base):
    """Registered camera device."""

    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    location_description: Mapped[str] = mapped_column(String(255), nullable=False)
    rtsp_url: Mapped[str] = mapped_column(Text, nullable=False)
    floor_zone: Mapped[str] = mapped_column(String(64), nullable=False)
    homography_matrix: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )

    tracks: Mapped[list[Track]] = relationship("Track", back_populates="camera")

    def __repr__(self) -> str:
        return f"<Camera id={self.id!r} zone={self.floor_zone!r}>"


# ── Person ────────────────────────────────────────────────────────────────────

class Person(Base):
    """Registered gym member with biometric identity data.

    Note: face_embedding and reid_gallery are populated in Phase 2.
    """

    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    face_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(512), nullable=True
    )
    reid_gallery: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False,
        comment="List of OSNet 256-d embeddings from different appearances",
    )
    notification_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    websocket_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )

    tracks: Mapped[list[Track]] = relationship("Track", back_populates="person")
    sessions: Mapped[list[GymSession]] = relationship("GymSession", back_populates="person")
    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation", back_populates="person"
    )
    notifications: Mapped[list[Notification]] = relationship(
        "Notification", back_populates="person"
    )

    def __repr__(self) -> str:
        return f"<Person id={self.id} name={self.display_name!r}>"


# ── Track ─────────────────────────────────────────────────────────────────────

class Track(Base):
    """A detected person blob within a single camera's field of view.

    May be linked to a registered Person once ReID matches (Phase 2).
    Multiple tracks (across cameras or sessions) can link to the same Person.
    """

    __tablename__ = "tracks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    camera_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    local_track_id: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="ByteTrack integer ID within the camera",
    )
    global_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        comment="Populated by ReID service once identity is resolved",
    )
    reid_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(256), nullable=True,
        comment="OSNet 256-d L2-normalized appearance embedding",
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    bbox_history: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    camera: Mapped[Camera] = relationship("Camera", back_populates="tracks")
    person: Mapped[Person | None] = relationship("Person", back_populates="tracks")
    exercise_sets: Mapped[list[ExerciseSet]] = relationship(
        "ExerciseSet", back_populates="track"
    )
    pose_frames: Mapped[list[PoseFrame]] = relationship(
        "PoseFrame", back_populates="track"
    )

    def __repr__(self) -> str:
        return f"<Track id={self.id} camera={self.camera_id!r} local_id={self.local_track_id}>"


# ── GymSession ────────────────────────────────────────────────────────────────

class GymSession(Base):
    """One gym visit per person (entry to exit)."""

    __tablename__ = "gym_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        comment="Null for anonymous sessions (Phase 1)",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    primary_track_ids: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False,
        comment="UUIDs of all Tracks across cameras for this session",
    )

    person: Mapped[Person | None] = relationship("Person", back_populates="sessions")
    exercise_sets: Mapped[list[ExerciseSet]] = relationship(
        "ExerciseSet", back_populates="session"
    )
    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation", back_populates="session"
    )
    notifications: Mapped[list[Notification]] = relationship(
        "Notification", back_populates="session"
    )

    def __repr__(self) -> str:
        return f"<GymSession id={self.id} started={self.started_at}>"


# ── ExerciseSet ───────────────────────────────────────────────────────────────

class ExerciseSet(Base):
    """A single set of a single exercise type performed by a tracked person."""

    __tablename__ = "exercise_sets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gym_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracks.id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_type: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rep_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    form_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    alerts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False,
        comment="Form alerts fired + optional clip_url for video replay",
    )
    classifier_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    session: Mapped[GymSession] = relationship("GymSession", back_populates="exercise_sets")
    track: Mapped[Track] = relationship("Track", back_populates="exercise_sets")
    rep_events: Mapped[list[RepEvent]] = relationship(
        "RepEvent", back_populates="exercise_set"
    )

    def __repr__(self) -> str:
        return (
            f"<ExerciseSet id={self.id} exercise={self.exercise_type!r}"
            f" reps={self.rep_count}>"
        )


# ── RepEvent ──────────────────────────────────────────────────────────────────

class RepEvent(Base):
    """Individual rep record. Converted to TimescaleDB hypertable in migration."""

    __tablename__ = "rep_events"

    # TimescaleDB requires the partition key (time) to be part of the PK
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    exercise_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exercise_sets.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    rep_number: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    form_flags: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    keypoint_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    exercise_set: Mapped[ExerciseSet] = relationship("ExerciseSet", back_populates="rep_events")

    def __repr__(self) -> str:
        return f"<RepEvent set={self.exercise_set_id} rep={self.rep_number} t={self.time}>"


# ── PoseFrame ─────────────────────────────────────────────────────────────────

class PoseFrame(Base):
    """Raw pose keypoint snapshot per frame. TimescaleDB hypertable in migration."""

    __tablename__ = "pose_frames"

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracks.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    camera_id: Mapped[str] = mapped_column(String(64), nullable=False)
    keypoints: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False,
        comment="List of 33 keypoints: [{x, y, z, visibility}]",
    )
    joint_angles: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False,
        comment="Pre-computed joint angles for downstream analysis",
    )
    frame_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)

    track: Mapped[Track] = relationship("Track", back_populates="pose_frames")

    def __repr__(self) -> str:
        return f"<PoseFrame track={self.track_id} t={self.time}>"


# ── Conversation / Message ────────────────────────────────────────────────────

class Conversation(Base):
    """LLM conversation thread per person."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gym_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    context_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="general",
        comment="'guidance' | 'planning' | 'general'",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )

    person: Mapped[Person] = relationship("Person", back_populates="conversations")
    session: Mapped[GymSession | None] = relationship(
        "GymSession", back_populates="conversations"
    )
    messages: Mapped[list[Message]] = relationship("Message", back_populates="conversation")

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} type={self.context_type!r}>"


class Message(Base):
    """Single message within a conversation."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="'user' | 'assistant' | 'system'",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    conversation: Mapped[Conversation] = relationship(
        "Conversation", back_populates="messages"
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role!r}>"


# ── GymKnowledge ──────────────────────────────────────────────────────────────

class GymKnowledge(Base):
    """RAG document store for gym knowledge base (Phase 3)."""

    __tablename__ = "gym_knowledge"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="'exercise_guide' | 'nutrition' | 'safety'",
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(384), nullable=True,
        comment="sentence-transformers all-MiniLM-L6-v2 embedding",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    def __repr__(self) -> str:
        return f"<GymKnowledge id={self.id} title={self.title!r}>"


# ── Notification ──────────────────────────────────────────────────────────────

class Notification(Base):
    """Audit log of all guidance messages sent to users."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gym_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    exercise_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exercise_sets.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="'push' | 'websocket' | 'display'",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    person: Mapped[Person] = relationship("Person", back_populates="notifications")
    session: Mapped[GymSession | None] = relationship(
        "GymSession", back_populates="notifications"
    )

    def __repr__(self) -> str:
        return f"<Notification id={self.id} channel={self.channel!r}>"
