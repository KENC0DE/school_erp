"""HTTP routes for mark structures (P4-05)."""

from __future__ import annotations

import uuid
from typing import Literal

from app.logging import request_id_var
from core.actions.registry import ActionContext
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session as db_session
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from modules.assessment.actions import (
    create_structure,
    delete_structure,
    get_structure,
    recalculate_structure,
    search_structures,
    structure_impact,
    update_structure,
)
from modules.assessment.schemas import (
    StructureCreate,
    StructureImpact,
    StructureImpactRequest,
    StructureList,
    StructureOut,
    StructureQuery,
    StructureUpdate,
    StructureUpdateResult,
)

router = APIRouter(tags=["assessment"])


def _context(
    principal: Principal,
    session: AsyncSession,
    request: Request,
) -> ActionContext:
    return ActionContext(
        principal=principal,
        session=session,
        via=principal.via,
        request_id=request_id_var.get(),
        request=request,
        settings=request.app.state.settings,
    )


@router.get("/structures", response_model=StructureList)
async def list_structures_route(
    request: Request,
    year_id: uuid.UUID | None = Query(None),
    scope_type: Literal["school", "stage", "level", "subject"] | None = Query(None),
    level_id: uuid.UUID | None = Query(None),
    stage_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    cursor: str | None = Query(None, max_length=1000),
    sort: str | None = Query(None, max_length=60),
    order: Literal["asc", "desc"] = Query("desc"),
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> StructureList:
    query = StructureQuery(
        year_id=year_id,
        scope_type=scope_type,
        level_id=level_id,
        stage_id=stage_id,
        subject_id=subject_id,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
    )
    return await search_structures(_context(principal, session, request), query.model_dump(mode="json"))


@router.post("/structures", response_model=StructureOut, status_code=201)
async def create_structure_route(
    payload: StructureCreate,
    request: Request,
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> StructureOut:
    return await create_structure(_context(principal, session, request), payload.model_dump(mode="json"))


@router.get("/structures/{structure_id}", response_model=StructureOut)
async def get_structure_route(
    structure_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> StructureOut:
    return await get_structure(
        _context(principal, session, request),
        {"structure_id": str(structure_id)},
    )


@router.patch("/structures/{structure_id}", response_model=StructureUpdateResult)
async def update_structure_route(
    structure_id: uuid.UUID,
    payload: StructureUpdate,
    request: Request,
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> StructureUpdateResult:
    return await update_structure(
        _context(principal, session, request),
        {"structure_id": str(structure_id), **payload.model_dump(mode="json")},
    )


@router.post("/structures/{structure_id}/impact", response_model=StructureImpact)
async def structure_impact_route(
    structure_id: uuid.UUID,
    payload: StructureImpactRequest,
    request: Request,
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> StructureImpact:
    return await structure_impact(
        _context(principal, session, request),
        {"structure_id": str(structure_id), **payload.model_dump(mode="json")},
    )


@router.post("/structures/{structure_id}/recalculate", response_model=dict)
async def recalculate_structure_route(
    structure_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> dict:
    return await recalculate_structure(
        _context(principal, session, request),
        {"structure_id": str(structure_id)},
    )


@router.delete("/structures/{structure_id}")
async def delete_structure_route(
    structure_id: uuid.UUID,
    request: Request,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> dict:
    return await delete_structure(
        _context(principal, session, request),
        {"structure_id": str(structure_id), "reason": reason},
    )


__all__ = ["router"]
