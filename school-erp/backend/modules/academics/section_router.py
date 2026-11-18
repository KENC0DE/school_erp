from __future__ import annotations

import uuid
from typing import Literal

from app.errors import Forbidden
from app.logging import request_id_var
from core.actions.registry import ActionContext
from core.api.concurrency import parse_if_match
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.section_actions import (
    create_section,
    delete_section,
    get_section,
    list_sections,
    restore_section,
    update_section,
)
from modules.academics.section_schemas import SectionCreate, SectionList, SectionOut, SectionUpdate

section_router = APIRouter(tags=["academics"])

ScopeQuery = Literal["school", "all"]


def _context(principal: Principal, session: AsyncSession) -> ActionContext:
    return ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )


def _guard(principal: Principal, scope: ScopeQuery, include_inactive: bool) -> None:
    if (scope == "all" or include_inactive) and not principal.can("academics.manage"):
        raise Forbidden(
            "Managing sections requires academics.manage",
            details={"permission": "academics.manage"},
        )


@section_router.get("/sections", response_model=SectionList)
async def get_sections(
    year_id: uuid.UUID | None = Query(None),
    level_id: uuid.UUID | None = Query(None),
    include_inactive: bool = Query(False),
    scope: ScopeQuery = Query("school"),
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> SectionList:
    _guard(principal, scope, include_inactive)
    payload = {
        "year_id": str(year_id) if year_id else None,
        "level_id": str(level_id) if level_id else None,
        "include_inactive": include_inactive,
        "all_scope": scope == "all",
    }
    return await list_sections(_context(principal, session), payload)


@section_router.get("/sections/{section_id}", response_model=SectionOut)
async def get_section_detail(
    section_id: uuid.UUID,
    scope: ScopeQuery = Query("school"),
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> SectionOut:
    _guard(principal, scope, False)
    payload = {"section_id": str(section_id), "all_scope": scope == "all"}
    return await get_section(_context(principal, session), payload)


@section_router.post("/sections", response_model=SectionOut, status_code=201)
async def post_section(
    payload: SectionCreate,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> SectionOut:
    return await create_section(_context(principal, session), payload.model_dump(mode="json"))


@section_router.patch("/sections/{section_id}", response_model=SectionOut)
async def patch_section(
    section_id: uuid.UUID,
    payload: SectionUpdate,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> SectionOut:
    body = {
        **payload.model_dump(mode="json", exclude_unset=True),
        "section_id": str(section_id),
        "reason": reason,
    }
    return await update_section(_context(principal, session), body)


@section_router.delete("/sections/{section_id}", response_model=SectionOut)
async def delete_section_route(
    section_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> SectionOut:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    body = {"section_id": str(section_id), "row_version": expected, "reason": reason}
    return await delete_section(_context(principal, session), body)


@section_router.post("/sections/{section_id}/restore", response_model=SectionOut)
async def restore_section_route(
    section_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> SectionOut:
    body = {"section_id": str(section_id), "reason": reason}
    return await restore_section(_context(principal, session), body)
