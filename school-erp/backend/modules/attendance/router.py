"""HTTP routes for attendance registers and entries."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from app.logging import request_id_var
from core.actions.registry import ActionContext
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session as db_session
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from modules.attendance.actions import (
    create_session,
    delete_session,
    get_session,
    lock_session,
    reopen_session,
    search_sessions,
    section_report,
    student_report,
    submit_session,
    update_record,
    update_session,
    upsert_records,
)
from modules.attendance.schemas import (
    AttendanceReportQuery,
    BulkRecordsInput,
    RecordUpdate,
    SectionAttendanceReport,
    SessionCreate,
    SessionDetail,
    SessionList,
    SessionQuery,
    SessionStatus,
    SessionUpdate,
    StudentAttendanceReport,
)

router = APIRouter(tags=["attendance"])


def _context(principal: Principal, session: AsyncSession) -> ActionContext:
    return ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )


def _with(payload: dict, **values) -> dict:
    return {**payload, **values}


@router.get("", response_model=SessionList)
async def list_sessions_route(
    year_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    status: SessionStatus | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    cursor: str | None = Query(None, max_length=1000),
    sort: str | None = Query(None, max_length=60),
    order: Literal["asc", "desc"] = Query("desc"),
    principal: Principal = Depends(require("attendance.view")),
    session: AsyncSession = Depends(db_session),
) -> SessionList:
    query = SessionQuery(
        year_id=year_id,
        section_id=section_id,
        from_date=from_date,
        to_date=to_date,
        status=status,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
    )
    return await search_sessions(_context(principal, session), query.model_dump())


@router.post("", response_model=SessionDetail, status_code=201)
async def create_session_route(
    payload: SessionCreate,
    principal: Principal = Depends(require("attendance.record")),
    session: AsyncSession = Depends(db_session),
) -> SessionDetail:
    return await create_session(_context(principal, session), payload.model_dump())


@router.get("/reports/students", response_model=StudentAttendanceReport)
async def student_report_route(
    from_date: date = Query(...),
    to_date: date = Query(...),
    year_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    student_id: uuid.UUID | None = Query(None),
    threshold: int = Query(85, ge=0, le=100),
    below_only: bool = Query(False),
    limit: int = Query(500, ge=1, le=2000),
    principal: Principal = Depends(require("attendance.view")),
    session: AsyncSession = Depends(db_session),
) -> StudentAttendanceReport:
    query = AttendanceReportQuery(
        from_date=from_date,
        to_date=to_date,
        year_id=year_id,
        section_id=section_id,
        student_id=student_id,
        threshold=threshold,
        below_only=below_only,
        limit=limit,
    )
    return await student_report(_context(principal, session), query.model_dump(mode="json"))


@router.get("/reports/sections", response_model=SectionAttendanceReport)
async def section_report_route(
    from_date: date = Query(...),
    to_date: date = Query(...),
    year_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    student_id: uuid.UUID | None = Query(None),
    threshold: int = Query(85, ge=0, le=100),
    below_only: bool = Query(False),
    limit: int = Query(500, ge=1, le=2000),
    principal: Principal = Depends(require("attendance.view")),
    session: AsyncSession = Depends(db_session),
) -> SectionAttendanceReport:
    query = AttendanceReportQuery(
        from_date=from_date,
        to_date=to_date,
        year_id=year_id,
        section_id=section_id,
        student_id=student_id,
        threshold=threshold,
        below_only=below_only,
        limit=limit,
    )
    return await section_report(_context(principal, session), query.model_dump(mode="json"))


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session_route(
    session_id: uuid.UUID,
    principal: Principal = Depends(require("attendance.view")),
    session: AsyncSession = Depends(db_session),
) -> SessionDetail:
    return await get_session(_context(principal, session), {"session_id": str(session_id)})


@router.patch("/{session_id}", response_model=SessionDetail)
async def update_session_route(
    session_id: uuid.UUID,
    payload: SessionUpdate,
    principal: Principal = Depends(require("attendance.record")),
    session: AsyncSession = Depends(db_session),
) -> SessionDetail:
    return await update_session(
        _context(principal, session),
        _with(payload.model_dump(), session_id=str(session_id)),
    )


@router.delete("/{session_id}")
async def delete_session_route(
    session_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("attendance.manage")),
    session: AsyncSession = Depends(db_session),
) -> dict:
    return await delete_session(
        _context(principal, session),
        _with({"reason": reason}, session_id=str(session_id)),
    )


@router.post("/{session_id}/submit", response_model=SessionDetail)
async def submit_session_route(
    session_id: uuid.UUID,
    principal: Principal = Depends(require("attendance.record")),
    session: AsyncSession = Depends(db_session),
) -> SessionDetail:
    return await submit_session(_context(principal, session), {"session_id": str(session_id)})


@router.post("/{session_id}/lock", response_model=SessionDetail)
async def lock_session_route(
    session_id: uuid.UUID,
    principal: Principal = Depends(require("attendance.manage")),
    session: AsyncSession = Depends(db_session),
) -> SessionDetail:
    return await lock_session(_context(principal, session), {"session_id": str(session_id)})


@router.post("/{session_id}/reopen", response_model=SessionDetail)
async def reopen_session_route(
    session_id: uuid.UUID,
    principal: Principal = Depends(require("attendance.manage")),
    session: AsyncSession = Depends(db_session),
) -> SessionDetail:
    return await reopen_session(_context(principal, session), {"session_id": str(session_id)})


@router.post("/{session_id}/records", response_model=SessionDetail)
async def upsert_records_route(
    session_id: uuid.UUID,
    payload: BulkRecordsInput,
    principal: Principal = Depends(require("attendance.record")),
    session: AsyncSession = Depends(db_session),
) -> SessionDetail:
    return await upsert_records(
        _context(principal, session),
        _with(payload.model_dump(), session_id=str(session_id)),
    )


@router.patch("/{session_id}/records/{record_id}", response_model=SessionDetail)
async def update_record_route(
    session_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: RecordUpdate,
    principal: Principal = Depends(require("attendance.record")),
    session: AsyncSession = Depends(db_session),
) -> SessionDetail:
    return await update_record(
        _context(principal, session),
        _with(payload.model_dump(), session_id=str(session_id), record_id=str(record_id)),
    )


__all__ = ["router"]
