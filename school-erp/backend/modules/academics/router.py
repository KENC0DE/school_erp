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

from modules.academics.actions import (
    create_level,
    create_stage,
    delete_level,
    delete_stage,
    get_level,
    get_scope,
    get_stage,
    list_levels,
    list_stages,
    restore_level,
    restore_stage,
    update_level,
    update_scope,
    update_stage,
)
from modules.academics.curriculum_router import curriculum_router
from modules.academics.schemas import (
    LevelCreate,
    LevelList,
    LevelOut,
    LevelUpdate,
    ScopeOut,
    ScopeUpdate,
    StageCreate,
    StageList,
    StageOut,
    StageUpdate,
)
from modules.academics.section_router import section_router
from modules.academics.subject_router import subject_router
from modules.academics.year_router import year_router

router = APIRouter(tags=["academics"])
router.include_router(year_router)
router.include_router(subject_router)
router.include_router(section_router)
router.include_router(curriculum_router)

ScopeQuery = Literal["school", "all"]


def _context(principal: Principal, session: AsyncSession) -> ActionContext:
    return ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )


def _authorise_catalog_scope(principal: Principal, scope: ScopeQuery, include_inactive: bool) -> None:
    """Only catalog managers may look outside the school's scope or at inactive rows."""
    if (scope == "all" or include_inactive) and not principal.can("academics.manage"):
        raise Forbidden(
            "Managing the catalog requires academics.manage",
            details={"permission": "academics.manage"},
        )


@router.get("/levels", response_model=LevelList)
async def get_levels(
    scope: ScopeQuery = Query("school"),
    include_inactive: bool = Query(False),
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> LevelList:
    _authorise_catalog_scope(principal, scope, include_inactive)
    return await list_levels(
        _context(principal, session),
        {"all_scope": scope == "all", "include_inactive": include_inactive},
    )


@router.get("/levels/{level_id}", response_model=LevelOut)
async def get_level_detail(
    level_id: uuid.UUID,
    scope: ScopeQuery = Query("school"),
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> LevelOut:
    _authorise_catalog_scope(principal, scope, False)
    return await get_level(
        _context(principal, session),
        {"level_id": str(level_id), "all_scope": scope == "all"},
    )


@router.post("/levels", response_model=LevelOut, status_code=201)
async def post_level(
    payload: LevelCreate,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> LevelOut:
    return await create_level(_context(principal, session), payload.model_dump())


@router.patch("/levels/{level_id}", response_model=LevelOut)
async def patch_level(
    level_id: uuid.UUID,
    payload: LevelUpdate,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> LevelOut:
    body = {**payload.model_dump(exclude_unset=True), "level_id": str(level_id)}
    return await update_level(_context(principal, session), body)


@router.delete("/levels/{level_id}", response_model=LevelOut)
async def delete_level_route(
    level_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> LevelOut:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    body = {"level_id": str(level_id), "row_version": expected, "reason": reason}
    return await delete_level(_context(principal, session), body)


@router.post("/levels/{level_id}/restore", response_model=LevelOut)
async def restore_level_route(
    level_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> LevelOut:
    return await restore_level(
        _context(principal, session),
        {"level_id": str(level_id), "reason": reason},
    )


@router.get("/stages", response_model=StageList)
async def get_stages(
    scope: ScopeQuery = Query("school"),
    include_inactive: bool = Query(False),
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> StageList:
    _authorise_catalog_scope(principal, scope, include_inactive)
    return await list_stages(
        _context(principal, session),
        {"all_scope": scope == "all", "include_inactive": include_inactive},
    )


@router.get("/stages/{stage_id}", response_model=StageOut)
async def get_stage_detail(
    stage_id: uuid.UUID,
    scope: ScopeQuery = Query("school"),
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> StageOut:
    _authorise_catalog_scope(principal, scope, False)
    return await get_stage(
        _context(principal, session),
        {"stage_id": str(stage_id), "all_scope": scope == "all"},
    )


@router.post("/stages", response_model=StageOut, status_code=201)
async def post_stage(
    payload: StageCreate,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> StageOut:
    return await create_stage(_context(principal, session), payload.model_dump())


@router.patch("/stages/{stage_id}", response_model=StageOut)
async def patch_stage(
    stage_id: uuid.UUID,
    payload: StageUpdate,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> StageOut:
    body = {**payload.model_dump(exclude_unset=True), "stage_id": str(stage_id)}
    return await update_stage(_context(principal, session), body)


@router.delete("/stages/{stage_id}", response_model=StageOut)
async def delete_stage_route(
    stage_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> StageOut:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    body = {"stage_id": str(stage_id), "row_version": expected, "reason": reason}
    return await delete_stage(_context(principal, session), body)


@router.post("/stages/{stage_id}/restore", response_model=StageOut)
async def restore_stage_route(
    stage_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> StageOut:
    return await restore_stage(
        _context(principal, session),
        {"stage_id": str(stage_id), "reason": reason},
    )


@router.get("/scope", response_model=ScopeOut)
async def get_academic_scope(
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> ScopeOut:
    return await get_scope(_context(principal, session), {})


@router.put("/scope", response_model=ScopeOut)
async def put_academic_scope(
    payload: ScopeUpdate,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> ScopeOut:
    return await update_scope(_context(principal, session), payload.model_dump())
