"""leave types, yearly balances and requests

Revision ID: 0024_leave
Revises: 0023_teaching_assignments
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_leave"
down_revision: str | None = "0023_teaching_assignments"
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
        "staff_leave_types",
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_am", sa.String(120)),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "annual_entitlement_units",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "counts_against_balance",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    op.create_index(
        "uq_staff_leave_types_code_live",
        "staff_leave_types",
        ["code"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index("ix_staff_leave_types_sort_order", "staff_leave_types", ["sort_order"])

    op.create_table(
        "staff_leave_balances",
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
            "leave_type_id",
            sa.Uuid(),
            sa.ForeignKey("staff_leave_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("entitled_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("carried_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("adjustment_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    op.create_index(
        "uq_staff_leave_balance_live",
        "staff_leave_balances",
        ["staff_id", "year_id", "leave_type_id"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index("ix_staff_leave_balances_staff", "staff_leave_balances", ["staff_id"])
    op.create_index("ix_staff_leave_balances_year", "staff_leave_balances", ["year_id"])
    op.create_index("ix_staff_leave_balances_type", "staff_leave_balances", ["leave_type_id"])

    op.create_table(
        "staff_leave_requests",
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
            "leave_type_id",
            sa.Uuid(),
            sa.ForeignKey("staff_leave_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_half_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("days_units", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column(
            "decided_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("decision_note", sa.Text()),
        *_business_columns(),
    )
    op.create_index("ix_staff_leave_requests_staff", "staff_leave_requests", ["staff_id"])
    op.create_index("ix_staff_leave_requests_year", "staff_leave_requests", ["year_id"])
    op.create_index("ix_staff_leave_requests_type", "staff_leave_requests", ["leave_type_id"])
    op.create_index("ix_staff_leave_requests_status", "staff_leave_requests", ["status"])
    op.create_index(
        "ix_staff_leave_requests_dates",
        "staff_leave_requests",
        ["start_date", "end_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_staff_leave_requests_dates", table_name="staff_leave_requests")
    op.drop_index("ix_staff_leave_requests_status", table_name="staff_leave_requests")
    op.drop_index("ix_staff_leave_requests_type", table_name="staff_leave_requests")
    op.drop_index("ix_staff_leave_requests_year", table_name="staff_leave_requests")
    op.drop_index("ix_staff_leave_requests_staff", table_name="staff_leave_requests")
    op.drop_table("staff_leave_requests")

    op.drop_index("ix_staff_leave_balances_type", table_name="staff_leave_balances")
    op.drop_index("ix_staff_leave_balances_year", table_name="staff_leave_balances")
    op.drop_index("ix_staff_leave_balances_staff", table_name="staff_leave_balances")
    op.drop_index("uq_staff_leave_balance_live", table_name="staff_leave_balances")
    op.drop_table("staff_leave_balances")

    op.drop_index("ix_staff_leave_types_sort_order", table_name="staff_leave_types")
    op.drop_index("uq_staff_leave_types_code_live", table_name="staff_leave_types")
    op.drop_table("staff_leave_types")
