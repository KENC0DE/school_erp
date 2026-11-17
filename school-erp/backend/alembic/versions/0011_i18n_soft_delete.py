"""i18n: soft-deleted school overrides

Revision ID: 0011_i18n_soft_delete
Revises: 0010_custom_fields
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_i18n_soft_delete"
down_revision: str | None = "0010_custom_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "translation_entries", sa.Column("deleted_at", sa.DateTime(timezone=True))
    )
    op.add_column("translation_entries", sa.Column("deleted_by", sa.Uuid()))
    op.add_column(
        "translation_entries",
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("translation_entries", "row_version")
    op.drop_column("translation_entries", "deleted_by")
    op.drop_column("translation_entries", "deleted_at")
