"""Action-registry entry points for mark structures (P4-05)."""

from __future__ import annotations

import uuid

from core.actions.registry import ActionContext, action

from modules.assessment import results, service, workflow
from modules.assessment.schemas import (
    AssessmentCreate,
    AssessmentList,
    AssessmentOut,
    AssessmentQuery,
    AssessmentUpdate,
    CorrectionCreate,
    CorrectionDecision,
    CorrectionList,
    CorrectionOut,
    CorrectionQuery,
    ResultSnapshotList,
    ResultSnapshotOut,
    ResultSnapshotQuery,
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
    TermResultPublish,
    TermResultQuery,
    TermResultSheet,
    WindowCreate,
    WindowList,
    WindowOut,
    WindowQuery,
    WindowUpdate,
    YearResultPublish,
    YearResultQuery,
    YearResultSheet,
)


def _id(payload: dict, key: str) -> uuid.UUID:
    return uuid.UUID(str(payload[key]))


def _body(payload: dict, *path_keys: str) -> dict:
    return {key: value for key, value in payload.items() if key not in path_keys}


@action(
    key="assessment.structures.search",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="List the mark structures of an academic year",
    input=StructureQuery,
    output=StructureList,
)
async def search_structures(ctx: ActionContext, payload: dict | None = None) -> StructureList:
    query = StructureQuery.model_validate(payload or {})
    page = await service.list_structures(ctx.session, query)
    return StructureList(
        items=page.items,
        next_cursor=page.next_cursor,
        total=page.total,
    )


@action(
    key="assessment.structures.get",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="Read one mark structure with its components",
    output=StructureOut,
)
async def get_structure(ctx: ActionContext, payload: dict) -> StructureOut:
    return await service.get_structure(ctx.session, _id(payload, "structure_id"))


@action(
    key="assessment.structures.create",
    module="assessment",
    permission="assessment.manage",
    risk="write",
    describe="Create a mark structure for a year and scope",
    input=StructureCreate,
    output=StructureOut,
)
async def create_structure(ctx: ActionContext, payload: dict) -> StructureOut:
    data = StructureCreate.model_validate(payload)
    return await service.create_structure(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="assessment.structures.update",
    module="assessment",
    permission="assessment.manage",
    risk="write",
    describe="Edit a mark structure and recompute converted values",
    input=StructureUpdate,
    output=StructureUpdateResult,
)
async def update_structure(ctx: ActionContext, payload: dict) -> StructureUpdateResult:
    structure_id = _id(payload, "structure_id")
    data = StructureUpdate.model_validate(_body(payload, "structure_id"))
    return await service.update_structure(
        ctx.session,
        ctx.principal,
        structure_id,
        data,
        via=ctx.via,
        settings=ctx.settings,
    )


@action(
    key="assessment.structures.impact",
    module="assessment",
    permission="assessment.manage",
    risk="read",
    describe="Preview how a structure edit changes converted values",
    input=StructureImpactRequest,
    output=StructureImpact,
)
async def structure_impact(ctx: ActionContext, payload: dict) -> StructureImpact:
    structure_id = _id(payload, "structure_id")
    data = StructureImpactRequest.model_validate(_body(payload, "structure_id"))
    return await service.structure_impact(ctx.session, structure_id, data.components)


@action(
    key="assessment.structures.delete",
    module="assessment",
    permission="assessment.manage",
    risk="destructive",
    describe="Remove a mark structure that has no marks",
    output=dict,
)
async def delete_structure(ctx: ActionContext, payload: dict) -> dict:
    return await service.delete_structure(
        ctx.session,
        ctx.principal,
        _id(payload, "structure_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="assessment.structures.recalculate",
    module="assessment",
    permission="assessment.manage",
    risk="write",
    describe="Recompute converted marks from the current structure",
    output=dict,
)
async def recalculate_structure(ctx: ActionContext, payload: dict) -> dict:
    result = await service.recalculate_structure(ctx.session, _id(payload, "structure_id"))
    return result.model_dump(mode="json")


@action(
    key="assessment.assessments.search",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="List assessments for a year, term, section or subject",
    input=AssessmentQuery,
    output=AssessmentList,
)
async def search_assessments(ctx: ActionContext, payload: dict | None = None) -> AssessmentList:
    query = AssessmentQuery.model_validate(payload or {})
    page = await service.list_assessments(ctx.session, ctx.principal, query)
    return AssessmentList(items=page.items, next_cursor=page.next_cursor, total=page.total)


@action(
    key="assessment.assessments.get",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="Read one assessment",
    output=AssessmentOut,
)
async def get_assessment(ctx: ActionContext, payload: dict) -> AssessmentOut:
    return await service.get_assessment(ctx.session, ctx.principal, _id(payload, "assessment_id"))


@action(
    key="assessment.assessments.create",
    module="assessment",
    permission="assessment.enter_marks",
    risk="write",
    describe="Create an assessment inside a mark structure component",
    input=AssessmentCreate,
    output=AssessmentOut,
)
async def create_assessment(ctx: ActionContext, payload: dict) -> AssessmentOut:
    data = AssessmentCreate.model_validate(payload)
    return await service.create_assessment(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="assessment.assessments.update",
    module="assessment",
    permission="assessment.enter_marks",
    risk="write",
    describe="Edit an assessment before marks make its maximum immutable",
    input=AssessmentUpdate,
    output=AssessmentOut,
)
async def update_assessment(ctx: ActionContext, payload: dict) -> AssessmentOut:
    assessment_id = _id(payload, "assessment_id")
    data = AssessmentUpdate.model_validate(_body(payload, "assessment_id"))
    return await service.update_assessment(ctx.session, ctx.principal, assessment_id, data, via=ctx.via)


@action(
    key="assessment.assessments.delete",
    module="assessment",
    permission="assessment.enter_marks",
    risk="destructive",
    describe="Remove an assessment that has no marks",
    output=dict,
)
async def delete_assessment(ctx: ActionContext, payload: dict) -> dict:
    return await service.delete_assessment(
        ctx.session,
        ctx.principal,
        _id(payload, "assessment_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="assessment.scores.sheet",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="Read the score sheet, roster and statistics for one assessment",
    output=ScoreSheet,
)
async def score_sheet(ctx: ActionContext, payload: dict) -> ScoreSheet:
    return await service.score_sheet(ctx.session, ctx.principal, _id(payload, "assessment_id"))


@action(
    key="assessment.scores.upsert",
    module="assessment",
    permission="assessment.enter_marks",
    risk="write",
    describe="Enter or update scores for one assessment in bulk",
    input=ScoreBulkInput,
    output=ScoreBulkResult,
)
async def upsert_scores(ctx: ActionContext, payload: dict) -> ScoreBulkResult:
    assessment_id = _id(payload, "assessment_id")
    data = ScoreBulkInput.model_validate(_body(payload, "assessment_id"))
    return await service.upsert_scores(ctx.session, ctx.principal, assessment_id, data, via=ctx.via)


@action(
    key="assessment.windows.search",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="List marking windows for a year, term, level or section",
    input=WindowQuery,
    output=WindowList,
)
async def search_windows(ctx: ActionContext, payload: dict | None = None) -> WindowList:
    query = WindowQuery.model_validate(payload or {})
    page = await workflow.list_windows(ctx.session, query)
    return WindowList(items=page.items, next_cursor=page.next_cursor, total=page.total)


@action(
    key="assessment.windows.get",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="Read one marking window",
    output=WindowOut,
)
async def get_window(ctx: ActionContext, payload: dict) -> WindowOut:
    return await workflow.get_window(ctx.session, _id(payload, "window_id"))


@action(
    key="assessment.windows.create",
    module="assessment",
    permission="assessment.manage",
    risk="write",
    describe="Open a marking window for a term, level or section",
    input=WindowCreate,
    output=WindowOut,
)
async def create_window(ctx: ActionContext, payload: dict) -> WindowOut:
    data = WindowCreate.model_validate(payload)
    return await workflow.create_window(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="assessment.windows.update",
    module="assessment",
    permission="assessment.manage",
    risk="write",
    describe="Change a marking window's dates or active state",
    input=WindowUpdate,
    output=WindowOut,
)
async def update_window(ctx: ActionContext, payload: dict) -> WindowOut:
    window_id = _id(payload, "window_id")
    data = WindowUpdate.model_validate(_body(payload, "window_id"))
    return await workflow.update_window(ctx.session, ctx.principal, window_id, data, via=ctx.via)


@action(
    key="assessment.windows.delete",
    module="assessment",
    permission="assessment.manage",
    risk="destructive",
    describe="Remove a marking window",
    output=dict,
)
async def delete_window(ctx: ActionContext, payload: dict) -> dict:
    return await workflow.delete_window(
        ctx.session,
        ctx.principal,
        _id(payload, "window_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="assessment.submissions.search",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="List mark submissions for a year, term, section or subject",
    input=SubmissionQuery,
    output=SubmissionList,
)
async def search_submissions(ctx: ActionContext, payload: dict | None = None) -> SubmissionList:
    query = SubmissionQuery.model_validate(payload or {})
    page = await workflow.list_submissions(ctx.session, ctx.principal, query)
    return SubmissionList(items=page.items, next_cursor=page.next_cursor, total=page.total)


@action(
    key="assessment.submissions.get",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="Read one mark submission and its progress",
    output=SubmissionOut,
)
async def get_submission(ctx: ActionContext, payload: dict) -> SubmissionOut:
    return await workflow.get_submission(ctx.session, ctx.principal, _id(payload, "submission_id"))


@action(
    key="assessment.submissions.ensure",
    module="assessment",
    permission="assessment.submit",
    risk="write",
    describe="Open or reuse the draft submission for a section and subject",
    input=SubmissionCreate,
    output=SubmissionResult,
)
async def ensure_submission(ctx: ActionContext, payload: dict) -> SubmissionResult:
    data = SubmissionCreate.model_validate(payload)
    return await workflow.ensure_submission(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="assessment.submissions.submit",
    module="assessment",
    permission="assessment.submit",
    risk="write",
    describe="Submit a section's marks for review",
    input=SubmissionAction,
    output=SubmissionOut,
)
async def submit_marks(ctx: ActionContext, payload: dict) -> SubmissionOut:
    submission_id = _id(payload, "submission_id")
    data = SubmissionAction.model_validate(_body(payload, "submission_id"))
    return await workflow.submit_marks(ctx.session, ctx.principal, submission_id, data, via=ctx.via)


@action(
    key="assessment.submissions.approve",
    module="assessment",
    permission="assessment.approve",
    risk="write",
    describe="Approve a submitted set of marks",
    input=SubmissionAction,
    output=SubmissionOut,
)
async def approve_marks(ctx: ActionContext, payload: dict) -> SubmissionOut:
    submission_id = _id(payload, "submission_id")
    data = SubmissionAction.model_validate(_body(payload, "submission_id"))
    return await workflow.approve_marks(ctx.session, ctx.principal, submission_id, data, via=ctx.via)


@action(
    key="assessment.submissions.reject",
    module="assessment",
    permission="assessment.approve",
    risk="write",
    describe="Return submitted marks to the teacher",
    input=SubmissionAction,
    output=SubmissionOut,
)
async def reject_marks(ctx: ActionContext, payload: dict) -> SubmissionOut:
    submission_id = _id(payload, "submission_id")
    data = SubmissionAction.model_validate(_body(payload, "submission_id"))
    return await workflow.reject_marks(ctx.session, ctx.principal, submission_id, data, via=ctx.via)


@action(
    key="assessment.submissions.publish",
    module="assessment",
    permission="assessment.publish",
    risk="write",
    describe="Publish approved marks to students and parents",
    input=SubmissionAction,
    output=SubmissionOut,
)
async def publish_marks(ctx: ActionContext, payload: dict) -> SubmissionOut:
    submission_id = _id(payload, "submission_id")
    data = SubmissionAction.model_validate(_body(payload, "submission_id"))
    return await workflow.publish_marks(ctx.session, ctx.principal, submission_id, data, via=ctx.via)


@action(
    key="assessment.submissions.lock",
    module="assessment",
    permission="assessment.publish",
    risk="write",
    describe="Lock published marks against further entry",
    input=SubmissionAction,
    output=SubmissionOut,
)
async def lock_marks(ctx: ActionContext, payload: dict) -> SubmissionOut:
    submission_id = _id(payload, "submission_id")
    data = SubmissionAction.model_validate(_body(payload, "submission_id"))
    return await workflow.lock_marks(ctx.session, ctx.principal, submission_id, data, via=ctx.via)


@action(
    key="assessment.corrections.search",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="List correction requests for a year, term, section or score",
    input=CorrectionQuery,
    output=CorrectionList,
)
async def search_corrections(ctx: ActionContext, payload: dict | None = None) -> CorrectionList:
    query = CorrectionQuery.model_validate(payload or {})
    page = await workflow.list_corrections(ctx.session, ctx.principal, query)
    return CorrectionList(items=page.items, next_cursor=page.next_cursor, total=page.total)


@action(
    key="assessment.corrections.get",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="Read one correction request",
    output=CorrectionOut,
)
async def get_correction(ctx: ActionContext, payload: dict) -> CorrectionOut:
    return await workflow.get_correction(ctx.session, ctx.principal, _id(payload, "correction_id"))


@action(
    key="assessment.corrections.create",
    module="assessment",
    permission="assessment.correct",
    risk="write",
    describe="Request a correction to a locked mark",
    input=CorrectionCreate,
    output=CorrectionOut,
)
async def create_correction(ctx: ActionContext, payload: dict) -> CorrectionOut:
    data = CorrectionCreate.model_validate(payload)
    return await workflow.create_correction(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="assessment.corrections.approve",
    module="assessment",
    permission="assessment.correct_approve",
    risk="write",
    describe="Accept a correction request and rewrite the mark",
    input=CorrectionDecision,
    output=CorrectionOut,
)
async def approve_correction(ctx: ActionContext, payload: dict) -> CorrectionOut:
    correction_id = _id(payload, "correction_id")
    data = CorrectionDecision.model_validate(_body(payload, "correction_id"))
    return await workflow.approve_correction(ctx.session, ctx.principal, correction_id, data, via=ctx.via)


@action(
    key="assessment.corrections.reject",
    module="assessment",
    permission="assessment.correct_approve",
    risk="write",
    describe="Reject a correction request",
    input=CorrectionDecision,
    output=CorrectionOut,
)
async def reject_correction(ctx: ActionContext, payload: dict) -> CorrectionOut:
    correction_id = _id(payload, "correction_id")
    data = CorrectionDecision.model_validate(_body(payload, "correction_id"))
    return await workflow.reject_correction(ctx.session, ctx.principal, correction_id, data, via=ctx.via)


@action(
    key="assessment.results.term",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="Compute a section's live term result sheet and ranks",
    input=TermResultQuery,
    output=TermResultSheet,
)
async def term_results(ctx: ActionContext, payload: dict) -> TermResultSheet:
    data = TermResultQuery.model_validate(payload)
    return await results.term_results(ctx.session, ctx.principal, data)


@action(
    key="assessment.results.year",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="Compute a section's live year result sheet and ranks",
    input=YearResultQuery,
    output=YearResultSheet,
)
async def year_results(ctx: ActionContext, payload: dict) -> YearResultSheet:
    data = YearResultQuery.model_validate(payload)
    return await results.year_results(ctx.session, ctx.principal, data)


@action(
    key="assessment.results.publish_term",
    module="assessment",
    permission="assessment.publish",
    risk="write",
    describe="Publish a term result sheet as an immutable snapshot",
    input=TermResultPublish,
    output=ResultSnapshotOut,
)
async def publish_term_results(ctx: ActionContext, payload: dict) -> ResultSnapshotOut:
    data = TermResultPublish.model_validate(payload)
    return await results.publish_term_results(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="assessment.results.republish_term",
    module="assessment",
    permission="assessment.publish",
    risk="write",
    describe="Publish a corrected term result sheet, superseding the last snapshot",
    input=TermResultPublish,
    output=ResultSnapshotOut,
)
async def republish_term_results(ctx: ActionContext, payload: dict) -> ResultSnapshotOut:
    data = TermResultPublish.model_validate(payload)
    return await results.republish_term_results(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="assessment.results.publish_year",
    module="assessment",
    permission="assessment.publish",
    risk="write",
    describe="Publish a year result sheet as an immutable snapshot",
    input=YearResultPublish,
    output=ResultSnapshotOut,
)
async def publish_year_results(ctx: ActionContext, payload: dict) -> ResultSnapshotOut:
    data = YearResultPublish.model_validate(payload)
    return await results.publish_year_results(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="assessment.results.republish_year",
    module="assessment",
    permission="assessment.publish",
    risk="write",
    describe="Publish a corrected year result sheet, superseding the last snapshot",
    input=YearResultPublish,
    output=ResultSnapshotOut,
)
async def republish_year_results(ctx: ActionContext, payload: dict) -> ResultSnapshotOut:
    data = YearResultPublish.model_validate(payload)
    return await results.republish_year_results(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="assessment.results.snapshots",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="List published result snapshots",
    input=ResultSnapshotQuery,
    output=ResultSnapshotList,
)
async def search_result_snapshots(ctx: ActionContext, payload: dict | None = None) -> ResultSnapshotList:
    query = ResultSnapshotQuery.model_validate(payload or {})
    return await results.list_snapshots(ctx.session, ctx.principal, query)


@action(
    key="assessment.results.snapshot",
    module="assessment",
    permission="assessment.view",
    risk="read",
    describe="Read one published result snapshot",
    output=ResultSnapshotOut,
)
async def get_result_snapshot(ctx: ActionContext, payload: dict) -> ResultSnapshotOut:
    return await results.get_snapshot(ctx.session, ctx.principal, _id(payload, "snapshot_id"))


__all__ = [
    "approve_correction",
    "approve_marks",
    "create_assessment",
    "create_correction",
    "create_structure",
    "create_window",
    "delete_assessment",
    "delete_structure",
    "delete_window",
    "ensure_submission",
    "get_assessment",
    "get_correction",
    "get_result_snapshot",
    "get_structure",
    "get_submission",
    "get_window",
    "lock_marks",
    "publish_marks",
    "publish_term_results",
    "publish_year_results",
    "recalculate_structure",
    "reject_correction",
    "reject_marks",
    "republish_term_results",
    "republish_year_results",
    "score_sheet",
    "search_assessments",
    "search_corrections",
    "search_result_snapshots",
    "search_structures",
    "search_submissions",
    "search_windows",
    "structure_impact",
    "submit_marks",
    "term_results",
    "update_assessment",
    "update_structure",
    "update_window",
    "upsert_scores",
    "year_results",
]
