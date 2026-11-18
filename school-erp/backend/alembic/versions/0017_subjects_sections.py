"""academics: subjects, level assignments, subject groups and sections

Revision ID: 0017_subjects_sections
Revises: 0016_academic_years
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_subjects_sections"
down_revision: str | None = "0016_academic_years"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "academics_subjects",
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("name_am", sa.String(length=120), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        "uq_academics_subjects_code_live",
        "academics_subjects",
        ["code"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_academics_subjects_sort_order", "academics_subjects", ["sort_order"])

    op.create_table(
        "academics_level_subjects",
        sa.Column(
            "level_id",
            sa.Uuid(),
            sa.ForeignKey("academics_grade_levels.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("academics_subjects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("credit", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "academics_subject_groups",
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("name_am", sa.String(length=120), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        "uq_academics_subject_groups_code_live",
        "academics_subject_groups",
        ["code"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_academics_subject_groups_sort_order",
        "academics_subject_groups",
        ["sort_order"],
    )

    op.create_table(
        "academics_subject_group_members",
        sa.Column(
            "group_id",
            sa.Uuid(),
            sa.ForeignKey("academics_subject_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("academics_subjects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "academics_sections",
        sa.Column(
            "year_id",
            sa.Uuid(),
            sa.ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "level_id",
            sa.Uuid(),
            sa.ForeignKey("academics_grade_levels.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("name_am", sa.String(length=120), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="40"),
        sa.Column(
            "homeroom_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        "uq_academics_sections_year_level_code_live",
        "academics_sections",
        ["year_id", "level_id", "code"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_academics_sections_year_level",
        "academics_sections",
        ["year_id", "level_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_academics_sections_year_level", table_name="academics_sections")
    op.drop_index(
        "uq_academics_sections_year_level_code_live",
        table_name="academics_sections",
    )
    op.drop_table("academics_sections")
    op.drop_table("academics_subject_group_members")
    op.drop_index(
        "ix_academics_subject_groups_sort_order",
        table_name="academics_subject_groups",
    )
    op.drop_index(
        "uq_academics_subject_groups_code_live",
        table_name="academics_subject_groups",
    )
    op.drop_table("academics_subject_groups")
    op.drop_table("academics_level_subjects")
    op.drop_index("ix_academics_subjects_sort_order", table_name="academics_subjects")
    op.drop_index("uq_academics_subjects_code_live", table_name="academics_subjects")
    op.drop_table("academics_subjects")
