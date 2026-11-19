"""Yearly leave balances per staff member and leave type."""

from __future__ import annotations

import uuid
from typing import Any

from core.api.concurrency import ensure_row_version, version_from_payload
from core.audit.service import record
from core.auth.principal import Principal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear
from modules.staff.common import live_staff
from modules.staff.leave_common import (
    MODULE,
    leave_balance_state,
    live_leave_type,
    live_leave_year,
    staff_identity,
    units_from_days,
)
from modules.staff.leave_schemas import (
    LeaveBalanceInput,
    LeaveBalanceList,
    LeaveBalanceOut,
)
from modules.staff.leave_scopes import assert_leave_staff_visible, visible_leave_staff_ids
from modules.staff.models import StaffLeaveBalance, StaffLeaveRequest, StaffLeaveType

UsageKey = tuple[uuid.UUID, uuid.UUID, uuid.UUID]


async def usage_map(session: AsyncSession, keys: set[UsageKey]) -> dict[UsageKey, dict[str, int]]:
    """Sum submitted and approved half-day units for the requested keys."""
    if not keys:
        return {}
    staff_ids = {key[0] for key in keys}
    year_ids = {key[1] for key in keys}
    type_ids = {key[2] for key in keys}
    rows = (
        await session.execute(
            select(
                StaffLeaveRequest.staff_id,
                StaffLeaveRequest.year_id,
                StaffLeaveRequest.leave_type_id,
                StaffLeaveRequest.status,
                StaffLeaveRequest.days_units,
            ).where(
                StaffLeaveRequest.deleted_at.is_(None),
                StaffLeaveRequest.staff_id.in_(staff_ids),
                StaffLeaveRequest.year_id.in_(year_ids),
                StaffLeaveRequest.leave_type_id.in_(type_ids),
                StaffLeaveRequest.status.in_(("submitted", "approved")),
            )
        )
    ).all()
    result: dict[UsageKey, dict[str, int]] = {key: {"used": 0, "pending": 0} for key in keys}
    for staff_id, year_id, type_id, status, units in rows:
        key = (staff_id, year_id, type_id)
        if key not in result:
            continue
        if status == "approved":
            result[key]["used"] += units or 0
        else:
            result[key]["pending"] += units or 0
    return result


async def _out_many(session: AsyncSession, rows: list[StaffLeaveBalance]) -> list[LeaveBalanceOut]:
    if not rows:
        return []
    identities = await staff_identity(session, {row.staff_id for row in rows})
    year_ids = {row.year_id for row in rows}
    type_ids = {row.leave_type_id for row in rows}
    years = {
        row.id: row
        for row in (await session.execute(select(AcademicYear).where(AcademicYear.id.in_(year_ids))))
        .scalars()
        .all()
    }
    types = {
        row.id: row
        for row in (await session.execute(select(StaffLeaveType).where(StaffLeaveType.id.in_(type_ids))))
        .scalars()
        .all()
    }
    usage = await usage_map(session, {(row.staff_id, row.year_id, row.leave_type_id) for row in rows})
    items: list[LeaveBalanceOut] = []
    for row in rows:
        staff_number, staff_name = identities.get(row.staff_id, ("", ""))
        year = years[row.year_id]
        leave_type = types[row.leave_type_id]
        counters = usage.get((row.staff_id, row.year_id, row.leave_type_id), {})
        used = counters.get("used", 0)
        pending = counters.get("pending", 0)
        total = row.entitled_units + row.carried_units + row.adjustment_units
        remaining = total - used - pending
        items.append(
            LeaveBalanceOut(
                id=str(row.id),
                staff_id=str(row.staff_id),
                staff_number=staff_number,
                staff_name=staff_name,
                year_id=str(year.id),
                year_code=year.code,
                leave_type_id=str(leave_type.id),
                leave_type_code=leave_type.code,
                leave_type_name=leave_type.name,
                entitled_days=row.entitled_units / 2,
                carried_days=row.carried_units / 2,
                adjustment_days=row.adjustment_units / 2,
                used_days=used / 2,
                pending_days=pending / 2,
                remaining_days=remaining / 2,
                notes=row.notes,
                row_version=row.row_version,
            )
        )
    return items


async def list_leave_balances(
    session: AsyncSession,
    principal: Principal,
    *,
    staff_id: uuid.UUID | None = None,
    year_id: uuid.UUID | None = None,
    leave_type_id: uuid.UUID | None = None,
) -> LeaveBalanceList:
    if staff_id is not None:
        await live_staff(session, staff_id)
        await assert_leave_staff_visible(session, principal, staff_id)
    stmt = select(StaffLeaveBalance).where(StaffLeaveBalance.deleted_at.is_(None))
    visible = await visible_leave_staff_ids(session, principal)
    if visible is not None:
        if not visible:
            return LeaveBalanceList(items=[], total=0)
        stmt = stmt.where(StaffLeaveBalance.staff_id.in_(visible))
    if staff_id is not None:
        stmt = stmt.where(StaffLeaveBalance.staff_id == staff_id)
    if year_id is not None:
        stmt = stmt.where(StaffLeaveBalance.year_id == year_id)
    if leave_type_id is not None:
        stmt = stmt.where(StaffLeaveBalance.leave_type_id == leave_type_id)
    rows = (
        (
            await session.execute(
                stmt.order_by(
                    StaffLeaveBalance.staff_id,
                    StaffLeaveBalance.year_id,
                    StaffLeaveBalance.leave_type_id,
                )
            )
        )
        .scalars()
        .all()
    )
    items = await _out_many(session, list(rows))
    return LeaveBalanceList(items=items, total=len(items))


async def ensure_balance(
    session: AsyncSession,
    staff_id: uuid.UUID,
    year_id: uuid.UUID,
    leave_type: StaffLeaveType,
) -> StaffLeaveBalance:
    """Return the balance row, creating the type's default entitlement if absent."""
    row = (
        await session.execute(
            select(StaffLeaveBalance).where(
                StaffLeaveBalance.staff_id == staff_id,
                StaffLeaveBalance.year_id == year_id,
                StaffLeaveBalance.leave_type_id == leave_type.id,
                StaffLeaveBalance.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    row = StaffLeaveBalance(
        staff_id=staff_id,
        year_id=year_id,
        leave_type_id=leave_type.id,
        entitled_units=leave_type.annual_entitlement_units,
        carried_units=0,
        adjustment_units=0,
    )
    session.add(row)
    await session.flush()
    return row


async def set_leave_balance(
    session: AsyncSession,
    principal: Principal,
    data: LeaveBalanceInput,
    *,
    via: str = "api",
) -> LeaveBalanceOut:
    staff = await live_staff(session, data.staff_id)
    year = await live_leave_year(session, data.year_id)
    leave_type = await live_leave_type(session, data.leave_type_id)
    existing = (
        await session.execute(
            select(StaffLeaveBalance).where(
                StaffLeaveBalance.staff_id == staff.id,
                StaffLeaveBalance.year_id == year.id,
                StaffLeaveBalance.leave_type_id == leave_type.id,
                StaffLeaveBalance.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    entitled = units_from_days(data.entitled_days)
    carried = units_from_days(data.carried_days)
    adjustment = units_from_days(data.adjustment_days)

    if existing is None:
        row = StaffLeaveBalance(
            staff_id=staff.id,
            year_id=year.id,
            leave_type_id=leave_type.id,
            entitled_units=entitled,
            carried_units=carried,
            adjustment_units=adjustment,
            notes=data.notes,
        )
        session.add(row)
        await session.flush()
        action = "staff.leave_balances.create"
        before: dict[str, Any] | None = None
    else:
        expected = version_from_payload({"row_version": data.row_version})
        row = existing
        before = leave_balance_state(row)
        ensure_row_version(row, expected, current_state=before)
        row.entitled_units = entitled
        row.carried_units = carried
        row.adjustment_units = adjustment
        row.notes = data.notes
        row.row_version = (row.row_version or 0) + 1
        await session.flush()
        action = "staff.leave_balances.update"

    await record(
        session,
        action=action,
        module=MODULE,
        entity_type="staff_leave_balance",
        entity_id=str(row.id),
        before=before,
        after=leave_balance_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    items = await _out_many(session, [row])
    return items[0]


__all__ = [
    "ensure_balance",
    "list_leave_balances",
    "set_leave_balance",
    "usage_map",
]
