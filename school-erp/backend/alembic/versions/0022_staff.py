"""staff: profiles, departments, positions, contracts and qualifications

Revision ID: 0022_staff
Revises: 0021_admissions
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_staff"
down_revision: str | None = "0021_admissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.Uuid()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    ]


def _live_index(name: str, table: str, columns: list[str], *, unique: bool = False) -> None:
    op.create_index(
        name,
        table,
        columns,
        unique=unique,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def upgrade() -> None:
    op.create_table(
        "staff_departments",
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("name_am", sa.String(length=120)),
        sa.Column(
            "parent_id",
            sa.Uuid(),
            sa.ForeignKey("staff_departments.id", ondelete="RESTRICT"),
        ),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_common_columns(),
    )
    _live_index("uq_staff_departments_code_live", "staff_departments", ["code"], unique=True)
    op.create_index("ix_staff_departments_sort_order", "staff_departments", ["sort_order"])

    op.create_table(
        "staff_positions",
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("name_am", sa.String(length=120)),
        sa.Column(
            "department_id",
            sa.Uuid(),
            sa.ForeignKey("staff_departments.id", ondelete="RESTRICT"),
        ),
        sa.Column("is_teaching", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_common_columns(),
    )
    _live_index("uq_staff_positions_code_live", "staff_positions", ["code"], unique=True)
    op.create_index("ix_staff_positions_department", "staff_positions", ["department_id"])
    op.create_index("ix_staff_positions_sort_order", "staff_positions", ["sort_order"])

    op.create_table(
        "staff_profiles",
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("persons.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("staff_number", sa.String(length=40), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column(
            "department_id",
            sa.Uuid(),
            sa.ForeignKey("staff_departments.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "position_id",
            sa.Uuid(),
            sa.ForeignKey("staff_positions.id", ondelete="RESTRICT"),
        ),
        sa.Column("hire_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("custom", sa.JSON()),
        *_common_columns(),
    )
    _live_index("uq_staff_profiles_number_live", "staff_profiles", ["staff_number"], unique=True)
    _live_index("uq_staff_profiles_person_live", "staff_profiles", ["person_id"], unique=True)
    _live_index("uq_staff_profiles_user_live", "staff_profiles", ["user_id"], unique=True)
    op.create_index("ix_staff_profiles_status", "staff_profiles", ["status"])
    op.create_index("ix_staff_profiles_department", "staff_profiles", ["department_id"])
    op.create_index("ix_staff_profiles_position", "staff_profiles", ["position_id"])

    op.create_table(
        "staff_contracts",
        sa.Column(
            "staff_id",
            sa.Uuid(),
            sa.ForeignKey("staff_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=30), nullable=False, server_default="permanent"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("salary_santim", sa.BigInteger()),
        sa.Column("notes", sa.Text()),
        *_common_columns(),
    )
    op.create_index("ix_staff_contracts_staff", "staff_contracts", ["staff_id"])
    op.create_index("ix_staff_contracts_status", "staff_contracts", ["status"])

    op.create_table(
        "staff_qualifications",
        sa.Column(
            "staff_id",
            sa.Uuid(),
            sa.ForeignKey("staff_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=30), nullable=False, server_default="education"),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("institution", sa.String(length=200)),
        sa.Column("field_of_study", sa.String(length=200)),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("result", sa.String(length=80)),
        sa.Column("notes", sa.Text()),
        *_common_columns(),
    )
    op.create_index("ix_staff_qualifications_staff", "staff_qualifications", ["staff_id"])

    op.create_table(
        "staff_number_sequences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("scope", name="uq_staff_number_sequences_scope"),
    )


def downgrade() -> None:
    op.drop_table("staff_number_sequences")
    op.drop_index("ix_staff_qualifications_staff", table_name="staff_qualifications")
    op.drop_table("staff_qualifications")
    op.drop_index("ix_staff_contracts_status", table_name="staff_contracts")
    op.drop_index("ix_staff_contracts_staff", table_name="staff_contracts")
    op.drop_table("staff_contracts")
    op.drop_index("ix_staff_profiles_position", table_name="staff_profiles")
    op.drop_index("ix_staff_profiles_department", table_name="staff_profiles")
    op.drop_index("ix_staff_profiles_status", table_name="staff_profiles")
    op.drop_index("uq_staff_profiles_user_live", table_name="staff_profiles")
    op.drop_index("uq_staff_profiles_person_live", table_name="staff_profiles")
    op.drop_index("uq_staff_profiles_number_live", table_name="staff_profiles")
    op.drop_table("staff_profiles")
    op.drop_index("ix_staff_positions_sort_order", table_name="staff_positions")
    op.drop_index("ix_staff_positions_department", table_name="staff_positions")
    op.drop_index("uq_staff_positions_code_live", table_name="staff_positions")
    op.drop_table("staff_positions")
    op.drop_index("ix_staff_departments_sort_order", table_name="staff_departments")
    op.drop_index("uq_staff_departments_code_live", table_name="staff_departments")
    op.drop_table("staff_departments")
