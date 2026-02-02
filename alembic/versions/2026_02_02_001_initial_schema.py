"""Initial database schema.

Revision ID: 001
Revises:
Create Date: 2026-02-02

Creates tables for:
- stories: Main story metadata with UUID id and slug
- story_roles: Roles within a story
- story_lines: Individual lines in a story
- voices: Voice configurations
- voice_pools: Named groups of voices
- voice_pool_members: Mapping of voices to pools
- jobs: Async job queue for generation tasks
- story_generation_metadata: Caching metadata for incremental generation
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Stories table
    op.create_table(
        "stories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("language", sa.String(50), nullable=False, server_default="English"),
        sa.Column("default_voice_id", sa.String(100), nullable=False),
        sa.Column("casting", postgresql.JSONB, nullable=True),
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
            onupdate=sa.func.now(),
        ),
    )

    # Story roles table
    op.create_table(
        "story_roles",
        sa.Column(
            "story_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role_id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
    )

    # Story lines table
    op.create_table(
        "story_lines",
        sa.Column(
            "story_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("line_index", sa.Integer, primary_key=True),
        sa.Column("role_id", sa.Integer, nullable=False),
        sa.Column("line_text", sa.Text, nullable=False),
        sa.Column("extra", sa.String(500), nullable=True),
        sa.Column("actor_id", sa.String(100), nullable=True),
    )
    op.create_index("ix_story_lines_story_id", "story_lines", ["story_id"])

    # Voices table
    op.create_table(
        "voices",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("language", sa.String(50), nullable=False),
        sa.Column("instruction", sa.Text, nullable=False),
        sa.Column("sample_text", sa.Text, nullable=True),
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
            onupdate=sa.func.now(),
        ),
    )

    # Voice pools table
    op.create_table(
        "voice_pools",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Voice pool members table
    op.create_table(
        "voice_pool_members",
        sa.Column(
            "pool_id",
            sa.Integer,
            sa.ForeignKey("voice_pools.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "voice_id",
            sa.String(100),
            sa.ForeignKey("voices.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # Jobs table
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("voice_id", sa.String(100), nullable=True, index=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("output_path", sa.String(500), nullable=True),
        sa.Column("request_params", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Story generation metadata table (for incremental generation)
    op.create_table(
        "story_generation_metadata",
        sa.Column(
            "story_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("line_hashes", postgresql.JSONB, nullable=False),
        sa.Column("language", sa.String(50), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("story_generation_metadata")
    op.drop_table("jobs")
    op.drop_table("voice_pool_members")
    op.drop_table("voice_pools")
    op.drop_table("voices")
    op.drop_index("ix_story_lines_story_id", table_name="story_lines")
    op.drop_table("story_lines")
    op.drop_table("story_roles")
    op.drop_table("stories")
