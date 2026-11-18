"""academics: grade levels, stages and stage membership

Revision ID: 0015_academics
Revises: 0014_notifications
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_academics"
down_revision: str | None = "0014_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "academics_grade_levels",
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("name_am", sa.String(length=80), nullable=True),
        sa.Column("scope_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_starter", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.Uuid()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "uq_academics_grade_levels_code_live",
        "academics_grade_levels",
        ["code"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_academics_grade_levels_sort_order",
        "academics_grade_levels",
        ["sort_order"],
    )

    op.create_table(
        "academics_stages",
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("name_am", sa.String(length=80), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_starter", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.Uuid()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "uq_academics_stages_code_live",
        "academics_stages",
        ["code"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_academics_stages_sort_order", "academics_stages", ["sort_order"])

    op.create_table(
        "academics_stage_levels",
        sa.Column(
            "stage_id",
            sa.Uuid(),
            sa.ForeignKey("academics_stages.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "level_id",
            sa.Uuid(),
            sa.ForeignKey("academics_grade_levels.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("academics_stage_levels")
    op.drop_index("ix_academics_stages_sort_order", table_name="academics_stages")
    op.drop_index("uq_academics_stages_code_live", table_name="academics_stages")
    op.drop_table("academics_stages")
    op.drop_index("ix_academics_grade_levels_sort_order", table_name="academics_grade_levels")
    op.drop_index("uq_academics_grade_levels_code_live", table_name="academics_grade_levels")
    op.drop_table("academics_grade_levels")
