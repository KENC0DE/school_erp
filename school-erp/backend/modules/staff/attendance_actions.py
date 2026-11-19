"""Action-registry entry points for staff attendance."""

from __future__ import annotations

import uuid
from datetime import date

from core.actions.registry import ActionContext, action

from modules.staff import attendance_service
from modules.staff.attendance_schemas import (
    StaffAttendanceBulkInput,
    StaffAttendanceDay,
    StaffAttendanceQuery,
    StaffAttendanceSummary,
)


def _id(payload: dict, key: str) -> uuid.UUID:
    return uuid.UUID(str(payload[key]))


@action(
    key="staff.attendance.search",
    module="staff",
    permission="staff.attendance.view",
    risk="read",
    describe="Read one day's staff attendance roster",
    input=StaffAttendanceQuery,
    output=StaffAttendanceDay,
)
async def search_staff_attendance(ctx: ActionContext, payload: dict | None = None) -> StaffAttendanceDay:
    query = StaffAttendanceQuery.model_validate(payload or {})
    return await attendance_service.day_view(ctx.session, ctx.principal, query)


@action(
    key="staff.attendance.upsert",
    module="staff",
    permission="staff.attendance.record",
    risk="write",
    describe="Record staff attendance for one or more staff members",
    input=StaffAttendanceBulkInput,
    output=StaffAttendanceDay,
)
async def upsert_staff_attendance(ctx: ActionContext, payload: dict) -> StaffAttendanceDay:
    data = StaffAttendanceBulkInput.model_validate(payload)
    return await attendance_service.upsert_day(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="staff.attendance.summary",
    module="staff",
    permission="staff.attendance.view",
    risk="read",
    describe="Summarise one staff member's attendance over a date range",
    output=StaffAttendanceSummary,
)
async def staff_attendance_summary(ctx: ActionContext, payload: dict) -> StaffAttendanceSummary:
    return await attendance_service.summary(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        from_date=date.fromisoformat(str(payload["from_date"])),
        to_date=date.fromisoformat(str(payload["to_date"])),
    )


__all__ = [
    "search_staff_attendance",
    "staff_attendance_summary",
    "upsert_staff_attendance",
]
