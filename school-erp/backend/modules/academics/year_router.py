from __future__ import annotations

import uuid

from app.logging import request_id_var
from core.actions.registry import ActionContext
from core.api.concurrency import parse_if_match
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.schemas import (
    TermUpdate,
    YearCreate,
    YearList,
    YearOut,
    YearStatus,
    YearUpdate,
)
from modules.academics.year_actions import (
    close_term,
    close_year,
    create_year,
    delete_year,
    get_year,
    list_years,
    open_term,
    open_year,
    restore_year,
    update_term,
    update_year,
)

year_router = APIRouter(tags=["academics"])


def _context(principal: Principal, session: AsyncSession) -> ActionContext:
    return ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )


@year_router.get("/academic-years", response_model=YearList)
async def get_years(
    status: YearStatus | None = Query(None),
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> YearList:
    return await list_years(_context(principal, session), {"status": status})


@year_router.get("/academic-years/{year_id}", response_model=YearOut)
async def get_year_detail(
    year_id: uuid.UUID,
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> YearOut:
    return await get_year(_context(principal, session), {"year_id": str(year_id)})


@year_router.post("/academic-years", response_model=YearOut, status_code=201)
async def post_year(
    payload: YearCreate,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> YearOut:
    return await create_year(_context(principal, session), payload.model_dump())


@year_router.patch("/academic-years/{year_id}", response_model=YearOut)
async def patch_year(
    year_id: uuid.UUID,
    payload: YearUpdate,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> YearOut:
    body = {**payload.model_dump(exclude_unset=True), "year_id": str(year_id), "reason": reason}
    return await update_year(_context(principal, session), body)


@year_router.delete("/academic-years/{year_id}", response_model=YearOut)
async def delete_year_route(
    year_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> YearOut:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    body = {"year_id": str(year_id), "row_version": expected, "reason": reason}
    return await delete_year(_context(principal, session), body)


@year_router.post("/academic-years/{year_id}/restore", response_model=YearOut)
async def restore_year_route(
    year_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> YearOut:
    body = {"year_id": str(year_id), "reason": reason}
    return await restore_year(_context(principal, session), body)


@year_router.post("/academic-years/{year_id}/open", response_model=YearOut)
async def open_year_route(
    year_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> YearOut:
    body = {"year_id": str(year_id), "reason": reason}
    return await open_year(_context(principal, session), body)


@year_router.post("/academic-years/{year_id}/close", response_model=YearOut)
async def close_year_route(
    year_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> YearOut:
    body = {"year_id": str(year_id), "reason": reason}
    return await close_year(_context(principal, session), body)


@year_router.patch("/academic-years/{year_id}/terms/{term_id}", response_model=YearOut)
async def patch_term(
    year_id: uuid.UUID,
    term_id: uuid.UUID,
    payload: TermUpdate,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> YearOut:
    body = {
        **payload.model_dump(exclude_unset=True),
        "year_id": str(year_id),
        "term_id": str(term_id),
        "reason": reason,
    }
    return await update_term(_context(principal, session), body)


@year_router.post("/academic-years/{year_id}/terms/{term_id}/open", response_model=YearOut)
async def open_term_route(
    year_id: uuid.UUID,
    term_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> YearOut:
    body = {"year_id": str(year_id), "term_id": str(term_id), "reason": reason}
    return await open_term(_context(principal, session), body)


@year_router.post("/academic-years/{year_id}/terms/{term_id}/close", response_model=YearOut)
async def close_term_route(
    year_id: uuid.UUID,
    term_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> YearOut:
    body = {"year_id": str(year_id), "term_id": str(term_id), "reason": reason}
    return await close_term(_context(principal, session), body)
