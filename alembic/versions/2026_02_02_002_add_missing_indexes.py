"""Add missing indexes for query performance.

Revision ID: 002
Revises: 001
Create Date: 2026-02-02

Adds indexes for:
- story_roles.story_id (for loading roles by story)
- voice_pool_members.voice_id (for finding pools by voice)
- jobs(status, created_at) composite (for queue queries)
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Index for loading roles by story (JOIN queries)
    op.create_index("ix_story_roles_story_id", "story_roles", ["story_id"])

    # Index for finding pools containing a voice
    op.create_index("ix_voice_pool_members_voice_id", "voice_pool_members", ["voice_id"])

    # Composite index for queue queries: WHERE status = 'queued' ORDER BY created_at
    op.create_index("ix_jobs_status_created_at", "jobs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_status_created_at", table_name="jobs")
    op.drop_index("ix_voice_pool_members_voice_id", table_name="voice_pool_members")
    op.drop_index("ix_story_roles_story_id", table_name="story_roles")
