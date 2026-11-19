"""soft delete: partial index excluding deleted rows

Revision ID: 0004_soft_delete
Revises: 0003_api
Create Date: 2026-11-17 20:05:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_soft_delete"
down_revision: str | None = "0003_api"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_sample_notes_live",
        "sample_notes",
        ["created_at"],
        unique=False,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_sample_notes_live", table_name="sample_notes")
