"""attendance sessions and records

Revision ID: 0026_attendance
Revises: 0025_payroll
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_attendance"
down_revision: str | None = "0025_payroll"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIVE_WHERE = sa.text("deleted_at IS NULL")


def _business_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "attendance_sessions",
        sa.Column(
            "year_id",
            sa.Uuid(),
            sa.ForeignKey("academics_academic_years.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            sa.Uuid(),
            sa.ForeignKey("academics_sections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False, server_default="daily"),
        sa.Column("period", sa.Integer()),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("academics_subjects.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("notes", sa.Text()),
        sa.Column("status_changed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "status_changed_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        *_business_columns(),
    )
    op.create_index(
        "uq_attendance_sessions_scope_live",
        "attendance_sessions",
        ["year_id", "section_id", "date", "mode", "period"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index(
        "ix_attendance_sessions_section_date",
        "attendance_sessions",
        ["section_id", "date"],
    )
    op.create_index(
        "ix_attendance_sessions_year_date",
        "attendance_sessions",
        ["year_id", "date"],
    )
    op.create_index("ix_attendance_sessions_status", "attendance_sessions", ["status"])

    op.create_table(
        "attendance_records",
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="present"),
        sa.Column("reason", sa.String(500)),
        sa.Column("late_minutes", sa.Integer()),
        sa.Column("note", sa.Text()),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "recorded_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        *_business_columns(),
    )
    op.create_index(
        "uq_attendance_records_session_student_live",
        "attendance_records",
        ["session_id", "student_id"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index("ix_attendance_records_student", "attendance_records", ["student_id"])
    op.create_index(
        "ix_attendance_records_session_status",
        "attendance_records",
        ["session_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("attendance_records")
    op.drop_table("attendance_sessions")
