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
    approve_correction,
    approve_marks,
    create_assessment,
    create_correction,
    create_grade_scale,
    create_scale_assignment,
    create_structure,
    create_window,
    delete_assessment,
    delete_grade_scale,
    delete_scale_assignment,
    delete_structure,
    delete_window,
    ensure_submission,
    get_assessment,
    get_correction,
    get_grade_scale,
    get_result_snapshot,
    get_structure,
    get_submission,
    get_window,
    lock_marks,
    publish_marks,
    publish_term_results,
    publish_year_results,
    recalculate_structure,
    reject_correction,
    reject_marks,
    republish_term_results,
    republish_year_results,
    score_sheet,
    search_assessments,
    search_corrections,
    search_result_snapshots,
    search_scale_assignments,
    search_scales,
    search_structures,
    search_submissions,
    search_windows,
    structure_impact,
    submit_marks,
    term_results,
    test_grade_scale,
    update_assessment,
    update_grade_scale,
    update_structure,
    update_window,
    upsert_scores,
    year_results,
)
from modules.assessment.schemas import (
    AssessmentCreate,
    AssessmentList,
    AssessmentOut,
    AssessmentQuery,
    AssessmentStatus,
    AssessmentUpdate,
    CorrectionCreate,
    CorrectionDecision,
    CorrectionList,
    CorrectionOut,
    CorrectionQuery,
    CorrectionStatus,
    GradeScaleCreate,
    GradeScaleList,
    GradeScaleOut,
    GradeScaleUpdate,
    ResultSnapshotList,
    ResultSnapshotOut,
    ResultSnapshotQuery,
    ScaleAssignmentInput,
    ScaleAssignmentList,
    ScaleAssignmentOut,
    ScaleTestInput,
    ScaleTestResult,
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
    SubmissionAction,
    SubmissionCreate,
    SubmissionList,
    SubmissionOut,
    SubmissionQuery,
    SubmissionResult,
    SubmissionStatus,
    TermResultPublish,
    TermResultSheet,
    WindowCreate,
    WindowList,
    WindowOut,
    WindowQuery,
    WindowUpdate,
    YearResultPublish,
    YearResultSheet,
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


@router.get("/scales", response_model=GradeScaleList)
async def list_scales_route(
    request: Request,
    include_inactive: bool = Query(False),
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> GradeScaleList:
    return await search_scales(
        _context(principal, session, request),
        {"include_inactive": include_inactive},
    )


@router.post("/scales", response_model=GradeScaleOut, status_code=201)
async def create_scale_route(
    payload: GradeScaleCreate,
    request: Request,
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> GradeScaleOut:
    return await create_grade_scale(_context(principal, session, request), payload.model_dump(mode="json"))


@router.get("/scales/{scale_id}", response_model=GradeScaleOut)
async def get_scale_route(
    scale_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> GradeScaleOut:
    return await get_grade_scale(_context(principal, session, request), {"scale_id": str(scale_id)})


@router.patch("/scales/{scale_id}", response_model=GradeScaleOut)
async def update_scale_route(
    scale_id: uuid.UUID,
    payload: GradeScaleUpdate,
    request: Request,
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> GradeScaleOut:
    return await update_grade_scale(
        _context(principal, session, request),
        {"scale_id": str(scale_id), **payload.model_dump(mode="json")},
    )


@router.delete("/scales/{scale_id}")
async def delete_scale_route(
    scale_id: uuid.UUID,
    request: Request,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> dict:
    return await delete_grade_scale(
        _context(principal, session, request),
        {"scale_id": str(scale_id), "reason": reason},
    )


@router.post("/scales/{scale_id}/test", response_model=ScaleTestResult)
async def test_scale_route(
    scale_id: uuid.UUID,
    payload: ScaleTestInput,
    request: Request,
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> ScaleTestResult:
    return await test_grade_scale(
        _context(principal, session, request),
        {"scale_id": str(scale_id), **payload.model_dump(mode="json")},
    )


@router.get("/scale-assignments", response_model=ScaleAssignmentList)
async def list_scale_assignments_route(
    request: Request,
    scale_id: uuid.UUID | None = Query(None),
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> ScaleAssignmentList:
    return await search_scale_assignments(
        _context(principal, session, request),
        {"scale_id": str(scale_id) if scale_id else None},
    )


@router.post("/scale-assignments", response_model=ScaleAssignmentOut, status_code=201)
async def create_scale_assignment_route(
    payload: ScaleAssignmentInput,
    request: Request,
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> ScaleAssignmentOut:
    return await create_scale_assignment(
        _context(principal, session, request), payload.model_dump(mode="json")
    )


@router.delete("/scale-assignments/{assignment_id}")
async def delete_scale_assignment_route(
    assignment_id: uuid.UUID,
    request: Request,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> dict:
    return await delete_scale_assignment(
        _context(principal, session, request),
        {"assignment_id": str(assignment_id), "reason": reason},
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


@router.get("/windows", response_model=WindowList)
async def list_windows_route(
    request: Request,
    year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    level_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    cursor: str | None = Query(None, max_length=1000),
    sort: str | None = Query(None, max_length=60),
    order: Literal["asc", "desc"] = Query("desc"),
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> WindowList:
    query = WindowQuery(
        year_id=year_id,
        term_id=term_id,
        level_id=level_id,
        section_id=section_id,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
    )
    return await search_windows(_context(principal, session, request), query.model_dump(mode="json"))


@router.post("/windows", response_model=WindowOut, status_code=201)
async def create_window_route(
    payload: WindowCreate,
    request: Request,
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> WindowOut:
    return await create_window(_context(principal, session, request), payload.model_dump(mode="json"))


@router.get("/windows/{window_id}", response_model=WindowOut)
async def get_window_route(
    window_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> WindowOut:
    return await get_window(_context(principal, session, request), {"window_id": str(window_id)})


@router.patch("/windows/{window_id}", response_model=WindowOut)
async def update_window_route(
    window_id: uuid.UUID,
    payload: WindowUpdate,
    request: Request,
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> WindowOut:
    return await update_window(
        _context(principal, session, request),
        {"window_id": str(window_id), **payload.model_dump(mode="json")},
    )


@router.delete("/windows/{window_id}")
async def delete_window_route(
    window_id: uuid.UUID,
    request: Request,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("assessment.manage")),
    session: AsyncSession = Depends(db_session),
) -> dict:
    return await delete_window(
        _context(principal, session, request),
        {"window_id": str(window_id), "reason": reason},
    )


@router.get("/submissions", response_model=SubmissionList)
async def list_submissions_route(
    request: Request,
    year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    status: SubmissionStatus | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    cursor: str | None = Query(None, max_length=1000),
    sort: str | None = Query(None, max_length=60),
    order: Literal["asc", "desc"] = Query("desc"),
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> SubmissionList:
    query = SubmissionQuery(
        year_id=year_id,
        term_id=term_id,
        section_id=section_id,
        subject_id=subject_id,
        status=status,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
    )
    return await search_submissions(_context(principal, session, request), query.model_dump(mode="json"))


@router.post("/submissions", response_model=SubmissionResult)
async def ensure_submission_route(
    payload: SubmissionCreate,
    request: Request,
    principal: Principal = Depends(require("assessment.submit")),
    session: AsyncSession = Depends(db_session),
) -> SubmissionResult:
    return await ensure_submission(_context(principal, session, request), payload.model_dump(mode="json"))


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
async def get_submission_route(
    submission_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> SubmissionOut:
    return await get_submission(_context(principal, session, request), {"submission_id": str(submission_id)})


def _submission_route(action, permission: str):
    async def route(
        submission_id: uuid.UUID,
        payload: SubmissionAction,
        request: Request,
        principal: Principal = Depends(require(permission)),
        session: AsyncSession = Depends(db_session),
    ) -> SubmissionOut:
        return await action(
            _context(principal, session, request),
            {"submission_id": str(submission_id), **payload.model_dump(mode="json")},
        )

    return route


router.add_api_route(
    "/submissions/{submission_id}/submit",
    _submission_route(submit_marks, "assessment.submit"),
    methods=["POST"],
    response_model=SubmissionOut,
)
router.add_api_route(
    "/submissions/{submission_id}/approve",
    _submission_route(approve_marks, "assessment.approve"),
    methods=["POST"],
    response_model=SubmissionOut,
)
router.add_api_route(
    "/submissions/{submission_id}/reject",
    _submission_route(reject_marks, "assessment.approve"),
    methods=["POST"],
    response_model=SubmissionOut,
)
router.add_api_route(
    "/submissions/{submission_id}/publish",
    _submission_route(publish_marks, "assessment.publish"),
    methods=["POST"],
    response_model=SubmissionOut,
)
router.add_api_route(
    "/submissions/{submission_id}/lock",
    _submission_route(lock_marks, "assessment.publish"),
    methods=["POST"],
    response_model=SubmissionOut,
)


@router.get("/corrections", response_model=CorrectionList)
async def list_corrections_route(
    request: Request,
    year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    score_id: uuid.UUID | None = Query(None),
    status: CorrectionStatus | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    cursor: str | None = Query(None, max_length=1000),
    sort: str | None = Query(None, max_length=60),
    order: Literal["asc", "desc"] = Query("desc"),
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> CorrectionList:
    query = CorrectionQuery(
        year_id=year_id,
        term_id=term_id,
        section_id=section_id,
        subject_id=subject_id,
        score_id=score_id,
        status=status,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
    )
    return await search_corrections(_context(principal, session, request), query.model_dump(mode="json"))


@router.post("/corrections", response_model=CorrectionOut, status_code=201)
async def create_correction_route(
    payload: CorrectionCreate,
    request: Request,
    principal: Principal = Depends(require("assessment.correct")),
    session: AsyncSession = Depends(db_session),
) -> CorrectionOut:
    return await create_correction(_context(principal, session, request), payload.model_dump(mode="json"))


@router.get("/corrections/{correction_id}", response_model=CorrectionOut)
async def get_correction_route(
    correction_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> CorrectionOut:
    return await get_correction(_context(principal, session, request), {"correction_id": str(correction_id)})


@router.post("/corrections/{correction_id}/approve", response_model=CorrectionOut)
async def approve_correction_route(
    correction_id: uuid.UUID,
    payload: CorrectionDecision,
    request: Request,
    principal: Principal = Depends(require("assessment.correct_approve")),
    session: AsyncSession = Depends(db_session),
) -> CorrectionOut:
    return await approve_correction(
        _context(principal, session, request),
        {"correction_id": str(correction_id), **payload.model_dump(mode="json")},
    )


@router.post("/corrections/{correction_id}/reject", response_model=CorrectionOut)
async def reject_correction_route(
    correction_id: uuid.UUID,
    payload: CorrectionDecision,
    request: Request,
    principal: Principal = Depends(require("assessment.correct_approve")),
    session: AsyncSession = Depends(db_session),
) -> CorrectionOut:
    return await reject_correction(
        _context(principal, session, request),
        {"correction_id": str(correction_id), **payload.model_dump(mode="json")},
    )


@router.get("/results/term", response_model=TermResultSheet)
async def term_results_route(
    request: Request,
    year_id: uuid.UUID = Query(...),
    term_id: uuid.UUID = Query(...),
    section_id: uuid.UUID = Query(...),
    subject_id: uuid.UUID | None = Query(None),
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> TermResultSheet:
    return await term_results(
        _context(principal, session, request),
        {
            "year_id": str(year_id),
            "term_id": str(term_id),
            "section_id": str(section_id),
            "subject_id": str(subject_id) if subject_id else None,
        },
    )


@router.get("/results/year", response_model=YearResultSheet)
async def year_results_route(
    request: Request,
    year_id: uuid.UUID = Query(...),
    section_id: uuid.UUID = Query(...),
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> YearResultSheet:
    return await year_results(
        _context(principal, session, request),
        {"year_id": str(year_id), "section_id": str(section_id)},
    )


@router.post("/results/term/publish", response_model=ResultSnapshotOut)
async def publish_term_results_route(
    payload: TermResultPublish,
    request: Request,
    principal: Principal = Depends(require("assessment.publish")),
    session: AsyncSession = Depends(db_session),
) -> ResultSnapshotOut:
    return await publish_term_results(_context(principal, session, request), payload.model_dump(mode="json"))


@router.post("/results/term/republish", response_model=ResultSnapshotOut)
async def republish_term_results_route(
    payload: TermResultPublish,
    request: Request,
    principal: Principal = Depends(require("assessment.publish")),
    session: AsyncSession = Depends(db_session),
) -> ResultSnapshotOut:
    return await republish_term_results(
        _context(principal, session, request), payload.model_dump(mode="json")
    )


@router.post("/results/year/publish", response_model=ResultSnapshotOut)
async def publish_year_results_route(
    payload: YearResultPublish,
    request: Request,
    principal: Principal = Depends(require("assessment.publish")),
    session: AsyncSession = Depends(db_session),
) -> ResultSnapshotOut:
    return await publish_year_results(_context(principal, session, request), payload.model_dump(mode="json"))


@router.post("/results/year/republish", response_model=ResultSnapshotOut)
async def republish_year_results_route(
    payload: YearResultPublish,
    request: Request,
    principal: Principal = Depends(require("assessment.publish")),
    session: AsyncSession = Depends(db_session),
) -> ResultSnapshotOut:
    return await republish_year_results(
        _context(principal, session, request), payload.model_dump(mode="json")
    )


@router.get("/results/snapshots", response_model=ResultSnapshotList)
async def list_result_snapshots_route(
    request: Request,
    year_id: uuid.UUID | None = Query(None),
    term_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    student_id: uuid.UUID | None = Query(None),
    kind: Literal["term", "year"] | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    cursor: str | None = Query(None, max_length=1000),
    order: Literal["asc", "desc"] = Query("desc"),
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> ResultSnapshotList:
    query = ResultSnapshotQuery(
        year_id=year_id,
        term_id=term_id,
        section_id=section_id,
        student_id=student_id,
        kind=kind,
        limit=limit,
        cursor=cursor,
        order=order,
    )
    return await search_result_snapshots(_context(principal, session, request), query.model_dump(mode="json"))


@router.get("/results/snapshots/{snapshot_id}", response_model=ResultSnapshotOut)
async def get_result_snapshot_route(
    snapshot_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require("assessment.view")),
    session: AsyncSession = Depends(db_session),
) -> ResultSnapshotOut:
    return await get_result_snapshot(_context(principal, session, request), {"snapshot_id": str(snapshot_id)})


__all__ = ["router"]
