"""Leave type catalogue: paid, unpaid and other staff absence categories."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import Conflict
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.staff.leave_common import MODULE, leave_type_state, live_leave_type, units_from_days
from modules.staff.leave_schemas import (
    LeaveTypeInput,
    LeaveTypeList,
    LeaveTypeOut,
    LeaveTypeUpdate,
)
from modules.staff.models import StaffLeaveType


def _out(row: StaffLeaveType) -> LeaveTypeOut:
    return LeaveTypeOut(
        id=str(row.id),
        code=row.code,
        name=row.name,
        name_am=row.name_am,
        is_paid=row.is_paid,
        annual_entitlement_days=row.annual_entitlement_units / 2,
        counts_against_balance=row.counts_against_balance,
        requires_approval=row.requires_approval,
        is_active=row.is_active,
        sort_order=row.sort_order,
        notes=row.notes,
        row_version=row.row_version,
    )


async def _assert_code_free(session: AsyncSession, code: str, *, current_id: uuid.UUID | None = None) -> None:
    stmt = select(StaffLeaveType.id).where(
        StaffLeaveType.code == code,
        StaffLeaveType.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(StaffLeaveType.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "A leave type with that code already exists",
            message_key="staff.error.leave_type_code_taken",
            details={"code": code},
        )


async def list_leave_types(session: AsyncSession, *, include_inactive: bool = False) -> LeaveTypeList:
    stmt = select(StaffLeaveType).where(StaffLeaveType.deleted_at.is_(None))
    if not include_inactive:
        stmt = stmt.where(StaffLeaveType.is_active.is_(True))
    rows = (
        (await session.execute(stmt.order_by(StaffLeaveType.sort_order, StaffLeaveType.name))).scalars().all()
    )
    return LeaveTypeList(items=[_out(row) for row in rows], total=len(rows))


async def get_leave_type(session: AsyncSession, leave_type_id: uuid.UUID) -> LeaveTypeOut:
    return _out(await live_leave_type(session, leave_type_id))


async def create_leave_type(
    session: AsyncSession,
    principal: Principal,
    data: LeaveTypeInput,
    *,
    via: str = "api",
) -> LeaveTypeOut:
    await _assert_code_free(session, data.code)
    payload = data.model_dump()
    payload["annual_entitlement_units"] = units_from_days(payload.pop("annual_entitlement_days"))
    row = StaffLeaveType(**payload)
    session.add(row)
    await session.flush()
    await record(
        session,
        action="staff.leave_types.create",
        module=MODULE,
        entity_type="staff_leave_type",
        entity_id=str(row.id),
        after=leave_type_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return _out(row)


async def update_leave_type(
    session: AsyncSession,
    principal: Principal,
    leave_type_id: uuid.UUID,
    data: LeaveTypeUpdate,
    *,
    via: str = "api",
) -> LeaveTypeOut:
    row = await live_leave_type(session, leave_type_id)
    before = leave_type_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload: dict[str, Any] = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    if "code" in payload:
        await _assert_code_free(session, payload["code"], current_id=row.id)
    if "annual_entitlement_days" in payload:
        payload["annual_entitlement_units"] = units_from_days(payload.pop("annual_entitlement_days"))

    changes: dict[str, Any] = {}
    for key, value in payload.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changes[key] = value
    if changes:
        row.row_version = (row.row_version or 0) + 1
    await session.flush()
    if changes:
        await record(
            session,
            action="staff.leave_types.update",
            module=MODULE,
            entity_type="staff_leave_type",
            entity_id=str(row.id),
            before=before,
            after=leave_type_state(row),
            actor=principal,
            via=via,
        )
    await session.commit()
    return _out(row)


__all__ = [
    "create_leave_type",
    "get_leave_type",
    "list_leave_types",
    "update_leave_type",
]
