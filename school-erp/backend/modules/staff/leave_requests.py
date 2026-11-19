"""Leave requests: drafts, submission, approval, rejection and cancellation."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.models import User
from core.auth.principal import Principal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear
from modules.staff.common import live_staff
from modules.staff.leave_balances import ensure_balance, usage_map
from modules.staff.leave_common import (
    MODULE,
    days_from_units,
    leave_request_state,
    live_leave_type,
    live_leave_year,
    request_units,
    staff_identity,
)
from modules.staff.leave_schemas import (
    LeaveCalendarOut,
    LeaveDecisionInput,
    LeaveRequestInput,
    LeaveRequestList,
    LeaveRequestOut,
    LeaveRequestUpdate,
    LeaveStatus,
)
from modules.staff.leave_scopes import (
    assert_can_decide_for,
    assert_can_request_for,
    assert_leave_staff_visible,
    visible_leave_staff_ids,
)
from modules.staff.models import StaffLeaveRequest, StaffLeaveType

ACTIVE_STATUSES: tuple[str, ...] = ("draft", "submitted", "approved")


async def _live_request(session: AsyncSession, request_id: uuid.UUID) -> StaffLeaveRequest:
    row = (
        await session.execute(
            select(StaffLeaveRequest).where(
                StaffLeaveRequest.id == request_id,
                StaffLeaveRequest.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The leave request does not exist",
            message_key="staff.error.leave_request_not_found",
        )
    return row


async def _out_many(session: AsyncSession, rows: list[StaffLeaveRequest]) -> list[LeaveRequestOut]:
    if not rows:
        return []
    identities = await staff_identity(session, {row.staff_id for row in rows})
    year_ids = {row.year_id for row in rows}
    type_ids = {row.leave_type_id for row in rows}
    decided_ids = {row.decided_by for row in rows if row.decided_by is not None}
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
    deciders = {
        row.id: row.display_name
        for row in (await session.execute(select(User).where(User.id.in_(decided_ids)))).scalars().all()
    }
    items: list[LeaveRequestOut] = []
    for row in rows:
        staff_number, staff_name = identities.get(row.staff_id, ("", ""))
        year = years[row.year_id]
        leave_type = types[row.leave_type_id]
        items.append(
            LeaveRequestOut(
                id=str(row.id),
                staff_id=str(row.staff_id),
                staff_number=staff_number,
                staff_name=staff_name,
                year_id=str(year.id),
                year_code=year.code,
                leave_type_id=str(leave_type.id),
                leave_type_code=leave_type.code,
                leave_type_name=leave_type.name,
                start_date=row.start_date,
                end_date=row.end_date,
                is_half_day=row.is_half_day,
                days=days_from_units(row.days_units),
                reason=row.reason,
                status=row.status,  # type: ignore[arg-type]
                submitted_at=row.submitted_at,
                decided_at=row.decided_at,
                decided_by=str(row.decided_by) if row.decided_by else None,
                decided_by_name=deciders.get(row.decided_by) if row.decided_by else None,
                decision_note=row.decision_note,
                row_version=row.row_version,
            )
        )
    return items


async def _out_one(session: AsyncSession, row: StaffLeaveRequest) -> LeaveRequestOut:
    return (await _out_many(session, [row]))[0]


def _assert_inside_year(year: AcademicYear, start: date, end: date) -> None:
    if start < year.start_date or end > year.end_date:
        raise ValidationFailed(
            "The leave dates must fall inside the academic year",
            message_key="staff.error.leave_outside_year",
            details={
                "year_id": str(year.id),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
        )


async def _assert_no_overlap(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    start: date,
    end: date,
    current_id: uuid.UUID | None = None,
) -> None:
    stmt = select(StaffLeaveRequest.id).where(
        StaffLeaveRequest.staff_id == staff_id,
        StaffLeaveRequest.deleted_at.is_(None),
        StaffLeaveRequest.status.in_(ACTIVE_STATUSES),
        StaffLeaveRequest.start_date <= end,
        StaffLeaveRequest.end_date >= start,
    )
    if current_id is not None:
        stmt = stmt.where(StaffLeaveRequest.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "That staff member already has leave covering those dates",
            message_key="staff.error.leave_overlap",
            details={
                "staff_id": str(staff_id),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
        )


async def _assert_balance(
    session: AsyncSession,
    row: StaffLeaveRequest,
    leave_type: StaffLeaveType,
    *,
    exclude_current_pending: bool = False,
) -> None:
    if not leave_type.counts_against_balance:
        return
    balance = await ensure_balance(session, row.staff_id, row.year_id, leave_type)
    usage = (await usage_map(session, {(row.staff_id, row.year_id, row.leave_type_id)})).get(
        (row.staff_id, row.year_id, row.leave_type_id), {"used": 0, "pending": 0}
    )
    pending = usage["pending"]
    if exclude_current_pending:
        pending = max(0, pending - row.days_units)
    total = balance.entitled_units + balance.carried_units + balance.adjustment_units
    available = total - usage["used"] - pending
    if row.days_units > available:
        raise ValidationFailed(
            "The request exceeds the remaining leave balance",
            message_key="staff.error.leave_balance_exceeded",
            details={
                "staff_id": str(row.staff_id),
                "leave_type_id": str(row.leave_type_id),
                "requested_half_days": row.days_units,
                "available_half_days": max(0, available),
            },
        )


async def _validate_target(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    year_id: uuid.UUID,
    leave_type_id: uuid.UUID,
    start: date,
    end: date,
) -> tuple[Any, AcademicYear, StaffLeaveType]:
    staff = await live_staff(session, staff_id)
    if staff.status == "terminated":
        raise ValidationFailed(
            "A terminated staff member cannot request leave",
            message_key="staff.error.leave_staff_terminated",
        )
    year = await live_leave_year(session, year_id)
    if year.status == "closed":
        raise Conflict(
            "A closed academic year cannot receive leave requests",
            message_key="error.academics.year_closed",
        )
    leave_type = await live_leave_type(session, leave_type_id)
    if not leave_type.is_active:
        raise ValidationFailed(
            "An inactive leave type cannot be requested",
            message_key="staff.error.leave_type_inactive",
        )
    _assert_inside_year(year, start, end)
    return staff, year, leave_type


async def list_leave_requests(
    session: AsyncSession,
    principal: Principal,
    *,
    staff_id: uuid.UUID | None = None,
    year_id: uuid.UUID | None = None,
    leave_type_id: uuid.UUID | None = None,
    status: LeaveStatus | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> LeaveRequestList:
    if staff_id is not None:
        await live_staff(session, staff_id)
        await assert_leave_staff_visible(session, principal, staff_id)
    stmt = select(StaffLeaveRequest).where(StaffLeaveRequest.deleted_at.is_(None))
    visible = await visible_leave_staff_ids(session, principal)
    if visible is not None:
        if not visible:
            return LeaveRequestList(items=[], total=0)
        stmt = stmt.where(StaffLeaveRequest.staff_id.in_(visible))
    if staff_id is not None:
        stmt = stmt.where(StaffLeaveRequest.staff_id == staff_id)
    if year_id is not None:
        stmt = stmt.where(StaffLeaveRequest.year_id == year_id)
    if leave_type_id is not None:
        stmt = stmt.where(StaffLeaveRequest.leave_type_id == leave_type_id)
    if status is not None:
        stmt = stmt.where(StaffLeaveRequest.status == status)
    if from_date is not None:
        stmt = stmt.where(StaffLeaveRequest.end_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(StaffLeaveRequest.start_date <= to_date)
    rows = (
        (
            await session.execute(
                stmt.order_by(
                    StaffLeaveRequest.start_date,
                    StaffLeaveRequest.staff_id,
                    StaffLeaveRequest.id,
                )
            )
        )
        .scalars()
        .all()
    )
    items = await _out_many(session, list(rows))
    return LeaveRequestList(items=items, total=len(items))


async def get_leave_request(
    session: AsyncSession, principal: Principal, request_id: uuid.UUID
) -> LeaveRequestOut:
    row = await _live_request(session, request_id)
    await assert_leave_staff_visible(session, principal, row.staff_id)
    return await _out_one(session, row)


async def leave_calendar(
    session: AsyncSession,
    principal: Principal,
    *,
    from_date: date,
    to_date: date,
    year_id: uuid.UUID | None = None,
    leave_type_id: uuid.UUID | None = None,
    status: LeaveStatus | None = None,
) -> LeaveCalendarOut:
    if to_date < from_date:
        raise ValidationFailed(
            "The calendar end date cannot be before the start date",
            message_key="staff.error.leave_dates",
        )
    listed = await list_leave_requests(
        session,
        principal,
        year_id=year_id,
        leave_type_id=leave_type_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
    items = (
        listed.items
        if status is not None
        else [item for item in listed.items if item.status in ACTIVE_STATUSES]
    )
    return LeaveCalendarOut(
        from_date=from_date,
        to_date=to_date,
        items=items,
        total=len(items),
    )


async def create_leave_request(
    session: AsyncSession,
    principal: Principal,
    data: LeaveRequestInput,
    *,
    via: str = "api",
) -> LeaveRequestOut:
    await assert_can_request_for(session, principal, data.staff_id)
    _staff, year, leave_type = await _validate_target(
        session,
        staff_id=data.staff_id,
        year_id=data.year_id,
        leave_type_id=data.leave_type_id,
        start=data.start_date,
        end=data.end_date,
    )
    await _assert_no_overlap(
        session,
        staff_id=data.staff_id,
        start=data.start_date,
        end=data.end_date,
    )
    row = StaffLeaveRequest(
        staff_id=data.staff_id,
        year_id=year.id,
        leave_type_id=leave_type.id,
        start_date=data.start_date,
        end_date=data.end_date,
        is_half_day=data.is_half_day,
        days_units=request_units(data.start_date, data.end_date, data.is_half_day),
        reason=data.reason,
        status="draft",
    )
    session.add(row)
    await session.flush()
    await record(
        session,
        action="staff.leave_requests.create",
        module=MODULE,
        entity_type="staff_leave_request",
        entity_id=str(row.id),
        after=leave_request_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await _out_one(session, row)


async def update_leave_request(
    session: AsyncSession,
    principal: Principal,
    request_id: uuid.UUID,
    data: LeaveRequestUpdate,
    *,
    via: str = "api",
) -> LeaveRequestOut:
    row = await _live_request(session, request_id)
    await assert_can_request_for(session, principal, row.staff_id)
    if row.status != "draft":
        raise Conflict(
            "Only a draft leave request can be edited",
            message_key="staff.error.leave_not_draft",
            details={"status": row.status},
        )
    before = leave_request_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    year_id = payload.get("year_id", row.year_id)
    type_id = payload.get("leave_type_id", row.leave_type_id)
    start = payload.get("start_date", row.start_date)
    end = payload.get("end_date", row.end_date)
    half_day = payload.get("is_half_day", row.is_half_day)
    _staff, year, leave_type = await _validate_target(
        session,
        staff_id=row.staff_id,
        year_id=year_id,
        leave_type_id=type_id,
        start=start,
        end=end,
    )
    await _assert_no_overlap(
        session,
        staff_id=row.staff_id,
        start=start,
        end=end,
        current_id=row.id,
    )
    row.year_id = year.id
    row.leave_type_id = leave_type.id
    row.start_date = start
    row.end_date = end
    row.is_half_day = half_day
    row.days_units = request_units(start, end, half_day)
    if "reason" in payload:
        row.reason = payload["reason"]
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="staff.leave_requests.update",
        module=MODULE,
        entity_type="staff_leave_request",
        entity_id=str(row.id),
        before=before,
        after=leave_request_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await _out_one(session, row)


async def submit_leave_request(
    session: AsyncSession,
    principal: Principal,
    request_id: uuid.UUID,
    *,
    via: str = "api",
) -> LeaveRequestOut:
    row = await _live_request(session, request_id)
    await assert_can_request_for(session, principal, row.staff_id)
    if row.status != "draft":
        raise Conflict(
            "Only a draft leave request can be submitted",
            message_key="staff.error.leave_not_draft",
            details={"status": row.status},
        )
    _staff, _year, leave_type = await _validate_target(
        session,
        staff_id=row.staff_id,
        year_id=row.year_id,
        leave_type_id=row.leave_type_id,
        start=row.start_date,
        end=row.end_date,
    )
    await _assert_no_overlap(
        session,
        staff_id=row.staff_id,
        start=row.start_date,
        end=row.end_date,
        current_id=row.id,
    )
    await _assert_balance(session, row, leave_type)
    before = leave_request_state(row)
    row.submitted_at = datetime.now(UTC)
    row.status = "submitted" if leave_type.requires_approval else "approved"
    if row.status == "approved":
        row.decided_at = row.submitted_at
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="staff.leave_requests.submit",
        module=MODULE,
        entity_type="staff_leave_request",
        entity_id=str(row.id),
        before=before,
        after=leave_request_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await _out_one(session, row)


async def approve_leave_request(
    session: AsyncSession,
    principal: Principal,
    request_id: uuid.UUID,
    data: LeaveDecisionInput | None = None,
    *,
    via: str = "api",
) -> LeaveRequestOut:
    row = await _live_request(session, request_id)
    await assert_can_decide_for(session, principal, row.staff_id)
    if row.status != "submitted":
        raise Conflict(
            "Only a submitted leave request can be approved",
            message_key="staff.error.leave_not_submitted",
            details={"status": row.status},
        )
    _staff, _year, leave_type = await _validate_target(
        session,
        staff_id=row.staff_id,
        year_id=row.year_id,
        leave_type_id=row.leave_type_id,
        start=row.start_date,
        end=row.end_date,
    )
    await _assert_balance(session, row, leave_type, exclude_current_pending=True)
    before = leave_request_state(row)
    row.status = "approved"
    row.decided_at = datetime.now(UTC)
    row.decided_by = uuid.UUID(principal.user_id)
    row.decision_note = data.note if data is not None else None
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="staff.leave_requests.approve",
        module=MODULE,
        entity_type="staff_leave_request",
        entity_id=str(row.id),
        before=before,
        after=leave_request_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await _out_one(session, row)


async def reject_leave_request(
    session: AsyncSession,
    principal: Principal,
    request_id: uuid.UUID,
    data: LeaveDecisionInput | None = None,
    *,
    via: str = "api",
) -> LeaveRequestOut:
    row = await _live_request(session, request_id)
    await assert_can_decide_for(session, principal, row.staff_id)
    if row.status != "submitted":
        raise Conflict(
            "Only a submitted leave request can be rejected",
            message_key="staff.error.leave_not_submitted",
            details={"status": row.status},
        )
    before = leave_request_state(row)
    row.status = "rejected"
    row.decided_at = datetime.now(UTC)
    row.decided_by = uuid.UUID(principal.user_id)
    row.decision_note = data.note if data is not None else None
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="staff.leave_requests.reject",
        module=MODULE,
        entity_type="staff_leave_request",
        entity_id=str(row.id),
        before=before,
        after=leave_request_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await _out_one(session, row)


async def cancel_leave_request(
    session: AsyncSession,
    principal: Principal,
    request_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> LeaveRequestOut:
    row = await _live_request(session, request_id)
    await assert_can_request_for(session, principal, row.staff_id)
    if row.status in ("rejected", "cancelled"):
        raise Conflict(
            "This leave request cannot be cancelled",
            message_key="staff.error.leave_not_cancellable",
            details={"status": row.status},
        )
    before = leave_request_state(row)
    row.status = "cancelled"
    row.decision_note = reason
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="staff.leave_requests.cancel",
        module=MODULE,
        entity_type="staff_leave_request",
        entity_id=str(row.id),
        before=before,
        after=leave_request_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await _out_one(session, row)


__all__ = [
    "approve_leave_request",
    "cancel_leave_request",
    "create_leave_request",
    "get_leave_request",
    "leave_calendar",
    "list_leave_requests",
    "reject_leave_request",
    "submit_leave_request",
    "update_leave_request",
]
