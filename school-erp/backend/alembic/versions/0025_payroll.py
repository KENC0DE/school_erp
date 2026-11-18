"""payroll: components, rule sets, runs and payslips

Revision ID: 0025_payroll
Revises: 0024_leave
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_payroll"
down_revision: str | None = "0024_leave"
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


def _live_index(
    name: str,
    table: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    op.create_index(
        name,
        table,
        columns,
        unique=unique,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )


def upgrade() -> None:
    op.create_table(
        "payroll_components",
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_am", sa.String(120)),
        sa.Column("kind", sa.String(20), nullable=False, server_default="earning"),
        sa.Column("is_taxable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_pensionable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    _live_index("uq_payroll_components_code_live", "payroll_components", ["code"], unique=True)
    op.create_index("ix_payroll_components_sort_order", "payroll_components", ["sort_order"])

    op.create_table(
        "payroll_staff_components",
        sa.Column(
            "staff_id",
            sa.Uuid(),
            sa.ForeignKey("staff_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "component_id",
            sa.Uuid(),
            sa.ForeignKey("payroll_components.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount_santim", sa.BigInteger()),
        sa.Column("rate_basis_points", sa.Integer()),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date()),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    _live_index(
        "uq_payroll_staff_component_live",
        "payroll_staff_components",
        ["staff_id", "component_id", "starts_on"],
        unique=True,
    )
    op.create_index("ix_payroll_staff_components_staff", "payroll_staff_components", ["staff_id"])
    op.create_index(
        "ix_payroll_staff_components_component",
        "payroll_staff_components",
        ["component_id"],
    )

    op.create_table(
        "payroll_rule_sets",
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column(
            "verified_by_accountant",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    _live_index("uq_payroll_rule_sets_code_live", "payroll_rule_sets", ["code"], unique=True)
    op.create_index("ix_payroll_rule_sets_status", "payroll_rule_sets", ["status"])
    op.create_index(
        "ix_payroll_rule_sets_effective",
        "payroll_rule_sets",
        ["effective_from", "effective_to"],
    )

    op.create_table(
        "payroll_rules",
        sa.Column(
            "rule_set_id",
            sa.Uuid(),
            sa.ForeignKey("payroll_rule_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="other"),
        sa.Column("payer", sa.String(20), nullable=False, server_default="employee"),
        sa.Column("method", sa.String(20), nullable=False, server_default="percent"),
        sa.Column("base", sa.String(20), nullable=False, server_default="gross"),
        sa.Column("rate_basis_points", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    _live_index("uq_payroll_rules_key_live", "payroll_rules", ["rule_set_id", "key"], unique=True)
    op.create_index("ix_payroll_rules_set", "payroll_rules", ["rule_set_id"])

    op.create_table(
        "payroll_rule_brackets",
        sa.Column(
            "rule_id",
            sa.Uuid(),
            sa.ForeignKey("payroll_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("lower_santim", sa.BigInteger(), nullable=False),
        sa.Column("upper_santim", sa.BigInteger()),
        sa.Column("rate_basis_points", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_business_columns(),
    )
    op.create_index(
        "ix_payroll_rule_brackets_rule",
        "payroll_rule_brackets",
        ["rule_id", "lower_santim"],
    )

    op.create_table(
        "payroll_runs",
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column(
            "rule_set_id",
            sa.Uuid(),
            sa.ForeignKey("payroll_rule_sets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("payslip_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gross_santim", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("deductions_santim", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("net_santim", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("employer_santim", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("calculated_at", sa.DateTime(timezone=True)),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    _live_index(
        "uq_payroll_runs_period_live",
        "payroll_runs",
        ["period_year", "period_month"],
        unique=True,
    )
    op.create_index("ix_payroll_runs_status", "payroll_runs", ["status"])

    op.create_table(
        "payroll_payslips",
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "staff_id",
            sa.Uuid(),
            sa.ForeignKey("staff_profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "contract_id",
            sa.Uuid(),
            sa.ForeignKey("staff_contracts.id", ondelete="SET NULL"),
        ),
        sa.Column("staff_number", sa.String(40), nullable=False),
        sa.Column("staff_name", sa.String(240), nullable=False),
        sa.Column("base_salary_santim", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("gross_santim", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("taxable_santim", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("pensionable_santim", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "total_deductions_santim",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("net_santim", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "employer_contributions_santim",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    _live_index(
        "uq_payroll_payslip_run_staff_live",
        "payroll_payslips",
        ["run_id", "staff_id"],
        unique=True,
    )
    op.create_index("ix_payroll_payslips_staff", "payroll_payslips", ["staff_id"])

    op.create_table(
        "payroll_payslip_lines",
        sa.Column(
            "payslip_id",
            sa.Uuid(),
            sa.ForeignKey("payroll_payslips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="rule"),
        sa.Column("rule_key", sa.String(40)),
        sa.Column("amount_santim", sa.BigInteger(), nullable=False),
        sa.Column("base_santim", sa.BigInteger()),
        sa.Column("rate_basis_points", sa.Integer()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_business_columns(),
    )
    op.create_index(
        "ix_payroll_payslip_lines_payslip",
        "payroll_payslip_lines",
        ["payslip_id", "sort_order"],
    )


def downgrade() -> None:
    op.drop_index("ix_payroll_payslip_lines_payslip", table_name="payroll_payslip_lines")
    op.drop_table("payroll_payslip_lines")

    op.drop_index("ix_payroll_payslips_staff", table_name="payroll_payslips")
    op.drop_index("uq_payroll_payslip_run_staff_live", table_name="payroll_payslips")
    op.drop_table("payroll_payslips")

    op.drop_index("ix_payroll_runs_status", table_name="payroll_runs")
    op.drop_index("uq_payroll_runs_period_live", table_name="payroll_runs")
    op.drop_table("payroll_runs")

    op.drop_index("ix_payroll_rule_brackets_rule", table_name="payroll_rule_brackets")
    op.drop_table("payroll_rule_brackets")

    op.drop_index("ix_payroll_rules_set", table_name="payroll_rules")
    op.drop_index("uq_payroll_rules_key_live", table_name="payroll_rules")
    op.drop_table("payroll_rules")

    op.drop_index("ix_payroll_rule_sets_effective", table_name="payroll_rule_sets")
    op.drop_index("ix_payroll_rule_sets_status", table_name="payroll_rule_sets")
    op.drop_index("uq_payroll_rule_sets_code_live", table_name="payroll_rule_sets")
    op.drop_table("payroll_rule_sets")

    op.drop_index("ix_payroll_staff_components_component", table_name="payroll_staff_components")
    op.drop_index("ix_payroll_staff_components_staff", table_name="payroll_staff_components")
    op.drop_index("uq_payroll_staff_component_live", table_name="payroll_staff_components")
    op.drop_table("payroll_staff_components")

    op.drop_index("ix_payroll_components_sort_order", table_name="payroll_components")
    op.drop_index("uq_payroll_components_code_live", table_name="payroll_components")
    op.drop_table("payroll_components")
