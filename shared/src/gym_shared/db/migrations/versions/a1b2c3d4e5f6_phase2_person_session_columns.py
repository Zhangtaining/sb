"""phase2_person_session_columns

Revision ID: a1b2c3d4e5f6
Revises: d60ecb05d003
Create Date: 2026-03-15

Adds Phase 2 columns:
- persons.goals (JSONB)
- persons.injury_notes (TEXT)
- gym_sessions.workout_plan (JSONB)
- ivfflat vector indexes on persons.face_embedding and gym_knowledge.embedding
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "d60ecb05d003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── persons: add goals + injury_notes ─────────────────────────────────────
    op.add_column(
        "persons",
        sa.Column("goals", JSONB, nullable=False, server_default="'[]'::jsonb"),
    )
    op.add_column(
        "persons",
        sa.Column("injury_notes", sa.Text, nullable=True),
    )

    # ── gym_sessions: add workout_plan ────────────────────────────────────────
    op.add_column(
        "gym_sessions",
        sa.Column("workout_plan", JSONB, nullable=True),
    )

    # ── vector indexes for fast cosine similarity search ──────────────────────
    # ivfflat requires at least one row to set lists; use a small lists=1 for dev.
    # Increase lists to ~sqrt(rows) in production.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_persons_face_embedding "
        "ON persons USING ivfflat (face_embedding vector_cosine_ops) WITH (lists = 1) "
        "WHERE face_embedding IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_gym_knowledge_embedding "
        "ON gym_knowledge USING ivfflat (embedding vector_cosine_ops) WITH (lists = 1) "
        "WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_gym_knowledge_embedding")
    op.execute("DROP INDEX IF EXISTS ix_persons_face_embedding")
    op.drop_column("gym_sessions", "workout_plan")
    op.drop_column("persons", "injury_notes")
    op.drop_column("persons", "goals")
