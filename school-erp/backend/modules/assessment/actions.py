"""Action-registry entry points for mark structures (P4-05)."""

from __future__ import annotations

import uuid

from core.actions.registry import ActionContext, action

from modules.assessment import service
from modules.assessment.schemas import (
    AssessmentCreate,
    AssessmentList,
    AssessmentOut,
    AssessmentQuery,
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


__all__ = [
    "create_assessment",
    "create_structure",
    "delete_assessment",
    "delete_structure",
    "get_assessment",
    "get_structure",
    "recalculate_structure",
    "score_sheet",
    "search_assessments",
    "search_structures",
    "structure_impact",
    "update_assessment",
    "update_structure",
    "upsert_scores",
]
