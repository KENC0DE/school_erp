"""HTTP routes for staff attendance.

Included by the staff router before its dynamic ``/{staff_id}`` routes so the
static ``/attendance`` paths always win.
"""

from __future__ import annotations

import uuid
from datetime import date

from app.logging import request_id_var
from core.actions.registry import ActionContext
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from modules.staff.attendance_actions import (
    search_staff_attendance,
    staff_attendance_summary,
    upsert_staff_attendance,
)
from modules.staff.attendance_schemas import (
    StaffAttendanceBulkInput,
    StaffAttendanceDay,
    StaffAttendanceStatus,
    StaffAttendanceSummary,
)

attendance_router = APIRouter(tags=["staff"])


def _context(principal: Principal, session: AsyncSession) -> ActionContext:
    return ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )


def _query(
    *,
    on_date: date | None,
    department_id: uuid.UUID | None,
    status: StaffAttendanceStatus | None,
    q: str | None,
) -> dict:
    return {
        "date": on_date.isoformat() if on_date else None,
        "department_id": str(department_id) if department_id else None,
        "status": status,
        "q": q,
    }


@attendance_router.get("/attendance", response_model=StaffAttendanceDay)
async def staff_attendance_day_route(
    date: date | None = Query(None),
    department_id: uuid.UUID | None = Query(None),
    status: StaffAttendanceStatus | None = Query(None),
    q: str | None = Query(None, max_length=120),
    principal: Principal = Depends(require("staff.attendance.view")),
    session: AsyncSession = Depends(get_session),
) -> StaffAttendanceDay:
    return await search_staff_attendance(
        _context(principal, session),
        _query(on_date=date, department_id=department_id, status=status, q=q),
    )


@attendance_router.post("/attendance", response_model=StaffAttendanceDay)
async def upsert_staff_attendance_route(
    payload: StaffAttendanceBulkInput,
    principal: Principal = Depends(require("staff.attendance.record")),
    session: AsyncSession = Depends(get_session),
) -> StaffAttendanceDay:
    return await upsert_staff_attendance(_context(principal, session), payload.model_dump(mode="json"))


@attendance_router.get("/attendance/{staff_id}/summary", response_model=StaffAttendanceSummary)
async def staff_attendance_summary_route(
    staff_id: uuid.UUID,
    from_date: date = Query(...),
    to_date: date = Query(...),
    principal: Principal = Depends(require("staff.attendance.view")),
    session: AsyncSession = Depends(get_session),
) -> StaffAttendanceSummary:
    return await staff_attendance_summary(
        _context(principal, session),
        {
            "staff_id": str(staff_id),
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        },
    )


__all__ = ["attendance_router"]
