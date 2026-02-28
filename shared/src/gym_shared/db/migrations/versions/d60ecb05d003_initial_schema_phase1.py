"""initial_schema_phase1

Revision ID: d60ecb05d003
Revises:
Create Date: 2026-02-28

Creates all Phase 1 tables and converts rep_events / pose_frames
to TimescaleDB hypertables. Enables pgvector and timescaledb extensions.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers
revision: str = "d60ecb05d003"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # ── cameras ───────────────────────────────────────────────────────────────
    op.create_table(
        "cameras",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("location_description", sa.String(255), nullable=False),
        sa.Column("rtsp_url", sa.Text, nullable=False),
        sa.Column("floor_zone", sa.String(64), nullable=False),
        sa.Column("homography_matrix", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── persons ───────────────────────────────────────────────────────────────
    op.create_table(
        "persons",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("face_embedding", Vector(512), nullable=True),
        sa.Column("reid_gallery", JSONB, nullable=False, server_default="{}"),
        sa.Column("notification_token", sa.String(512), nullable=True),
        sa.Column("websocket_session_id", sa.String(128), nullable=True),
        sa.Column("preferences", JSONB, nullable=False, server_default="{}"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── tracks ────────────────────────────────────────────────────────────────
    op.create_table(
        "tracks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "camera_id",
            sa.String(64),
            sa.ForeignKey("cameras.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("local_track_id", sa.Integer, nullable=False),
        sa.Column(
            "global_person_id",
            UUID(as_uuid=True),
            sa.ForeignKey("persons.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reid_embedding", Vector(256), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bbox_history", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index("ix_tracks_camera_id", "tracks", ["camera_id"])
    op.create_index("ix_tracks_global_person_id", "tracks", ["global_person_id"])
    op.create_index("ix_tracks_is_active", "tracks", ["is_active"])

    # ── gym_sessions ──────────────────────────────────────────────────────────
    op.create_table(
        "gym_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "person_id",
            UUID(as_uuid=True),
            sa.ForeignKey("persons.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("primary_track_ids", JSONB, nullable=False, server_default="[]"),
    )
    op.create_index("ix_gym_sessions_person_id", "gym_sessions", ["person_id"])
    op.create_index("ix_gym_sessions_started_at", "gym_sessions", ["started_at"])

    # ── exercise_sets ─────────────────────────────────────────────────────────
    op.create_table(
        "exercise_sets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("gym_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "track_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("exercise_type", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rep_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("form_score", sa.Float, nullable=True),
        sa.Column("alerts", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "classifier_confidence", sa.Float, nullable=False, server_default="0"
        ),
    )
    op.create_index("ix_exercise_sets_session_id", "exercise_sets", ["session_id"])
    op.create_index("ix_exercise_sets_track_id", "exercise_sets", ["track_id"])
    op.create_index("ix_exercise_sets_exercise_type", "exercise_sets", ["exercise_type"])

    # ── rep_events (TimescaleDB hypertable) ───────────────────────────────────
    op.create_table(
        "rep_events",
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True, nullable=False),
        sa.Column(
            "exercise_set_id",
            UUID(as_uuid=True),
            sa.ForeignKey("exercise_sets.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("rep_number", sa.Integer, nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("phase", sa.String(16), nullable=False),
        sa.Column("form_flags", JSONB, nullable=False, server_default="{}"),
        sa.Column("keypoint_snapshot", JSONB, nullable=False, server_default="{}"),
    )
    op.execute(
        "SELECT create_hypertable('rep_events', 'time', if_not_exists => TRUE)"
    )

    # ── pose_frames (TimescaleDB hypertable) ──────────────────────────────────
    op.create_table(
        "pose_frames",
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True, nullable=False),
        sa.Column(
            "track_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tracks.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("camera_id", sa.String(64), nullable=False),
        sa.Column("keypoints", JSONB, nullable=False),
        sa.Column("joint_angles", JSONB, nullable=False, server_default="{}"),
        sa.Column("frame_seq", sa.BigInteger, nullable=False),
    )
    op.execute(
        "SELECT create_hypertable('pose_frames', 'time', if_not_exists => TRUE)"
    )

    # ── conversations ─────────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "person_id",
            UUID(as_uuid=True),
            sa.ForeignKey("persons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("gym_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "context_type",
            sa.String(32),
            nullable=False,
            server_default="general",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── messages ──────────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tool_calls", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("token_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # ── gym_knowledge ─────────────────────────────────────────────────────────
    op.create_table(
        "gym_knowledge",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── notifications ─────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "person_id",
            UUID(as_uuid=True),
            sa.ForeignKey("persons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("gym_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "exercise_set_id",
            UUID(as_uuid=True),
            sa.ForeignKey("exercise_sets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_person_id", "notifications", ["person_id"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("gym_knowledge")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("pose_frames")
    op.drop_table("rep_events")
    op.drop_table("exercise_sets")
    op.drop_table("gym_sessions")
    op.drop_table("tracks")
    op.drop_table("persons")
    op.drop_table("cameras")
    op.execute("DROP EXTENSION IF EXISTS timescaledb")
    op.execute("DROP EXTENSION IF EXISTS vector")
