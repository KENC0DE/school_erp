"""Shared lookups, snapshots and engine adapters for payroll records."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from app.errors import NotFound
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payroll.engine import (
    Basis,
    Bracket,
    ComponentAmount,
    Payer,
    Rule,
    RuleKind,
    RuleMethod,
)
from modules.payroll.models import (
    PayrollComponent,
    PayrollPayslip,
    PayrollRule,
    PayrollRuleBracket,
    PayrollRuleSet,
    PayrollRun,
    PayrollStaffComponent,
)

MODULE = "payroll"


def _iso(value) -> str | None:  # type: ignore[no-untyped-def]
    return value.isoformat() if value else None


def _money(value: int | None) -> str | None:
    """Audit amounts as birr text so a reviewer can read them."""
    if value is None:
        return None
    return str((Decimal(value) / 100).quantize(Decimal("0.01")))


async def live_component(session: AsyncSession, component_id: uuid.UUID) -> PayrollComponent:
    row = (
        await session.execute(
            select(PayrollComponent).where(
                PayrollComponent.id == component_id,
                PayrollComponent.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The salary component does not exist",
            message_key="payroll.error.component_not_found",
        )
    return row


async def live_staff_component(
    session: AsyncSession,
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
) -> PayrollStaffComponent:
    row = (
        await session.execute(
            select(PayrollStaffComponent).where(
                PayrollStaffComponent.id == assignment_id,
                PayrollStaffComponent.staff_id == staff_id,
                PayrollStaffComponent.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The staff salary component does not exist",
            message_key="payroll.error.staff_component_not_found",
        )
    return row


async def live_rule_set(session: AsyncSession, rule_set_id: uuid.UUID) -> PayrollRuleSet:
    row = (
        await session.execute(
            select(PayrollRuleSet).where(
                PayrollRuleSet.id == rule_set_id,
                PayrollRuleSet.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The payroll rule set does not exist",
            message_key="payroll.error.rule_set_not_found",
        )
    return row


async def live_rule(
    session: AsyncSession,
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
) -> PayrollRule:
    row = (
        await session.execute(
            select(PayrollRule).where(
                PayrollRule.id == rule_id,
                PayrollRule.rule_set_id == rule_set_id,
                PayrollRule.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The payroll rule does not exist",
            message_key="payroll.error.rule_not_found",
        )
    return row


async def live_run(session: AsyncSession, run_id: uuid.UUID) -> PayrollRun:
    row = (
        await session.execute(
            select(PayrollRun).where(
                PayrollRun.id == run_id,
                PayrollRun.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The payroll run does not exist",
            message_key="payroll.error.run_not_found",
        )
    return row


async def live_payslip(session: AsyncSession, payslip_id: uuid.UUID) -> PayrollPayslip:
    row = (
        await session.execute(
            select(PayrollPayslip).where(
                PayrollPayslip.id == payslip_id,
                PayrollPayslip.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The payslip does not exist",
            message_key="payroll.error.payslip_not_found",
        )
    return row


async def rule_brackets(session: AsyncSession, rule_id: uuid.UUID) -> list[PayrollRuleBracket]:
    return list(
        (
            await session.execute(
                select(PayrollRuleBracket)
                .where(
                    PayrollRuleBracket.rule_id == rule_id,
                    PayrollRuleBracket.deleted_at.is_(None),
                )
                .order_by(PayrollRuleBracket.sort_order, PayrollRuleBracket.lower_santim)
            )
        )
        .scalars()
        .all()
    )


async def rule_set_rules(session: AsyncSession, rule_set_id: uuid.UUID) -> list[PayrollRule]:
    return list(
        (
            await session.execute(
                select(PayrollRule)
                .where(
                    PayrollRule.rule_set_id == rule_set_id,
                    PayrollRule.deleted_at.is_(None),
                )
                .order_by(PayrollRule.sort_order, PayrollRule.key)
            )
        )
        .scalars()
        .all()
    )


def engine_rule(row: PayrollRule, brackets: list[PayrollRuleBracket]) -> Rule:
    return Rule(
        key=row.key,
        name=row.name,
        kind=RuleKind(row.kind),
        payer=Payer(row.payer),
        method=RuleMethod(row.method),
        base=Basis(row.base),
        rate_basis_points=row.rate_basis_points,
        brackets=tuple(
            Bracket(
                lower_santim=bracket.lower_santim,
                upper_santim=bracket.upper_santim,
                rate_basis_points=bracket.rate_basis_points,
            )
            for bracket in brackets
        ),
    )


def engine_component(
    assignment: PayrollStaffComponent,
    component: PayrollComponent,
) -> ComponentAmount:
    return ComponentAmount(
        code=component.code,
        name=component.name,
        amount_santim=assignment.amount_santim,
        rate_basis_points=assignment.rate_basis_points,
        is_taxable=component.is_taxable,
        is_pensionable=component.is_pensionable,
    )


def component_state(row: PayrollComponent) -> dict[str, Any]:
    return {
        "code": row.code,
        "name": row.name,
        "name_am": row.name_am,
        "kind": row.kind,
        "is_taxable": row.is_taxable,
        "is_pensionable": row.is_pensionable,
        "is_active": row.is_active,
        "sort_order": row.sort_order,
        "notes": row.notes,
        "row_version": row.row_version,
    }


def staff_component_state(row: PayrollStaffComponent) -> dict[str, Any]:
    return {
        "staff_id": str(row.staff_id),
        "component_id": str(row.component_id),
        "amount_santim": row.amount_santim,
        "amount_birr": _money(row.amount_santim),
        "rate_basis_points": row.rate_basis_points,
        "starts_on": _iso(row.starts_on),
        "ends_on": _iso(row.ends_on),
        "notes": row.notes,
        "row_version": row.row_version,
    }


def rule_set_state(row: PayrollRuleSet) -> dict[str, Any]:
    return {
        "code": row.code,
        "name": row.name,
        "effective_from": _iso(row.effective_from),
        "effective_to": _iso(row.effective_to),
        "status": row.status,
        "verified_by_accountant": row.verified_by_accountant,
        "notes": row.notes,
        "row_version": row.row_version,
    }


def rule_state(row: PayrollRule, brackets: list[PayrollRuleBracket]) -> dict[str, Any]:
    return {
        "rule_set_id": str(row.rule_set_id),
        "key": row.key,
        "name": row.name,
        "kind": row.kind,
        "payer": row.payer,
        "method": row.method,
        "base": row.base,
        "rate_basis_points": row.rate_basis_points,
        "is_active": row.is_active,
        "sort_order": row.sort_order,
        "notes": row.notes,
        "brackets": [
            {
                "lower_santim": bracket.lower_santim,
                "upper_santim": bracket.upper_santim,
                "rate_basis_points": bracket.rate_basis_points,
            }
            for bracket in brackets
        ],
        "row_version": row.row_version,
    }


def run_state(row: PayrollRun) -> dict[str, Any]:
    return {
        "period_year": row.period_year,
        "period_month": row.period_month,
        "rule_set_id": str(row.rule_set_id),
        "status": row.status,
        "payslip_count": row.payslip_count,
        "skipped_count": row.skipped_count,
        "gross_santim": row.gross_santim,
        "deductions_santim": row.deductions_santim,
        "net_santim": row.net_santim,
        "employer_santim": row.employer_santim,
        "notes": row.notes,
        "row_version": row.row_version,
    }


def payslip_state(row: PayrollPayslip) -> dict[str, Any]:
    return {
        "run_id": str(row.run_id),
        "staff_id": str(row.staff_id),
        "staff_number": row.staff_number,
        "staff_name": row.staff_name,
        "base_salary_santim": row.base_salary_santim,
        "gross_santim": row.gross_santim,
        "taxable_santim": row.taxable_santim,
        "pensionable_santim": row.pensionable_santim,
        "total_deductions_santim": row.total_deductions_santim,
        "net_santim": row.net_santim,
        "employer_contributions_santim": row.employer_contributions_santim,
        "row_version": row.row_version,
    }


__all__ = [
    "MODULE",
    "component_state",
    "engine_component",
    "engine_rule",
    "live_component",
    "live_payslip",
    "live_rule",
    "live_rule_set",
    "live_run",
    "live_staff_component",
    "payslip_state",
    "rule_brackets",
    "rule_set_rules",
    "rule_set_state",
    "rule_state",
    "run_state",
    "staff_component_state",
]
