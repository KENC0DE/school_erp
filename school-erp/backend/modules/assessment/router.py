"""HTTP routes for mark structures, assessments and scores (P4-05, P4-06)."""

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
    create_assessment,
    create_structure,
    delete_assessment,
    delete_structure,
    get_assessment,
    get_structure,
    recalculate_structure,
    score_sheet,
    search_assessments,
    search_structures,
    structure_impact,
    update_assessment,
    update_structure,
    upsert_scores,
)
from modules.assessment.schemas import (
    AssessmentCreate,
    AssessmentList,
    AssessmentOut,
    AssessmentQuery,
    AssessmentStatus,
    AssessmentUpdate,
    ScoreBulkInput,
    ScoreBulkResult,
    ScoreSheet,
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


@router.get("/assessments", response_model=AssessmentList)
async def list_assessments_route(
    request: Request,
    year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    component_id: uuid.UUID | None = Query(None),
    status: AssessmentStatus | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    cursor: str | None = Query(None, max_length=1000),
    sort: str | None = Query(None, max_length=60),
    order: Literal["asc", "desc"] = Query("desc"),
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> AssessmentList:
    query = AssessmentQuery(
        year_id=year_id,
        term_id=term_id,
        section_id=section_id,
        subject_id=subject_id,
        component_id=component_id,
        status=status,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
    )
    return await search_assessments(_context(principal, session, request), query.model_dump(mode="json"))


@router.post("/assessments", response_model=AssessmentOut, status_code=201)
async def create_assessment_route(
    payload: AssessmentCreate,
    request: Request,
    principal: Principal = Depends(require("assessment.enter_marks")),
    session: AsyncSession = Depends(db_session),
) -> AssessmentOut:
    return await create_assessment(
        _context(principal, session, request),
        payload.model_dump(mode="json"),
    )


@router.get("/assessments/{assessment_id}", response_model=AssessmentOut)
async def get_assessment_route(
    assessment_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> AssessmentOut:
    return await get_assessment(
        _context(principal, session, request),
        {"assessment_id": str(assessment_id)},
    )


@router.patch("/assessments/{assessment_id}", response_model=AssessmentOut)
async def update_assessment_route(
    assessment_id: uuid.UUID,
    payload: AssessmentUpdate,
    request: Request,
    principal: Principal = Depends(require("assessment.enter_marks")),
    session: AsyncSession = Depends(db_session),
) -> AssessmentOut:
    return await update_assessment(
        _context(principal, session, request),
        {"assessment_id": str(assessment_id), **payload.model_dump(mode="json")},
    )


@router.delete("/assessments/{assessment_id}")
async def delete_assessment_route(
    assessment_id: uuid.UUID,
    request: Request,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("assessment.enter_marks")),
    session: AsyncSession = Depends(db_session),
) -> dict:
    return await delete_assessment(
        _context(principal, session, request),
        {"assessment_id": str(assessment_id), "reason": reason},
    )


@router.get("/assessments/{assessment_id}/scores", response_model=ScoreSheet)
async def score_sheet_route(
    assessment_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> ScoreSheet:
    return await score_sheet(
        _context(principal, session, request),
        {"assessment_id": str(assessment_id)},
    )


@router.put("/assessments/{assessment_id}/scores", response_model=ScoreBulkResult)
async def upsert_scores_route(
    assessment_id: uuid.UUID,
    payload: ScoreBulkInput,
    request: Request,
    principal: Principal = Depends(require("assessment.enter_marks")),
    session: AsyncSession = Depends(db_session),
) -> ScoreBulkResult:
    return await upsert_scores(
        _context(principal, session, request),
        {"assessment_id": str(assessment_id), **payload.model_dump(mode="json")},
    )


__all__ = ["router"]
