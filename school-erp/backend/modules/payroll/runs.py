"""Payroll runs: turn configurable rules into payslips for one month."""

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import UTC, date, datetime
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import mark_deleted, soft_delete
from core.people.models import Person, full_name
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payroll.common import (
    MODULE,
    engine_component,
    engine_rule,
    live_payslip,
    live_rule_set,
    live_run,
    rule_brackets,
    rule_set_rules,
    run_state,
)
from modules.payroll.engine import (
    ComponentAmount,
    PayrollError,
    PayslipInput,
    compute_payslip,
)
from modules.payroll.models import (
    PayrollComponent,
    PayrollPayslip,
    PayrollPayslipLine,
    PayrollRuleSet,
    PayrollRun,
    PayrollStaffComponent,
)
from modules.payroll.schemas import (
    PayslipList,
    PayslipOut,
    RunInput,
    RunList,
    RunOut,
    RunQuery,
)
from modules.payroll.views import payslip_out, run_out
from modules.staff.models import StaffContract, StaffProfile

PAYROLL_STATUSES = {"active", "on_leave"}


def _month_window(period_year: int, period_month: int) -> tuple[date, date]:
    first = date(period_year, period_month, 1)
    last = date(period_year, period_month, monthrange(period_year, period_month)[1])
    return first, last


def _period_label(period_year: int, period_month: int) -> str:
    return f"{period_year:04d}-{period_month:02d}"


async def _rule_set_code(session: AsyncSession, rule_set_id: uuid.UUID) -> str:
    return (
        await session.execute(select(PayrollRuleSet.code).where(PayrollRuleSet.id == rule_set_id))
    ).scalar_one()


async def _active_rule_set(session: AsyncSession) -> PayrollRuleSet | None:
    return (
        (
            await session.execute(
                select(PayrollRuleSet).where(
                    PayrollRuleSet.status == "active",
                    PayrollRuleSet.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .first()
    )


async def list_runs(session: AsyncSession, query: RunQuery) -> RunList:
    stmt = select(PayrollRun).where(PayrollRun.deleted_at.is_(None))
    if query.period_year is not None:
        stmt = stmt.where(PayrollRun.period_year == query.period_year)
    if query.period_month is not None:
        stmt = stmt.where(PayrollRun.period_month == query.period_month)
    if query.status is not None:
        stmt = stmt.where(PayrollRun.status == query.status)
    rows = (
        (await session.execute(stmt.order_by(PayrollRun.period_year.desc(), PayrollRun.period_month.desc())))
        .scalars()
        .all()
    )
    items = [run_out(row, await _rule_set_code(session, row.rule_set_id)) for row in rows]
    return RunList(items=items, total=len(items))


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> RunOut:
    row = await live_run(session, run_id)
    return run_out(row, await _rule_set_code(session, row.rule_set_id))


async def create_run(
    session: AsyncSession,
    principal: Principal,
    data: RunInput,
    *,
    via: str = "api",
) -> RunOut:
    existing = (
        (
            await session.execute(
                select(PayrollRun.id)
                .where(
                    PayrollRun.period_year == data.period_year,
                    PayrollRun.period_month == data.period_month,
                    PayrollRun.deleted_at.is_(None),
                )
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        raise Conflict(
            "A payroll run already exists for that month",
            message_key="payroll.error.run_exists",
            details={"period": _period_label(data.period_year, data.period_month)},
        )

    if data.rule_set_id is not None:
        rule_set = await live_rule_set(session, data.rule_set_id)
        if rule_set.status != "active":
            raise ValidationFailed(
                "Payroll runs use an active rule set",
                message_key="payroll.error.rule_set_not_active_start",
            )
    else:
        rule_set = await _active_rule_set(session)
        if rule_set is None:
            raise ValidationFailed(
                "Activate a payroll rule set before creating a run",
                message_key="payroll.error.no_active_rule_set",
            )

    row = PayrollRun(
        period_year=data.period_year,
        period_month=data.period_month,
        rule_set_id=rule_set.id,
        status="draft",
        notes=data.notes,
    )
    session.add(row)
    await session.flush()
    await record(
        session,
        action="payroll.runs.create",
        module=MODULE,
        entity_type="payroll_run",
        entity_id=str(row.id),
        after=run_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return run_out(row, rule_set.code)


async def _rules_for(session: AsyncSession, rule_set: PayrollRuleSet):
    rules = []
    for rule in await rule_set_rules(session, rule_set.id):
        if not rule.is_active:
            continue
        rules.append(engine_rule(rule, await rule_brackets(session, rule.id)))
    return rules


async def _contract_for(
    session: AsyncSession,
    staff_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> StaffContract | None:
    return (
        (
            await session.execute(
                select(StaffContract)
                .where(
                    StaffContract.staff_id == staff_id,
                    StaffContract.status == "active",
                    StaffContract.deleted_at.is_(None),
                    StaffContract.start_date <= period_end,
                    (StaffContract.end_date.is_(None)) | (StaffContract.end_date >= period_start),
                )
                .order_by(StaffContract.start_date.desc())
            )
        )
        .scalars()
        .first()
    )


async def _components_for(
    session: AsyncSession,
    staff_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> tuple[list[ComponentAmount], list[ComponentAmount]]:
    rows = (
        await session.execute(
            select(PayrollStaffComponent, PayrollComponent)
            .join(PayrollComponent, PayrollComponent.id == PayrollStaffComponent.component_id)
            .where(
                PayrollStaffComponent.staff_id == staff_id,
                PayrollStaffComponent.deleted_at.is_(None),
                PayrollComponent.deleted_at.is_(None),
                PayrollComponent.is_active.is_(True),
                PayrollStaffComponent.starts_on <= period_end,
                (PayrollStaffComponent.ends_on.is_(None)) | (PayrollStaffComponent.ends_on >= period_start),
            )
            .order_by(PayrollComponent.sort_order, PayrollComponent.code)
        )
    ).all()
    earnings: list[ComponentAmount] = []
    deductions: list[ComponentAmount] = []
    for assignment, component in rows:
        amount = engine_component(assignment, component)
        if component.kind == "deduction":
            deductions.append(amount)
        else:
            earnings.append(amount)
    return earnings, deductions


async def _delete_payslips(
    session: AsyncSession,
    principal: Principal,
    run_id: uuid.UUID,
) -> int:
    payslips = (
        (
            await session.execute(
                select(PayrollPayslip).where(
                    PayrollPayslip.run_id == run_id,
                    PayrollPayslip.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for payslip in payslips:
        lines = (
            (
                await session.execute(
                    select(PayrollPayslipLine).where(
                        PayrollPayslipLine.payslip_id == payslip.id,
                        PayrollPayslipLine.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for line in lines:
            mark_deleted(line, actor=principal)
        mark_deleted(payslip, actor=principal)
    # Flush the soft deletes before a recalculation inserts fresh rows, so the
    # live-unique (run_id, staff_id) index never sees two live payslips.
    await session.flush()
    return len(payslips)


async def calculate_run(
    session: AsyncSession,
    principal: Principal,
    run_id: uuid.UUID,
    *,
    via: str = "api",
) -> RunOut:
    row = await live_run(session, run_id)
    if row.status == "finalized":
        raise Conflict(
            "A finalized payroll run cannot be recalculated",
            message_key="payroll.error.run_finalized",
        )
    rule_set = await live_rule_set(session, row.rule_set_id)
    rules = await _rules_for(session, rule_set)
    if not rules:
        raise ValidationFailed(
            "The rule set has no active rules",
            message_key="payroll.error.rule_set_empty",
        )

    period_start, period_end = _month_window(row.period_year, row.period_month)
    before = run_state(row)
    await _delete_payslips(session, principal, row.id)

    staff_rows = (
        await session.execute(
            select(StaffProfile, Person)
            .join(Person, Person.id == StaffProfile.person_id)
            .where(
                StaffProfile.deleted_at.is_(None),
                StaffProfile.status.in_(PAYROLL_STATUSES),
            )
            .order_by(StaffProfile.staff_number)
        )
    ).all()

    payslips = 0
    skipped = 0
    gross = 0
    deductions = 0
    net = 0
    employer = 0
    for staff, person in staff_rows:
        contract = await _contract_for(session, staff.id, period_start, period_end)
        if contract is None or contract.salary_santim is None:
            skipped += 1
            continue
        earnings, deduction_components = await _components_for(session, staff.id, period_start, period_end)
        try:
            result = compute_payslip(
                PayslipInput(
                    base_salary_santim=contract.salary_santim,
                    earnings=tuple(earnings),
                    deductions=tuple(deduction_components),
                    rules=tuple(rules),
                )
            )
        except PayrollError as exc:
            raise ValidationFailed(
                f"Payroll calculation failed for {staff.staff_number}: {exc}",
                message_key="payroll.error.calculation_failed",
                details={"staff_id": str(staff.id), "reason": str(exc)},
            ) from exc

        payslip = PayrollPayslip(
            run_id=row.id,
            staff_id=staff.id,
            contract_id=contract.id,
            staff_number=staff.staff_number,
            staff_name=full_name(person, "en"),
            base_salary_santim=contract.salary_santim,
            gross_santim=result.gross_santim,
            taxable_santim=result.taxable_santim,
            pensionable_santim=result.pensionable_santim,
            total_deductions_santim=result.total_deductions_santim,
            net_santim=result.net_santim,
            employer_contributions_santim=result.employer_contributions_santim,
        )
        session.add(payslip)
        await session.flush()
        for index, line in enumerate(result.lines):
            session.add(
                PayrollPayslipLine(
                    payslip_id=payslip.id,
                    kind=line.kind,
                    code=line.code,
                    name=line.name,
                    source=line.source,
                    rule_key=line.rule_key,
                    amount_santim=line.amount_santim,
                    base_santim=line.base_santim,
                    rate_basis_points=line.rate_basis_points,
                    sort_order=index,
                )
            )
        payslips += 1
        gross += result.gross_santim
        deductions += result.total_deductions_santim
        net += result.net_santim
        employer += result.employer_contributions_santim

    row.status = "calculated"
    row.payslip_count = payslips
    row.skipped_count = skipped
    row.gross_santim = gross
    row.deductions_santim = deductions
    row.net_santim = net
    row.employer_santim = employer
    row.calculated_at = datetime.now(UTC)
    row.finalized_at = None
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="payroll.runs.calculate",
        module=MODULE,
        entity_type="payroll_run",
        entity_id=str(row.id),
        before=before,
        after=run_state(row),
        actor=principal,
        reason=f"period {_period_label(row.period_year, row.period_month)}"
        f", {payslips} payslip(s), {skipped} skipped",
        via=via,
    )
    await session.commit()
    return run_out(row, rule_set.code)


async def finalize_run(
    session: AsyncSession,
    principal: Principal,
    run_id: uuid.UUID,
    *,
    via: str = "api",
) -> RunOut:
    row = await live_run(session, run_id)
    if row.status == "finalized":
        return run_out(row, await _rule_set_code(session, row.rule_set_id))
    if row.status != "calculated":
        raise Conflict(
            "Calculate the run before finalizing it",
            message_key="payroll.error.run_not_calculated",
        )
    if row.payslip_count == 0:
        raise ValidationFailed(
            "A run with no payslips cannot be finalized",
            message_key="payroll.error.run_empty",
        )
    before = run_state(row)
    row.status = "finalized"
    row.finalized_at = datetime.now(UTC)
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="payroll.runs.finalize",
        module=MODULE,
        entity_type="payroll_run",
        entity_id=str(row.id),
        before=before,
        after=run_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return run_out(row, await _rule_set_code(session, row.rule_set_id))


async def delete_run(
    session: AsyncSession,
    principal: Principal,
    run_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await live_run(session, run_id)
    if row.status == "finalized":
        raise Conflict(
            "A finalized payroll run cannot be deleted",
            message_key="payroll.error.run_finalized_delete",
        )
    await _delete_payslips(session, principal, row.id)
    changed = await soft_delete(
        session,
        row,
        action="payroll.runs.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="payroll_run",
    )
    await session.flush()
    await session.commit()
    return {"id": str(row.id), "deleted": bool(changed), "row_version": row.row_version}


async def list_payslips(session: AsyncSession, run_id: uuid.UUID) -> PayslipList:
    await live_run(session, run_id)
    rows = (
        (
            await session.execute(
                select(PayrollPayslip)
                .where(
                    PayrollPayslip.run_id == run_id,
                    PayrollPayslip.deleted_at.is_(None),
                )
                .order_by(PayrollPayslip.staff_number)
            )
        )
        .scalars()
        .all()
    )
    items = [payslip_out(row, await _lines(session, row.id)) for row in rows]
    return PayslipList(items=items, total=len(items))


async def _lines(session: AsyncSession, payslip_id: uuid.UUID) -> list[PayrollPayslipLine]:
    return list(
        (
            await session.execute(
                select(PayrollPayslipLine)
                .where(
                    PayrollPayslipLine.payslip_id == payslip_id,
                    PayrollPayslipLine.deleted_at.is_(None),
                )
                .order_by(PayrollPayslipLine.sort_order, PayrollPayslipLine.id)
            )
        )
        .scalars()
        .all()
    )


async def get_payslip(session: AsyncSession, payslip_id: uuid.UUID) -> PayslipOut:
    row = await live_payslip(session, payslip_id)
    return payslip_out(row, await _lines(session, row.id))


async def payslip_for_staff(
    session: AsyncSession,
    run_id: uuid.UUID,
    staff_id: uuid.UUID,
) -> PayslipOut:
    row = (
        await session.execute(
            select(PayrollPayslip).where(
                PayrollPayslip.run_id == run_id,
                PayrollPayslip.staff_id == staff_id,
                PayrollPayslip.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "This staff member has no payslip in that run",
            message_key="payroll.error.payslip_not_found",
        )
    return payslip_out(row, await _lines(session, row.id))


__all__ = [
    "calculate_run",
    "create_run",
    "delete_run",
    "finalize_run",
    "get_payslip",
    "get_run",
    "list_payslips",
    "list_runs",
    "payslip_for_staff",
]
