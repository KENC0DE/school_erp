"""HTTP routes for leave types, balances, requests and the calendar view."""

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

from modules.staff.leave_actions import (
    approve_leave_request,
    cancel_leave_request,
    create_leave_request,
    create_leave_type,
    get_leave_calendar,
    get_leave_request,
    get_leave_type,
    reject_leave_request,
    search_leave_balances,
    search_leave_requests,
    search_leave_types,
    set_leave_balance,
    submit_leave_request,
    update_leave_request,
    update_leave_type,
)
from modules.staff.leave_schemas import (
    LeaveBalanceInput,
    LeaveBalanceList,
    LeaveBalanceOut,
    LeaveCalendarOut,
    LeaveDecisionInput,
    LeaveRequestInput,
    LeaveRequestList,
    LeaveRequestOut,
    LeaveRequestUpdate,
    LeaveStatus,
    LeaveTypeInput,
    LeaveTypeList,
    LeaveTypeOut,
    LeaveTypeUpdate,
)

leave_router = APIRouter(tags=["staff"])


def _context(principal: Principal, session: AsyncSession) -> ActionContext:
    return ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )


def _with(payload: dict, **values) -> dict:
    return {**payload, **values}


# ----------------------------------------------------------------- leave types


@leave_router.get("/leave-types", response_model=LeaveTypeList)
async def list_leave_types_route(
    include_inactive: bool = Query(False),
    principal: Principal = Depends(require("staff.leave.view")),
    session: AsyncSession = Depends(get_session),
) -> LeaveTypeList:
    return await search_leave_types(_context(principal, session), {"include_inactive": include_inactive})


@leave_router.post("/leave-types", response_model=LeaveTypeOut, status_code=201)
async def create_leave_type_route(
    payload: LeaveTypeInput,
    principal: Principal = Depends(require("staff.leave.manage")),
    session: AsyncSession = Depends(get_session),
) -> LeaveTypeOut:
    return await create_leave_type(_context(principal, session), payload.model_dump())


@leave_router.get("/leave-types/{leave_type_id}", response_model=LeaveTypeOut)
async def get_leave_type_route(
    leave_type_id: uuid.UUID,
    principal: Principal = Depends(require("staff.leave.view")),
    session: AsyncSession = Depends(get_session),
) -> LeaveTypeOut:
    return await get_leave_type(_context(principal, session), {"leave_type_id": str(leave_type_id)})


@leave_router.patch("/leave-types/{leave_type_id}", response_model=LeaveTypeOut)
async def update_leave_type_route(
    leave_type_id: uuid.UUID,
    payload: LeaveTypeUpdate,
    principal: Principal = Depends(require("staff.leave.manage")),
    session: AsyncSession = Depends(get_session),
) -> LeaveTypeOut:
    return await update_leave_type(
        _context(principal, session),
        _with(payload.model_dump(exclude_unset=True), leave_type_id=leave_type_id),
    )


# -------------------------------------------------------------- leave balances


@leave_router.get("/leave-balances", response_model=LeaveBalanceList)
async def list_leave_balances_route(
    staff_id: uuid.UUID | None = Query(None),
    year_id: uuid.UUID | None = Query(None),
    leave_type_id: uuid.UUID | None = Query(None),
    principal: Principal = Depends(require("staff.leave.view")),
    session: AsyncSession = Depends(get_session),
) -> LeaveBalanceList:
    return await search_leave_balances(
        _context(principal, session),
        {
            "staff_id": str(staff_id) if staff_id else None,
            "year_id": str(year_id) if year_id else None,
            "leave_type_id": str(leave_type_id) if leave_type_id else None,
        },
    )


@leave_router.put("/leave-balances", response_model=LeaveBalanceOut)
async def set_leave_balance_route(
    payload: LeaveBalanceInput,
    principal: Principal = Depends(require("staff.leave.manage")),
    session: AsyncSession = Depends(get_session),
) -> LeaveBalanceOut:
    return await set_leave_balance(_context(principal, session), payload.model_dump())


# -------------------------------------------------------------- leave requests


@leave_router.get("/leave-requests", response_model=LeaveRequestList)
async def list_leave_requests_route(
    staff_id: uuid.UUID | None = Query(None),
    year_id: uuid.UUID | None = Query(None),
    leave_type_id: uuid.UUID | None = Query(None),
    status: LeaveStatus | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    principal: Principal = Depends(require("staff.leave.view")),
    session: AsyncSession = Depends(get_session),
) -> LeaveRequestList:
    return await search_leave_requests(
        _context(principal, session),
        {
            "staff_id": str(staff_id) if staff_id else None,
            "year_id": str(year_id) if year_id else None,
            "leave_type_id": str(leave_type_id) if leave_type_id else None,
            "status": status,
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
        },
    )


@leave_router.post("/leave-requests", response_model=LeaveRequestOut, status_code=201)
async def create_leave_request_route(
    payload: LeaveRequestInput,
    principal: Principal = Depends(require("staff.leave.request")),
    session: AsyncSession = Depends(get_session),
) -> LeaveRequestOut:
    return await create_leave_request(_context(principal, session), payload.model_dump())


@leave_router.get("/leave-requests/{request_id}", response_model=LeaveRequestOut)
async def get_leave_request_route(
    request_id: uuid.UUID,
    principal: Principal = Depends(require("staff.leave.view")),
    session: AsyncSession = Depends(get_session),
) -> LeaveRequestOut:
    return await get_leave_request(_context(principal, session), {"request_id": str(request_id)})


@leave_router.patch("/leave-requests/{request_id}", response_model=LeaveRequestOut)
async def update_leave_request_route(
    request_id: uuid.UUID,
    payload: LeaveRequestUpdate,
    principal: Principal = Depends(require("staff.leave.request")),
    session: AsyncSession = Depends(get_session),
) -> LeaveRequestOut:
    return await update_leave_request(
        _context(principal, session),
        _with(payload.model_dump(exclude_unset=True), request_id=request_id),
    )


@leave_router.post("/leave-requests/{request_id}/submit", response_model=LeaveRequestOut)
async def submit_leave_request_route(
    request_id: uuid.UUID,
    principal: Principal = Depends(require("staff.leave.request")),
    session: AsyncSession = Depends(get_session),
) -> LeaveRequestOut:
    return await submit_leave_request(_context(principal, session), {"request_id": str(request_id)})


@leave_router.post("/leave-requests/{request_id}/approve", response_model=LeaveRequestOut)
async def approve_leave_request_route(
    request_id: uuid.UUID,
    payload: LeaveDecisionInput | None = None,
    principal: Principal = Depends(require("staff.leave.approve")),
    session: AsyncSession = Depends(get_session),
) -> LeaveRequestOut:
    body = {"request_id": str(request_id)}
    if payload is not None:
        body["note"] = payload.note
    return await approve_leave_request(_context(principal, session), body)


@leave_router.post("/leave-requests/{request_id}/reject", response_model=LeaveRequestOut)
async def reject_leave_request_route(
    request_id: uuid.UUID,
    payload: LeaveDecisionInput | None = None,
    principal: Principal = Depends(require("staff.leave.approve")),
    session: AsyncSession = Depends(get_session),
) -> LeaveRequestOut:
    body = {"request_id": str(request_id)}
    if payload is not None:
        body["note"] = payload.note
    return await reject_leave_request(_context(principal, session), body)


@leave_router.post("/leave-requests/{request_id}/cancel", response_model=LeaveRequestOut)
async def cancel_leave_request_route(
    request_id: uuid.UUID,
    reason: str | None = Query(None, max_length=2000),
    principal: Principal = Depends(require("staff.leave.request")),
    session: AsyncSession = Depends(get_session),
) -> LeaveRequestOut:
    return await cancel_leave_request(
        _context(principal, session),
        _with({"reason": reason}, request_id=request_id),
    )


# -------------------------------------------------------------------- calendar


@leave_router.get("/leave-calendar", response_model=LeaveCalendarOut)
async def leave_calendar_route(
    from_date: date = Query(...),
    to_date: date = Query(...),
    year_id: uuid.UUID | None = Query(None),
    leave_type_id: uuid.UUID | None = Query(None),
    status: LeaveStatus | None = Query(None),
    principal: Principal = Depends(require("staff.leave.view")),
    session: AsyncSession = Depends(get_session),
) -> LeaveCalendarOut:
    return await get_leave_calendar(
        _context(principal, session),
        {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "year_id": str(year_id) if year_id else None,
            "leave_type_id": str(leave_type_id) if leave_type_id else None,
            "status": status,
        },
    )


__all__ = ["leave_router"]
