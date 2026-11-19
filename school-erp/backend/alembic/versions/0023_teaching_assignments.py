"""staff teaching assignments: teacher, subject, section and academic year

Revision ID: 0023_teaching_assignments
Revises: 0022_staff
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_teaching_assignments"
down_revision: str | None = "0022_staff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIVE_WHERE = sa.text("deleted_at IS NULL")


def upgrade() -> None:
    op.create_table(
        "staff_teaching_assignments",
        sa.Column(
            "staff_id",
            sa.Uuid(),
            sa.ForeignKey("staff_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "year_id",
            sa.Uuid(),
            sa.ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            sa.Uuid(),
            sa.ForeignKey("academics_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("academics_subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text()),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.Uuid()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "uq_staff_teaching_assignment_live",
        "staff_teaching_assignments",
        ["staff_id", "year_id", "section_id", "subject_id"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index(
        "ix_staff_teaching_assignment_year",
        "staff_teaching_assignments",
        ["year_id"],
    )
    op.create_index(
        "ix_staff_teaching_assignment_section",
        "staff_teaching_assignments",
        ["section_id"],
    )
    op.create_index(
        "ix_staff_teaching_assignment_subject",
        "staff_teaching_assignments",
        ["subject_id"],
    )
    op.create_index(
        "ix_staff_teaching_assignment_staff",
        "staff_teaching_assignments",
        ["staff_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_staff_teaching_assignment_staff",
        table_name="staff_teaching_assignments",
    )
    op.drop_index(
        "ix_staff_teaching_assignment_subject",
        table_name="staff_teaching_assignments",
    )
    op.drop_index(
        "ix_staff_teaching_assignment_section",
        table_name="staff_teaching_assignments",
    )
    op.drop_index(
        "ix_staff_teaching_assignment_year",
        table_name="staff_teaching_assignments",
    )
    op.drop_index(
        "uq_staff_teaching_assignment_live",
        table_name="staff_teaching_assignments",
    )
    op.drop_table("staff_teaching_assignments")
