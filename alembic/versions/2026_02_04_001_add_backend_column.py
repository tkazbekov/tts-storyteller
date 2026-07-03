"""Add backend column to voices table

Revision ID: 2026_02_04_001
Revises: 002
Create Date: 2026-02-04 08:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2026_02_04_001"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add backend column to voices table."""
    # Add backend column with default 'qwen'
    op.add_column(
        "voices",
        sa.Column("backend", sa.String(length=50), nullable=False, server_default="qwen"),
    )

    # Add index for efficient filtering by backend
    op.create_index(
        "ix_voices_backend",
        "voices",
        ["backend"],
    )

    # Add check constraint for valid backends
    op.create_check_constraint(
        "check_valid_backend",
        "voices",
        "backend IN ('qwen', 'vibevoice')",
    )


def downgrade() -> None:
    """Remove backend column from voices table."""
    # Drop check constraint
    op.drop_constraint("check_valid_backend", "voices", type_="check")

    # Drop index
    op.drop_index("ix_voices_backend", table_name="voices")

    # Drop column
    op.drop_column("voices", "backend")
