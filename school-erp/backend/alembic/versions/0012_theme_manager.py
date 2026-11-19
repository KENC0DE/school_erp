"""themes: manager metadata, soft delete and per-user choice

Revision ID: 0012_theme_manager
Revises: 0011_i18n_soft_delete
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_theme_manager"
down_revision: str | None = "0011_i18n_soft_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("themes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("description", sa.String(length=500), nullable=True))
        batch_op.add_column(
            sa.Column("source", sa.String(length=20), nullable=False, server_default="builtin")
        )
        batch_op.add_column(sa.Column("source_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("created_by", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("updated_by", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("deleted_by", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"))

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("theme_key", sa.String(length=60), nullable=True))
        batch_op.add_column(
            sa.Column("theme_mode", sa.String(length=10), nullable=False, server_default="light")
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("theme_mode")
        batch_op.drop_column("theme_key")

    with op.batch_alter_table("themes", schema=None) as batch_op:
        batch_op.drop_column("row_version")
        batch_op.drop_column("deleted_by")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("updated_by")
        batch_op.drop_column("created_by")
        batch_op.drop_column("source_url")
        batch_op.drop_column("source")
        batch_op.drop_column("description")
