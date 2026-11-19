"""Mark structures: create, edit, impact preview and recalculation (P4-05).

A structure is configuration: component maxima, aggregation, the year rule and
rounding. Changing it never touches a raw score. The only derived value that
follows is ``Score.converted``, which a background job recomputes from the raw
value so a report can never disagree with the structure that produced it.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.api.pagination import Page, PageParams, paginate
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import mark_deleted, soft_delete
from core.events import service as events
from core.people.models import Person
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear, GradeLevel, Section, Stage, Subject, Term
from modules.assessment import common, scoping, workflow
from modules.assessment.common import MODULE, decimal_out, structure_state
from modules.assessment.engine import round_mark
from modules.assessment.models import (
    Assessment,
    AssessmentComponent,
    AssessmentStructure,
    Score,
    ScoreRevision,
)
from modules.assessment.schemas import (
    AssessmentCreate,
    AssessmentOut,
    AssessmentQuery,
    AssessmentUpdate,
    ComponentInput,
    ComponentOut,
    ImpactSample,
    RecalculationResult,
    ScoreBulkInput,
    ScoreBulkResult,
    ScoreInput,
    ScoreOut,
    ScoreSheet,
    ScoreStats,
    StructureCreate,
    StructureImpact,
    StructureOut,
    StructureQuery,
    StructureUpdate,
    StructureUpdateResult,
)
from modules.students.models import StudentProfile

SORT_COLUMNS = {
    "created_at": AssessmentStructure.created_at,
    "name": AssessmentStructure.name,
    "version": AssessmentStructure.version,
}
CONVERSION_FIELDS = {"precision", "rounding"}
CONVERSION_COMPONENT_KEYS = (
    "key",
    "max_points",
    "aggregation",
    "absent_counts_as_zero",
    "best_n",
    "cap",
)
STRUCTURE_FIELDS = {
    "name",
    "name_am",
    "year_mode",
    "year_weights",
    "precision",
    "rounding",
    "intended_total",
    "descriptive_mode",
    "notes",
    "is_active",
}


def _component_out(row: AssessmentComponent) -> ComponentOut:
    return ComponentOut(
        id=str(row.id),
        key=row.key,
        name=row.name,
        name_am=row.name_am,
        max_points=decimal_out(row.max_points) or "0",
        aggregation=row.aggregation,
        absent_counts_as_zero=row.absent_counts_as_zero,
        best_n=row.best_n,
        cap=decimal_out(row.cap),
        sort_order=row.sort_order,
        is_active=row.is_active,
        row_version=row.row_version,
    )


def _total(rows: list[AssessmentComponent]) -> Decimal:
    return sum((row.max_points for row in rows), Decimal(0))


def _conversion_differs(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> bool:
    """True when a component edit can change a converted value."""

    def view(items: list[dict[str, Any]]) -> dict[str, tuple[Any, ...]]:
        return {
            item["key"]: tuple(item[key] for key in CONVERSION_COMPONENT_KEYS) + (item["is_active"],)
            for item in items
        }

    return view(before) != view(after)


def _structure_out(
    row: AssessmentStructure,
    year: AcademicYear,
    components: list[AssessmentComponent],
    labels: dict[str, Any],
) -> StructureOut:
    total = _total(components)
    intended = row.intended_total
    return StructureOut(
        id=str(row.id),
        year_id=str(row.year_id),
        year_code=year.code,
        scope_type=row.scope_type,
        scope_key=row.scope_key,
        level_id=str(row.level_id) if row.level_id else None,
        level_name=labels["level"],
        stage_id=str(row.stage_id) if row.stage_id else None,
        stage_name=labels["stage"],
        subject_id=str(row.subject_id) if row.subject_id else None,
        subject_name=labels["subject"],
        name=row.name,
        name_am=row.name_am,
        term_system=row.term_system,
        year_mode=row.year_mode,
        year_weights=[decimal_out(Decimal(weight)) or weight for weight in row.year_weights or []],
        precision=row.precision,
        rounding=row.rounding,
        intended_total=decimal_out(intended),
        total=decimal_out(total) or "0",
        total_matches=intended is None or total == intended,
        descriptive_mode=row.descriptive_mode,
        version=row.version,
        is_active=row.is_active,
        row_version=row.row_version,
        components=[_component_out(component) for component in components],
    )


async def _labels(session: AsyncSession, row: AssessmentStructure) -> dict[str, Any]:
    labels: dict[str, Any] = {"level": None, "stage": None, "subject": None}
    if row.level_id is not None:
        level = await session.get(GradeLevel, row.level_id)
        labels["level"] = level.name if level is not None and level.deleted_at is None else None
    if row.stage_id is not None:
        stage = await session.get(Stage, row.stage_id)
        labels["stage"] = stage.name if stage is not None and stage.deleted_at is None else None
    if row.subject_id is not None:
        subject = await session.get(Subject, row.subject_id)
        labels["subject"] = subject.name if subject is not None and subject.deleted_at is None else None
    return labels


async def _detail(session: AsyncSession, row: AssessmentStructure) -> StructureOut:
    year = await common.live_year(session, row.year_id)
    components = await common.structure_components(session, row.id)
    return _structure_out(row, year, components, await _labels(session, row))


async def _assert_unique_scope(
    session: AsyncSession,
    year_id: uuid.UUID,
    key: str,
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    stmt = select(AssessmentStructure.id).where(
        AssessmentStructure.year_id == year_id,
        AssessmentStructure.scope_key == key,
        AssessmentStructure.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(AssessmentStructure.id != exclude_id)
    if (await session.execute(stmt)).first() is not None:
        raise Conflict(
            "A structure already exists for that year and scope",
            message_key="assessment.error.duplicate_structure",
        )


async def _validate_target(
    session: AsyncSession,
    scope_type: str,
    *,
    level_id: uuid.UUID | None,
    stage_id: uuid.UUID | None,
    subject_id: uuid.UUID | None,
) -> str:
    try:
        key = common.scope_key(scope_type, level_id=level_id, stage_id=stage_id, subject_id=subject_id)
    except ValidationFailed:
        raise
    if scope_type == "level" and level_id is not None:
        await common.live_level(session, level_id)
    elif scope_type == "stage" and stage_id is not None:
        await common.live_stage(session, stage_id)
    elif scope_type == "subject" and subject_id is not None:
        await common.live_subject(session, subject_id)
    return key


def _check_totals(components: list[ComponentInput], intended: Decimal | None) -> None:
    seen: set[str] = set()
    total = Decimal(0)
    for component in components:
        if component.key in seen:
            raise Conflict(
                "That component key is already used in this structure",
                message_key="assessment.error.duplicate_component",
                details={"key": component.key},
            )
        seen.add(component.key)
        total += component.max_points
    if intended is not None and total > intended:
        raise ValidationFailed(
            "The components add up to more than the intended total",
            message_key="assessment.error.component_sum",
            details={"total": decimal_out(total), "intended": decimal_out(intended)},
        )


async def _check_year_rule(
    session: AsyncSession,
    year_id: uuid.UUID,
    mode: str,
    weights: list[Decimal] | None,
) -> None:
    if mode != "weighted_average":
        if weights:
            raise ValidationFailed(
                "Year weights only apply to a weighted year result",
                message_key="assessment.error.year_weights_unused",
            )
        return
    if not weights:
        raise ValidationFailed(
            "A weighted year result needs one weight per term",
            message_key="assessment.error.year_weights_required",
        )
    count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Term)
                .where(Term.year_id == year_id, Term.deleted_at.is_(None))
            )
        ).scalar_one()
    )
    if len(weights) != count:
        raise ValidationFailed(
            "A weighted year result needs one weight per term",
            message_key="assessment.error.year_weights_required",
            details={"expected": count, "received": len(weights)},
        )


async def _apply_components(
    session: AsyncSession,
    structure: AssessmentStructure,
    principal: Principal,
    inputs: list[ComponentInput],
) -> list[AssessmentComponent]:
    existing = await common.structure_components(session, structure.id)
    by_id = {row.id: row for row in existing}
    by_key = {row.key: row for row in existing}
    actor_id = uuid.UUID(principal.user_id) if principal.actor_type == "user" else None
    kept_keys: set[str] = set()
    order = 0
    for item in inputs:
        target = by_id.get(item.id) if item.id is not None else None
        if target is None:
            target = by_key.get(item.key)
        if item.id is not None and target is None:
            raise NotFound(
                "That component does not belong to this structure",
                message_key="assessment.error.component_not_found",
            )
        if target is not None and target.structure_id != structure.id:
            raise ValidationFailed(
                "That component belongs to another structure",
                message_key="assessment.error.component_structure",
            )
        if target is not None and target.key != item.key:
            raise ValidationFailed(
                "A component key cannot change; add a new component instead",
                message_key="assessment.error.component_key_immutable",
                details={"key": target.key, "requested": item.key},
            )
        if target is None:
            target = AssessmentComponent(
                structure_id=structure.id,
                key=item.key,
                created_by=actor_id,
                updated_by=actor_id,
            )
            session.add(target)
        target.name = item.name
        target.name_am = item.name_am
        target.max_points = item.max_points
        target.aggregation = item.aggregation
        target.absent_counts_as_zero = item.absent_counts_as_zero
        target.best_n = item.best_n
        target.cap = item.cap
        target.sort_order = item.sort_order if item.sort_order is not None else order
        target.is_active = item.is_active
        target.updated_by = actor_id
        kept_keys.add(item.key)
        order += 1
    for row in existing:
        if row.key in kept_keys:
            continue
        if await _component_in_use(session, row.id):
            raise Conflict(
                "That component already has marks and cannot be removed",
                message_key="assessment.error.component_in_use",
                details={"key": row.key},
            )
        mark_deleted(row, actor=principal)
    await session.flush()
    return await common.structure_components(session, structure.id)


async def _component_in_use(session: AsyncSession, component_id: uuid.UUID) -> bool:
    count = (
        await session.execute(
            select(func.count())
            .select_from(Assessment)
            .where(
                Assessment.component_id == component_id,
                Assessment.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    return int(count) > 0


async def create_structure(
    session: AsyncSession,
    principal: Principal,
    data: StructureCreate,
    *,
    via: str = "api",
) -> StructureOut:
    year = await common.live_year(session, data.year_id)
    key = await _validate_target(
        session,
        data.scope_type,
        level_id=data.level_id,
        stage_id=data.stage_id,
        subject_id=data.subject_id,
    )
    if data.term_system is not None and data.term_system != year.term_system:
        raise ValidationFailed(
            "A structure inherits its term system from the academic year",
            message_key="assessment.error.term_system_mismatch",
            details={"year_term_system": year.term_system, "received": data.term_system},
        )
    await _assert_unique_scope(session, year.id, key)
    _check_totals(data.components, data.intended_total)
    await _check_year_rule(session, year.id, data.year_mode, data.year_weights)
    actor_id = uuid.UUID(principal.user_id) if principal.actor_type == "user" else None
    row = AssessmentStructure(
        year_id=year.id,
        scope_type=data.scope_type,
        scope_key=key,
        level_id=data.level_id,
        stage_id=data.stage_id,
        subject_id=data.subject_id,
        name=data.name,
        name_am=data.name_am,
        term_system=year.term_system,
        year_mode=data.year_mode,
        year_weights=[str(weight) for weight in data.year_weights] if data.year_weights else None,
        precision=data.precision,
        rounding=data.rounding,
        intended_total=data.intended_total,
        descriptive_mode=data.descriptive_mode,
        notes=data.notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    components = await _apply_components(session, row, principal, data.components)
    await record(
        session,
        action="assessment.structure.create",
        module=MODULE,
        entity_type="assessment_structure",
        entity_id=str(row.id),
        after={
            **structure_state(row),
            "components": [common.component_state(component) for component in components],
        },
        actor=principal,
        via=via,
    )
    await session.commit()
    return _structure_out(row, year, components, await _labels(session, row))


async def update_structure(
    session: AsyncSession,
    principal: Principal,
    structure_id: uuid.UUID,
    data: StructureUpdate,
    *,
    via: str = "api",
    settings: Any | None = None,
) -> StructureUpdateResult:
    row = await common.live_structure(session, structure_id)
    before = {
        **structure_state(row),
        "components": [
            common.component_state(component)
            for component in await common.structure_components(session, row.id)
        ],
    }
    ensure_row_version(row, data.row_version, current_state=before)
    year = await common.live_year(session, row.year_id)

    scope_type = data.scope_type or row.scope_type
    level_id = data.level_id if data.level_id is not None else row.level_id
    stage_id = data.stage_id if data.stage_id is not None else row.stage_id
    subject_id = data.subject_id if data.subject_id is not None else row.subject_id
    if scope_type == "school":
        level_id = stage_id = subject_id = None
    elif scope_type != row.scope_type:
        # A scope change must name its own target; stale ids from the old scope
        # would silently point at the wrong catalog row.
        level_id = data.level_id
        stage_id = data.stage_id
        subject_id = data.subject_id
    key = await _validate_target(
        session,
        scope_type,
        level_id=level_id,
        stage_id=stage_id,
        subject_id=subject_id,
    )
    if key != row.scope_key:
        await _assert_unique_scope(session, row.year_id, key, exclude_id=row.id)

    values = data.model_dump(
        exclude={"row_version", "reason", "components", "scope_type", "level_id", "stage_id", "subject_id"}
    )
    touched = False
    for field, value in values.items():
        if field in STRUCTURE_FIELDS and value is not None and getattr(row, field) != value:
            setattr(row, field, value)
            touched = True
    if data.year_weights is not None:
        row.year_weights = [str(weight) for weight in data.year_weights]
        touched = True
    if data.year_mode is not None and data.year_mode != "weighted_average":
        # Stale weights would fail validation once the mode stops being weighted.
        row.year_weights = None

    components = await common.structure_components(session, row.id)
    intended = data.intended_total if data.intended_total is not None else row.intended_total
    next_inputs = data.components
    if next_inputs is not None:
        _check_totals(next_inputs, intended)
        components = await _apply_components(session, row, principal, next_inputs)
        touched = True
    elif intended is not None and _total(components) > intended:
        raise ValidationFailed(
            "The components add up to more than the intended total",
            message_key="assessment.error.component_sum",
            details={"total": decimal_out(_total(components)), "intended": decimal_out(intended)},
        )
    await _check_year_rule(session, year.id, row.year_mode, row.year_weights)

    scope_changed = key != row.scope_key
    row.scope_type = scope_type
    row.scope_key = key
    row.level_id = level_id
    row.stage_id = stage_id
    row.subject_id = subject_id
    row.row_version = (row.row_version or 1) + 1
    if touched or scope_changed:
        row.version = (row.version or 1) + 1

    recalculation_job_id: str | None = None
    changed_scores = 0
    conversion_changed = bool(CONVERSION_FIELDS.intersection(data.model_fields_set))
    if next_inputs is not None:
        conversion_changed = conversion_changed or _conversion_differs(
            before["components"],
            [common.component_state(component) for component in components],
        )
    if conversion_changed:
        assessments, scores = await _count_scope(session, row)
        if scores:
            job = await events.create_job(
                session,
                "assessment.recalculate",
                {"structure_id": str(row.id)},
                created_by=principal.actor_id,
            )
            recalculation_job_id = str(job.id)
            changed_scores = await _count_changes(session, row, components)

    after = {
        **structure_state(row),
        "components": [common.component_state(component) for component in components],
    }
    await record(
        session,
        action="assessment.structure.update",
        module=MODULE,
        entity_type="assessment_structure",
        entity_id=str(row.id),
        before=before,
        after=after,
        actor=principal,
        reason=data.reason,
        via=via,
    )
    await session.commit()

    if recalculation_job_id is not None and settings is not None and settings.app_env != "test":
        try:
            import asyncio

            from core.events.celery_app import assessment_recalculate_task

            await asyncio.to_thread(
                assessment_recalculate_task.delay,
                recalculation_job_id,
                str(row.id),
            )
        except Exception as exc:  # pragma: no cover - broker outages are operational
            import logging

            logging.getLogger("erp.jobs").warning(
                "assessment recalculation enqueue failed for %s: %s", row.id, exc
            )

    return StructureUpdateResult(
        structure=await _detail(session, row),
        recalculation_job_id=recalculation_job_id,
        changed_scores=changed_scores,
    )


async def delete_structure(
    session: AsyncSession,
    principal: Principal,
    structure_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await common.live_structure(session, structure_id)
    assessments, scores = await _count_scope(session, row)
    if scores:
        raise Conflict(
            "A structure that already has marks cannot be removed",
            message_key="assessment.error.structure_in_use",
            details={"assessments": assessments, "scores": scores},
        )
    await soft_delete(
        session,
        row,
        action="assessment.structure.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="assessment_structure",
    )
    await session.commit()
    return {"id": str(row.id), "deleted": True}


async def get_structure(
    session: AsyncSession,
    structure_id: uuid.UUID,
) -> StructureOut:
    return await _detail(session, await common.live_structure(session, structure_id))


async def list_structures(
    session: AsyncSession,
    query: StructureQuery,
) -> Page[StructureOut]:
    stmt = select(AssessmentStructure).where(AssessmentStructure.deleted_at.is_(None))
    if query.year_id is not None:
        stmt = stmt.where(AssessmentStructure.year_id == query.year_id)
    if query.scope_type is not None:
        stmt = stmt.where(AssessmentStructure.scope_type == query.scope_type)
    if query.level_id is not None:
        stmt = stmt.where(AssessmentStructure.level_id == query.level_id)
    if query.stage_id is not None:
        stmt = stmt.where(AssessmentStructure.stage_id == query.stage_id)
    if query.subject_id is not None:
        stmt = stmt.where(AssessmentStructure.subject_id == query.subject_id)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    page_params = PageParams(
        limit=query.limit,
        cursor=query.cursor,
        sort=query.sort,
        order=query.order,
    )
    rows, next_cursor = await paginate(
        session,
        stmt,
        page_params,
        sort_columns=SORT_COLUMNS,
        default_sort="created_at",
        id_column=AssessmentStructure.id,
    )
    years = {
        year.id: year
        for year in (
            await session.execute(
                select(AcademicYear).where(
                    AcademicYear.id.in_({row.year_id for row in rows}),
                    AcademicYear.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }
    items: list[StructureOut] = []
    for row in rows:
        components = await common.structure_components(session, row.id)
        items.append(_structure_out(row, years[row.year_id], components, await _labels(session, row)))
    return Page[StructureOut](items=items, next_cursor=next_cursor, total=total)


async def _count_scope(
    session: AsyncSession,
    structure: AssessmentStructure,
) -> tuple[int, int]:
    assessments = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Assessment)
                .where(
                    Assessment.structure_id == structure.id,
                    Assessment.deleted_at.is_(None),
                )
            )
        ).scalar_one()
    )
    scores = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Score)
                .join(Assessment, Assessment.id == Score.assessment_id)
                .where(
                    Assessment.structure_id == structure.id,
                    Assessment.deleted_at.is_(None),
                    Score.deleted_at.is_(None),
                )
            )
        ).scalar_one()
    )
    return assessments, scores


async def _scores_for_structure(
    session: AsyncSession,
    structure_id: uuid.UUID,
) -> list[tuple[Score, Assessment]]:
    rows = (
        await session.execute(
            select(Score, Assessment)
            .join(Assessment, Assessment.id == Score.assessment_id)
            .where(
                Assessment.structure_id == structure_id,
                Assessment.deleted_at.is_(None),
                Score.deleted_at.is_(None),
            )
        )
    ).all()
    return [(row[0], row[1]) for row in rows]


async def _count_changes(
    session: AsyncSession,
    structure: AssessmentStructure,
    components: list[AssessmentComponent],
) -> int:
    by_id = {component.id: component for component in components}
    changed = 0
    for score, assessment in await _scores_for_structure(session, structure.id):
        component = by_id.get(assessment.component_id)
        if component is None:
            continue
        after = common.converted_for(
            raw=score.raw_score,
            out_of=score.out_of,
            status=score.status,
            component=component,
            structure=structure,
        )
        if after != score.converted:
            changed += 1
    return changed


async def structure_impact(
    session: AsyncSession,
    structure_id: uuid.UUID,
    proposed: list[ComponentInput] | None = None,
) -> StructureImpact:
    row = await common.live_structure(session, structure_id)
    current = await common.structure_components(session, row.id)
    after_by_key = {component.key: component for component in current}
    if proposed is not None:
        after_by_key = {
            component.key: AssessmentComponent(
                structure_id=row.id,
                key=component.key,
                name=component.name,
                max_points=component.max_points,
                aggregation=component.aggregation,
                absent_counts_as_zero=component.absent_counts_as_zero,
                best_n=component.best_n,
                cap=component.cap,
            )
            for component in proposed
        }
    pairs = await _scores_for_structure(session, row.id)
    changed = 0
    students: set[uuid.UUID] = set()
    samples: list[ImpactSample] = []
    for score, assessment in sorted(pairs, key=lambda pair: (str(pair[0].student_id), str(pair[0].id))):
        students.add(score.student_id)
        component = next(
            (item for item in current if item.id == assessment.component_id),
            None,
        )
        if component is None:
            continue
        after_component = after_by_key.get(component.key)
        after = (
            common.converted_for(
                raw=score.raw_score,
                out_of=score.out_of,
                status=score.status,
                component=after_component,
                structure=row,
            )
            if after_component is not None
            else None
        )
        if after != score.converted:
            changed += 1
            if len(samples) < 5:
                samples.append(
                    ImpactSample(
                        score_id=str(score.id),
                        student_id=str(score.student_id),
                        raw=decimal_out(score.raw_score),
                        out_of=decimal_out(score.out_of) or "0",
                        before=decimal_out(score.converted),
                        after=decimal_out(after),
                    )
                )
    total_before = _total(current)
    total_after = sum((component.max_points for component in after_by_key.values()), Decimal(0))
    assessments = len({assessment.id for _, assessment in pairs})
    return StructureImpact(
        structure_id=str(row.id),
        assessments=assessments,
        scores=len(pairs),
        students=len(students),
        changed=changed,
        recalculation_required=changed > 0,
        total_before=decimal_out(total_before) or "0",
        total_after=decimal_out(total_after) or "0",
        samples=samples,
    )


async def recalculate_structure(
    session: AsyncSession,
    structure_id: uuid.UUID,
) -> RecalculationResult:
    """Recompute ``Score.converted`` from raw values; raw marks stay untouched."""
    row = await common.live_structure(session, structure_id)
    components = await common.structure_components(session, row.id)
    by_id = {component.id: component for component in components}
    pairs = await _scores_for_structure(session, row.id)
    changed = 0
    students: set[uuid.UUID] = set()
    for score, assessment in pairs:
        students.add(score.student_id)
        component = by_id.get(assessment.component_id)
        if component is None:
            continue
        converted = common.converted_for(
            raw=score.raw_score,
            out_of=score.out_of,
            status=score.status,
            component=component,
            structure=row,
        )
        if converted == score.converted:
            continue
        score.converted = converted
        changed += 1
    await record(
        session,
        action="assessment.structure.recalculate",
        module=MODULE,
        entity_type="assessment_structure",
        entity_id=str(row.id),
        after={
            "assessments": len({assessment.id for _, assessment in pairs}),
            "scores": len(pairs),
            "students": len(students),
            "changed": changed,
        },
        via="api",
    )
    await session.commit()
    return RecalculationResult(
        structure_id=str(row.id),
        assessments=len({assessment.id for _, assessment in pairs}),
        scores=len(pairs),
        changed=changed,
    )


SORT_COLUMNS_ASSESSMENT = {
    "created_at": Assessment.created_at,
    "assessment_date": Assessment.assessment_date,
    "title": Assessment.title,
}


async def _score_counts(session: AsyncSession, assessment_id: uuid.UUID) -> tuple[int, int]:
    raw_values = (
        (
            await session.execute(
                select(Score.raw_score).where(
                    Score.assessment_id == assessment_id,
                    Score.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    return len(raw_values), sum(1 for value in raw_values if value is not None)


async def _assessment_out(
    session: AsyncSession,
    row: Assessment,
    cache: dict[tuple[type, uuid.UUID], Any],
    *,
    counts: tuple[int, int] | None = None,
) -> AssessmentOut:
    async def get(model: type, ident: uuid.UUID | None) -> Any:
        if ident is None:
            return None
        key = (model, ident)
        if key not in cache:
            cache[key] = await session.get(model, ident)
        return cache[key]

    year = await get(AcademicYear, row.year_id)
    term = await get(Term, row.term_id)
    section = await get(Section, row.section_id)
    level = await get(GradeLevel, section.level_id) if section is not None else None
    subject = await get(Subject, row.subject_id)
    component = await get(AssessmentComponent, row.component_id)
    scores, entered = counts if counts is not None else await _score_counts(session, row.id)
    return AssessmentOut(
        id=str(row.id),
        year_id=str(row.year_id),
        year_code=year.code if year is not None else "",
        term_id=str(row.term_id),
        term_name=term.name if term is not None else "",
        section_id=str(row.section_id),
        section_code=section.code if section is not None else "",
        level_id=str(section.level_id) if section is not None else "",
        level_name=level.name if level is not None else "",
        subject_id=str(row.subject_id),
        subject_name=subject.name if subject is not None else "",
        structure_id=str(row.structure_id) if row.structure_id else None,
        component_id=str(row.component_id),
        component_key=component.key if component is not None else "",
        component_name=component.name if component is not None else "",
        component_max_points=decimal_out(component.max_points) if component is not None else "0",
        title=row.title,
        title_am=row.title_am,
        assessment_date=row.assessment_date,
        out_of=decimal_out(row.out_of) or "0",
        weight=decimal_out(row.weight),
        allow_bonus=row.allow_bonus,
        status=row.status,
        notes=row.notes,
        scores=scores,
        entered=entered,
        row_version=row.row_version,
    )


async def _detail_assessment(session: AsyncSession, row: Assessment) -> AssessmentOut:
    return await _assessment_out(session, row, {})


async def _component_for(
    session: AsyncSession,
    structure: AssessmentStructure,
    key: str,
) -> AssessmentComponent:
    components = await common.structure_components(session, structure.id)
    match = next((component for component in components if component.key == key), None)
    if match is None:
        raise NotFound(
            "The component does not exist",
            message_key="assessment.error.component_not_found",
            details={"key": key},
        )
    if not match.is_active:
        raise ValidationFailed(
            "That component is not active in the mark structure",
            message_key="assessment.error.component_inactive",
            details={"key": key},
        )
    return match


def _check_weight(component: AssessmentComponent, weight: Decimal | None) -> None:
    if component.aggregation == "weighted_average":
        if weight is None or weight <= 0:
            raise ValidationFailed(
                "A weighted component needs a weight on every assessment",
                message_key="assessment.error.weight_required",
                details={"component": component.key},
            )
        return
    if weight is not None:
        raise ValidationFailed(
            "A weight only applies when the component uses weighted averaging",
            message_key="assessment.error.weight_unused",
            details={"component": component.key},
        )


def _validate_mark(
    assessment: Assessment,
    component: AssessmentComponent,
    item: ScoreInput,
) -> None:
    common.validate_mark(
        assessment=assessment,
        component=component,
        raw=item.raw_score,
        status=item.status,
        student_id=item.student_id,
    )


async def _assessment_structure(session: AsyncSession, row: Assessment) -> AssessmentStructure:
    if row.structure_id is None:
        raise ValidationFailed(
            "No mark structure applies to this year, level and subject",
            message_key="assessment.error.no_structure",
            details={"assessment_id": str(row.id)},
        )
    return await common.live_structure(session, row.structure_id)


async def create_assessment(
    session: AsyncSession,
    principal: Principal,
    data: AssessmentCreate,
    *,
    via: str = "api",
) -> AssessmentOut:
    year = await common.live_year(session, data.year_id)
    term = await common.live_term(session, data.term_id)
    if term.year_id != year.id:
        raise ValidationFailed(
            "The term does not belong to that academic year",
            message_key="assessment.error.term_year",
            details={"term_id": str(term.id), "year_id": str(year.id)},
        )
    section = await common.live_section(session, data.section_id)
    if section.year_id != year.id:
        raise ValidationFailed(
            "The section does not belong to that academic year",
            message_key="assessment.error.section_year",
            details={"section_id": str(section.id), "year_id": str(year.id)},
        )
    subject = await common.live_subject(session, data.subject_id)
    await scoping.assert_visible(
        session,
        principal,
        "assessment.enter_marks",
        section_id=section.id,
        subject_id=subject.id,
    )
    structure = await common.structure_for(
        session,
        year_id=year.id,
        level_id=section.level_id,
        subject_id=subject.id,
        structure_id=data.structure_id,
    )
    component = await _component_for(session, structure, data.component_key)
    _check_weight(component, data.weight)
    actor_id = uuid.UUID(principal.user_id) if principal.actor_type == "user" else None
    row = Assessment(
        year_id=year.id,
        term_id=term.id,
        section_id=section.id,
        subject_id=subject.id,
        structure_id=structure.id,
        component_id=component.id,
        title=data.title,
        title_am=data.title_am,
        assessment_date=data.assessment_date,
        out_of=data.out_of,
        weight=data.weight,
        allow_bonus=data.allow_bonus,
        status="active",
        notes=data.notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await record(
        session,
        action="assessment.assessment.create",
        module=MODULE,
        entity_type="assessment",
        entity_id=str(row.id),
        after=common.assessment_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await _detail_assessment(session, row)


async def update_assessment(
    session: AsyncSession,
    principal: Principal,
    assessment_id: uuid.UUID,
    data: AssessmentUpdate,
    *,
    via: str = "api",
) -> AssessmentOut:
    row = await common.live_assessment(session, assessment_id)
    before = common.assessment_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    await _assessment_structure(session, row)
    component = await common.live_component(session, row.component_id)
    await scoping.assert_visible(
        session,
        principal,
        "assessment.enter_marks",
        section_id=row.section_id,
        subject_id=row.subject_id,
    )
    if row.status == "archived" and data.status != "active":
        raise Conflict(
            "This assessment is archived and cannot change",
            message_key="assessment.error.assessment_archived",
            details={"assessment_id": str(row.id)},
        )

    changes: dict[str, Any] = {}
    if data.out_of is not None and data.out_of != row.out_of:
        scores, _entered = await _score_counts(session, row.id)
        if scores:
            raise Conflict(
                "The maximum cannot change after marks are entered",
                message_key="assessment.error.out_of_locked",
                details={"assessment_id": str(row.id), "scores": scores},
            )
        changes["out_of"] = data.out_of
    for field in ("title", "title_am", "assessment_date", "allow_bonus", "status", "notes"):
        value = getattr(data, field)
        if value is not None and getattr(row, field) != value:
            changes[field] = value
    if "weight" in data.model_fields_set:
        _check_weight(component, data.weight)
        if row.weight != data.weight:
            changes["weight"] = data.weight

    if changes.get("allow_bonus") is False and row.allow_bonus:
        over = (
            await session.execute(
                select(func.count())
                .select_from(Score)
                .where(
                    Score.assessment_id == row.id,
                    Score.deleted_at.is_(None),
                    Score.raw_score.is_not(None),
                    Score.raw_score > row.out_of,
                )
            )
        ).scalar_one()
        if int(over):
            raise ValidationFailed(
                "A score cannot exceed the assessment maximum unless bonus marks are allowed",
                message_key="assessment.error.raw_over_out_of",
                details={"assessment_id": str(row.id), "scores": int(over)},
            )

    if not changes:
        return await _detail_assessment(session, row)

    for field, value in changes.items():
        setattr(row, field, value)
    row.row_version = (row.row_version or 0) + 1
    row.updated_by = uuid.UUID(principal.user_id) if principal.actor_type == "user" else None
    await record(
        session,
        action="assessment.assessment.update",
        module=MODULE,
        entity_type="assessment",
        entity_id=str(row.id),
        before=before,
        after=common.assessment_state(row),
        actor=principal,
        reason=data.reason,
        via=via,
    )
    await session.commit()
    return await _detail_assessment(session, row)


async def delete_assessment(
    session: AsyncSession,
    principal: Principal,
    assessment_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await common.live_assessment(session, assessment_id)
    await scoping.assert_visible(
        session,
        principal,
        "assessment.enter_marks",
        section_id=row.section_id,
        subject_id=row.subject_id,
    )
    scores, _entered = await _score_counts(session, row.id)
    if scores:
        raise Conflict(
            "An assessment with marks cannot be removed",
            message_key="assessment.error.assessment_in_use",
            details={"assessment_id": str(row.id), "scores": scores},
        )
    await soft_delete(
        session,
        row,
        action="assessment.assessment.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="assessment",
    )
    await session.commit()
    return {"id": str(row.id), "deleted": True}


async def get_assessment(
    session: AsyncSession,
    principal: Principal,
    assessment_id: uuid.UUID,
) -> AssessmentOut:
    row = await common.live_assessment(session, assessment_id)
    await scoping.assert_visible(
        session,
        principal,
        "assessment.view",
        section_id=row.section_id,
        subject_id=row.subject_id,
    )
    return await _detail_assessment(session, row)


async def list_assessments(
    session: AsyncSession,
    principal: Principal,
    query: AssessmentQuery,
) -> Page[AssessmentOut]:
    stmt = select(Assessment).where(Assessment.deleted_at.is_(None))
    access = await scoping.visible_access(session, principal, "assessment.view")
    narrowed = scoping.condition(access)
    if narrowed is not None:
        stmt = stmt.where(narrowed)
    if query.year_id is not None:
        stmt = stmt.where(Assessment.year_id == query.year_id)
    if query.term_id is not None:
        stmt = stmt.where(Assessment.term_id == query.term_id)
    if query.section_id is not None:
        stmt = stmt.where(Assessment.section_id == query.section_id)
    if query.subject_id is not None:
        stmt = stmt.where(Assessment.subject_id == query.subject_id)
    if query.component_id is not None:
        stmt = stmt.where(Assessment.component_id == query.component_id)
    if query.status is not None:
        stmt = stmt.where(Assessment.status == query.status)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows, next_cursor = await paginate(
        session,
        stmt,
        PageParams(
            limit=query.limit,
            cursor=query.cursor,
            sort=query.sort,
            order=query.order,
        ),
        sort_columns=SORT_COLUMNS_ASSESSMENT,
        default_sort="created_at",
        id_column=Assessment.id,
    )
    cache: dict[tuple[type, uuid.UUID], Any] = {}
    items = [await _assessment_out(session, row, cache) for row in rows]
    return Page[AssessmentOut](items=items, next_cursor=next_cursor, total=total)


def _score_out(
    score: Score | None,
    profile: StudentProfile,
    person: Person,
    *,
    roll_number: str | None,
    out_of: Decimal,
    enrolled: bool = True,
) -> ScoreOut:
    return ScoreOut(
        score_id=str(score.id) if score is not None else None,
        student_id=str(profile.id),
        student_number=profile.student_number,
        student_name=common.person_name(person, "en"),
        student_name_am=common.person_name(person, "am") or None,
        roll_number=roll_number,
        enrolled=enrolled,
        raw_score=decimal_out(score.raw_score) if score is not None else None,
        out_of=decimal_out(score.out_of) if score is not None else decimal_out(out_of) or "0",
        status=score.status if score is not None else "present",
        converted=decimal_out(score.converted) if score is not None else None,
        note=score.note if score is not None else None,
        row_version=score.row_version if score is not None else None,
        entered_at=score.entered_at if score is not None else None,
    )


def _stats(
    items: list[ScoreOut],
    *,
    assessment: Assessment,
    component: AssessmentComponent,
    structure: AssessmentStructure | None,
) -> ScoreStats:
    counts = {"present": 0, "absent": 0, "excused": 0, "exempt": 0, "not_taken": 0}
    values: list[Decimal] = []
    entered = 0
    for item in items:
        if item.score_id is None:
            continue
        entered += 1
        counts[item.status] = counts.get(item.status, 0) + 1
        if item.converted is not None:
            values.append(Decimal(item.converted))
    precision = structure.precision if structure is not None else 2
    rounding = common.rounding_mode(structure.rounding) if structure is not None else None
    average_converted = None
    average_percent = None
    highest = None
    lowest = None
    if values:
        mean = sum(values, Decimal(0)) / len(values)
        if rounding is None:
            average_converted = round_mark(mean, precision=precision)
        else:
            average_converted = round_mark(mean, precision=precision, rounding=rounding)
        average_percent = round_mark(mean * 100 / component.max_points, precision=2)
        highest = max(values)
        lowest = min(values)
    return ScoreStats(
        total=len(items),
        entered=entered,
        missing=len(items) - entered,
        present=counts["present"],
        absent=counts["absent"],
        excused=counts["excused"],
        exempt=counts["exempt"],
        not_taken=counts["not_taken"],
        out_of=decimal_out(assessment.out_of) or "0",
        component_max_points=decimal_out(component.max_points) or "0",
        average_converted=decimal_out(average_converted),
        average_percent=decimal_out(average_percent),
        highest_converted=decimal_out(highest),
        lowest_converted=decimal_out(lowest),
    )


async def _sheet(session: AsyncSession, row: Assessment) -> ScoreSheet:
    structure = await _assessment_structure(session, row)
    component = await common.live_component(session, row.component_id)
    roster = await common.enrolled_roster(session, row.year_id, row.section_id)
    scores = {
        score.student_id: score
        for score in (
            await session.execute(
                select(Score).where(
                    Score.assessment_id == row.id,
                    Score.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }
    items: list[ScoreOut] = []
    for profile, person, enrollment in roster:
        items.append(
            _score_out(
                scores.pop(profile.id, None),
                profile,
                person,
                roll_number=enrollment.roll_number,
                out_of=row.out_of,
            )
        )
    # A student who left the section still has marks on this assessment; show
    # them at the end rather than hiding an entered value.
    for student_id, score in sorted(scores.items(), key=lambda pair: str(pair[0])):
        profile = await session.get(StudentProfile, student_id)
        if profile is None or profile.deleted_at is not None:
            continue
        person = await session.get(Person, profile.person_id)
        if person is None:
            continue
        items.append(
            _score_out(
                score,
                profile,
                person,
                roll_number=None,
                out_of=row.out_of,
                enrolled=False,
            )
        )
    return ScoreSheet(
        assessment_id=str(row.id),
        title=row.title,
        component_key=component.key,
        component_max_points=decimal_out(component.max_points) or "0",
        out_of=decimal_out(row.out_of) or "0",
        allow_bonus=row.allow_bonus,
        editable=row.status == "active",
        items=items,
        stats=_stats(items, assessment=row, component=component, structure=structure),
    )


async def score_sheet(
    session: AsyncSession,
    principal: Principal,
    assessment_id: uuid.UUID,
) -> ScoreSheet:
    row = await common.live_assessment(session, assessment_id)
    await scoping.assert_visible(
        session,
        principal,
        "assessment.view",
        section_id=row.section_id,
        subject_id=row.subject_id,
    )
    return await _sheet(session, row)


async def upsert_scores(
    session: AsyncSession,
    principal: Principal,
    assessment_id: uuid.UUID,
    data: ScoreBulkInput,
    *,
    via: str = "api",
) -> ScoreBulkResult:
    """Create or update one score per student, idempotently.

    The natural key ``(assessment, student)`` makes a repeated request a no-op:
    unchanged rows are counted, not rewritten, so retrying a flaky upload cannot
    duplicate a mark or a revision.
    """
    row = await common.live_assessment(session, assessment_id)
    await scoping.assert_visible(
        session,
        principal,
        "assessment.enter_marks",
        section_id=row.section_id,
        subject_id=row.subject_id,
    )
    if row.status != "active":
        raise Conflict(
            "This assessment is archived and cannot change",
            message_key="assessment.error.assessment_archived",
            details={"assessment_id": str(row.id)},
        )
    await workflow.assert_entry_open(session, row)
    structure = await _assessment_structure(session, row)
    component = await common.live_component(session, row.component_id)
    roster = {
        profile.id
        for profile, _person, _enrollment in await common.enrolled_roster(
            session, row.year_id, row.section_id
        )
    }
    existing = {
        score.student_id: score
        for score in (
            await session.execute(
                select(Score).where(
                    Score.assessment_id == row.id,
                    Score.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }
    actor_id = uuid.UUID(principal.user_id) if principal.actor_type == "user" else None
    seen: set[uuid.UUID] = set()
    created = updated = unchanged = 0
    for item in data.items:
        if item.student_id in seen:
            raise ValidationFailed(
                "That student appears twice in this request",
                message_key="assessment.error.duplicate_score_entry",
                details={"student_id": str(item.student_id)},
            )
        seen.add(item.student_id)
        current = existing.get(item.student_id)
        if item.student_id not in roster and current is None:
            raise ValidationFailed(
                "The student is not enrolled in this section",
                message_key="assessment.error.student_not_enrolled",
                details={"student_id": str(item.student_id)},
            )
        if current is not None and item.row_version is not None:
            ensure_row_version(
                current,
                item.row_version,
                current_state=common.score_state(current),
            )
        _validate_mark(row, component, item)
        converted = common.converted_for(
            raw=item.raw_score,
            out_of=row.out_of,
            status=item.status,
            component=component,
            structure=structure,
        )
        if current is None:
            score = Score(
                assessment_id=row.id,
                student_id=item.student_id,
                raw_score=item.raw_score,
                out_of=row.out_of,
                status=item.status,
                converted=converted,
                note=item.note,
                entered_at=common.utcnow(),
                entered_by=actor_id,
                created_by=actor_id,
                updated_by=actor_id,
            )
            session.add(score)
            await session.flush()
            session.add(
                ScoreRevision(
                    score_id=score.id,
                    assessment_id=row.id,
                    student_id=score.student_id,
                    old_raw=None,
                    new_raw=score.raw_score,
                    old_status=None,
                    new_status=score.status,
                    old_converted=None,
                    new_converted=score.converted,
                    source="entry",
                    reason=data.reason,
                    changed_by=actor_id,
                    created_by=actor_id,
                    updated_by=actor_id,
                )
            )
            await record(
                session,
                action="assessment.score.create",
                module=MODULE,
                entity_type="score",
                entity_id=str(score.id),
                after=common.score_state(score),
                actor=principal,
                reason=data.reason,
                via=via,
            )
            existing[score.student_id] = score
            created += 1
            continue

        same = (
            current.raw_score == item.raw_score
            and current.status == item.status
            and current.note == item.note
            and current.out_of == row.out_of
            and current.converted == converted
        )
        if same:
            unchanged += 1
            continue
        before = common.score_state(current)
        current.raw_score = item.raw_score
        current.out_of = row.out_of
        current.status = item.status
        current.converted = converted
        current.note = item.note
        current.entered_at = common.utcnow()
        current.entered_by = actor_id
        current.updated_by = actor_id
        current.row_version = (current.row_version or 0) + 1
        session.add(
            ScoreRevision(
                score_id=current.id,
                assessment_id=row.id,
                student_id=current.student_id,
                old_raw=Decimal(before["raw_score"]) if before["raw_score"] is not None else None,
                new_raw=current.raw_score,
                old_status=before["status"],
                new_status=current.status,
                old_converted=Decimal(before["converted"]) if before["converted"] is not None else None,
                new_converted=current.converted,
                source="entry",
                reason=data.reason,
                changed_by=actor_id,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        await record(
            session,
            action="assessment.score.update",
            module=MODULE,
            entity_type="score",
            entity_id=str(current.id),
            before=before,
            after=common.score_state(current),
            actor=principal,
            reason=data.reason,
            via=via,
        )
        updated += 1

    await session.commit()
    return ScoreBulkResult(
        sheet=await _sheet(session, row),
        created=created,
        updated=updated,
        unchanged=unchanged,
    )


async def preview_scores(
    session: AsyncSession,
    principal: Principal,
    assessment_id: uuid.UUID,
    data: ScoreBulkInput,
) -> dict[str, Any]:
    """Describe the marks a bulk entry would create, update or leave alone.

    The same live assessment, scope, window, roster and conversion rules as
    :func:`upsert_scores` run here, but nothing is written and no revision or
    audit row is produced. The AI layer can therefore show a teacher exactly
    what will change before it asks for confirmation.
    """
    row = await common.live_assessment(session, assessment_id)
    await scoping.assert_visible(
        session,
        principal,
        "assessment.enter_marks",
        section_id=row.section_id,
        subject_id=row.subject_id,
    )
    if row.status != "active":
        raise Conflict(
            "This assessment is archived and cannot change",
            message_key="assessment.error.assessment_archived",
            details={"assessment_id": str(row.id)},
        )
    await workflow.assert_entry_open(session, row)
    structure = await _assessment_structure(session, row)
    component = await common.live_component(session, row.component_id)
    roster = {
        profile.id: (profile, person)
        for profile, person, _enrollment in await common.enrolled_roster(session, row.year_id, row.section_id)
    }
    existing = {
        score.student_id: score
        for score in (
            await session.execute(
                select(Score).where(
                    Score.assessment_id == row.id,
                    Score.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }
    extra_ids = {item.student_id for item in data.items} - set(roster)
    if extra_ids:
        for profile, person in (
            await session.execute(
                select(StudentProfile, Person)
                .join(Person, Person.id == StudentProfile.person_id)
                .where(StudentProfile.id.in_(extra_ids))
            )
        ).all():
            roster[profile.id] = (profile, person)

    seen: set[uuid.UUID] = set()
    counts = {"create": 0, "update": 0, "unchanged": 0}
    rows: list[dict[str, Any]] = []
    for item in data.items:
        if item.student_id in seen:
            raise ValidationFailed(
                "That student appears twice in this request",
                message_key="assessment.error.duplicate_score_entry",
                details={"student_id": str(item.student_id)},
            )
        seen.add(item.student_id)
        current = existing.get(item.student_id)
        profile_person = roster.get(item.student_id)
        if profile_person is None and current is None:
            raise ValidationFailed(
                "The student is not enrolled in this section",
                message_key="assessment.error.student_not_enrolled",
                details={"student_id": str(item.student_id)},
            )
        if current is not None and item.row_version is not None:
            ensure_row_version(
                current,
                item.row_version,
                current_state=common.score_state(current),
            )
        _validate_mark(row, component, item)
        converted = common.converted_for(
            raw=item.raw_score,
            out_of=row.out_of,
            status=item.status,
            component=component,
            structure=structure,
        )
        if current is None:
            change = "create"
        elif (
            current.raw_score == item.raw_score
            and current.status == item.status
            and current.note == item.note
            and current.out_of == row.out_of
            and current.converted == converted
        ):
            change = "unchanged"
        else:
            change = "update"
        counts[change] += 1
        profile = profile_person[0] if profile_person else None
        person = profile_person[1] if profile_person else None
        rows.append(
            {
                "student_id": str(item.student_id),
                "student_number": profile.student_number if profile else None,
                "student_name": (common.person_name(person, principal.locale) if person else None),
                "raw_score": decimal_out(item.raw_score),
                "status": item.status,
                "converted": decimal_out(converted),
                "note": item.note,
                "change": change,
            }
        )

    return {
        "assessment_id": str(row.id),
        "title": row.title,
        "section_id": str(row.section_id),
        "subject_id": str(row.subject_id),
        "out_of": decimal_out(row.out_of),
        "entry_open": True,
        "items": rows,
        "created": counts["create"],
        "updated": counts["update"],
        "unchanged": counts["unchanged"],
    }


__all__ = [
    "create_assessment",
    "create_structure",
    "delete_assessment",
    "delete_structure",
    "get_assessment",
    "get_structure",
    "list_assessments",
    "list_structures",
    "preview_scores",
    "recalculate_structure",
    "score_sheet",
    "structure_impact",
    "update_assessment",
    "update_structure",
    "upsert_scores",
]
