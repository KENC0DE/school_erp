"""staff attendance

Revision ID: 0027_staff_attendance
Revises: 0026_attendance
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_staff_attendance"
down_revision: str | None = "0026_attendance"
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
        "staff_attendance",
        sa.Column(
            "staff_id",
            sa.Uuid(),
            sa.ForeignKey("staff_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="present"),
        sa.Column("reason", sa.String(500)),
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
        "uq_staff_attendance_staff_date_live",
        "staff_attendance",
        ["staff_id", "date"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index("ix_staff_attendance_date", "staff_attendance", ["date"])
    op.create_index("ix_staff_attendance_staff_date", "staff_attendance", ["staff_id", "date"])
    op.create_index("ix_staff_attendance_status", "staff_attendance", ["status"])


def downgrade() -> None:
    op.drop_table("staff_attendance")
