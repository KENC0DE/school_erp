"""academics: curriculum profiles and year selection

Revision ID: 0018_curriculum_profiles
Revises: 0017_subjects_sections
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_curriculum_profiles"
down_revision: str | None = "0017_subjects_sections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "academics_curriculum_profiles",
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("name_am", sa.String(length=120), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("term_system", sa.String(length=20), nullable=False, server_default="semester"),
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
        "uq_academics_curriculum_profiles_code_live",
        "academics_curriculum_profiles",
        ["code"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_academics_curriculum_profiles_sort_order",
        "academics_curriculum_profiles",
        ["sort_order"],
    )

    with op.batch_alter_table("academics_academic_years") as batch:
        batch.add_column(sa.Column("curriculum_profile_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_academics_academic_years_curriculum_profile",
            "academics_curriculum_profiles",
            ["curriculum_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "academics_curriculum_level_subjects",
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("academics_curriculum_profiles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
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


def downgrade() -> None:
    op.drop_table("academics_curriculum_level_subjects")
    with op.batch_alter_table("academics_academic_years") as batch:
        batch.drop_column("curriculum_profile_id")
    op.drop_index(
        "ix_academics_curriculum_profiles_sort_order",
        table_name="academics_curriculum_profiles",
    )
    op.drop_index(
        "uq_academics_curriculum_profiles_code_live",
        table_name="academics_curriculum_profiles",
    )
    op.drop_table("academics_curriculum_profiles")
