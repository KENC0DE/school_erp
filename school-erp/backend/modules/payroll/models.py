"""Payroll configuration and payslips (P3-05, optional sub-module of staff).

Rates are configuration, never constants: a rule set stores the tax and pension
rules a school's accountant validated. Money is integer santim throughout.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from core.db.base import BusinessModel
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

LIVE_INDEX = {
    "sqlite_where": text("deleted_at IS NULL"),
    "postgresql_where": text("deleted_at IS NULL"),
}


class PayrollComponent(BusinessModel):
    """A reusable earning or deduction, such as a housing allowance."""

    __tablename__ = "payroll_components"
    __table_args__ = (
        Index("uq_payroll_components_code_live", "code", unique=True, **LIVE_INDEX),
        Index("ix_payroll_components_sort_order", "sort_order"),
    )

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="earning")
    is_taxable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_pensionable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)


class PayrollStaffComponent(BusinessModel):
    """A component assigned to one staff member, fixed or as a basic-salary rate."""

    __tablename__ = "payroll_staff_components"
    __table_args__ = (
        Index(
            "uq_payroll_staff_component_live",
            "staff_id",
            "component_id",
            "starts_on",
            unique=True,
            **LIVE_INDEX,
        ),
        Index("ix_payroll_staff_components_staff", "staff_id"),
        Index("ix_payroll_staff_components_component", "component_id"),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    component_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_components.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount_santim: Mapped[int | None] = mapped_column(BigInteger)
    rate_basis_points: Mapped[int | None] = mapped_column(Integer)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class PayrollRuleSet(BusinessModel):
    """A dated, versioned bundle of tax and pension rules."""

    __tablename__ = "payroll_rule_sets"
    __table_args__ = (
        Index("uq_payroll_rule_sets_code_live", "code", unique=True, **LIVE_INDEX),
        Index("ix_payroll_rule_sets_status", "status"),
        Index("ix_payroll_rule_sets_effective", "effective_from", "effective_to"),
    )

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # The school's accountant must confirm the shipped/configurable rates. The
    # flag is surfaced everywhere so unverified rules are never mistaken for law.
    verified_by_accountant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)


class PayrollRule(BusinessModel):
    """One income-tax, pension or other rule inside a rule set."""

    __tablename__ = "payroll_rules"
    __table_args__ = (
        Index("uq_payroll_rules_key_live", "rule_set_id", "key", unique=True, **LIVE_INDEX),
        Index("ix_payroll_rules_set", "rule_set_id"),
    )

    rule_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_rule_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    payer: Mapped[str] = mapped_column(String(20), nullable=False, default="employee")
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="percent")
    base: Mapped[str] = mapped_column(String(20), nullable=False, default="gross")
    rate_basis_points: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)


class PayrollRuleBracket(BusinessModel):
    """One slice of a progressive rule. ``upper_santim`` is exclusive."""

    __tablename__ = "payroll_rule_brackets"
    __table_args__ = (Index("ix_payroll_rule_brackets_rule", "rule_id", "lower_santim"),)

    rule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    lower_santim: Mapped[int] = mapped_column(BigInteger, nullable=False)
    upper_santim: Mapped[int | None] = mapped_column(BigInteger)
    rate_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PayrollRun(BusinessModel):
    """One payroll period, calculated from a frozen rule set."""

    __tablename__ = "payroll_runs"
    __table_args__ = (
        Index("uq_payroll_runs_period_live", "period_year", "period_month", unique=True, **LIVE_INDEX),
        Index("ix_payroll_runs_status", "status"),
    )

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_rule_sets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    payslip_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gross_santim: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    deductions_santim: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    net_santim: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    employer_santim: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class PayrollPayslip(BusinessModel):
    """One staff member's immutable-by-finalization result for a run.

    The staff number and name are snapshots: a later rename must not rewrite
    history. Payslip lines hold the audit-ready breakdown.
    """

    __tablename__ = "payroll_payslips"
    __table_args__ = (
        Index("uq_payroll_payslip_run_staff_live", "run_id", "staff_id", unique=True, **LIVE_INDEX),
        Index("ix_payroll_payslips_staff", "staff_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_contracts.id", ondelete="SET NULL"),
    )
    staff_number: Mapped[str] = mapped_column(String(40), nullable=False)
    staff_name: Mapped[str] = mapped_column(String(240), nullable=False)
    base_salary_santim: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    gross_santim: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    taxable_santim: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    pensionable_santim: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_deductions_santim: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    net_santim: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    employer_contributions_santim: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)


class PayrollPayslipLine(BusinessModel):
    """One earning, deduction or employer contribution line on a payslip."""

    __tablename__ = "payroll_payslip_lines"
    __table_args__ = (Index("ix_payroll_payslip_lines_payslip", "payslip_id", "sort_order"),)

    payslip_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payroll_payslips.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="rule")
    rule_key: Mapped[str | None] = mapped_column(String(40))
    amount_santim: Mapped[int] = mapped_column(BigInteger, nullable=False)
    base_santim: Mapped[int | None] = mapped_column(BigInteger)
    rate_basis_points: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


__all__ = [
    "PayrollComponent",
    "PayrollPayslip",
    "PayrollPayslipLine",
    "PayrollRule",
    "PayrollRuleBracket",
    "PayrollRuleSet",
    "PayrollRun",
    "PayrollStaffComponent",
]
