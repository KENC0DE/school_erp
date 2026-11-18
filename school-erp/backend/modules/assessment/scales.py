"""Grade scale CRUD, bands, context assignments and the test tool (P4-11).

A scale is configuration: editing a band changes labels, never a raw or
converted mark. Every band change bumps the scale version, and published results
keep the version that produced their label so a later edit cannot pass itself
off as history.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import mark_deleted, soft_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import GradeLevel, Stage, Subject
from modules.assessment import common, grading
from modules.assessment.common import MODULE, decimal_out
from modules.assessment.models import (
    Assessment,
    GradeBand,
    GradeScale,
    ScaleAssignment,
)
from modules.assessment.schemas import (
    BandOut,
    GradeScaleCreate,
    GradeScaleList,
    GradeScaleOut,
    GradeScaleUpdate,
    ScaleAssignmentInput,
    ScaleAssignmentList,
    ScaleAssignmentOut,
    ScaleTestResult,
)

CONVERSION_FIELDS = {"type", "lower_bound", "upper_bound", "precision", "rounding"}
CONTEXT_ORDER = {"default": 0, "stage": 1, "level": 2, "subject": 3, "assessment": 4}


def _band_out(row: GradeBand) -> BandOut:
    return BandOut(
        id=str(row.id),
        min_value=decimal_out(row.min_value) or "0",
        max_value=decimal_out(row.max_value) or "0",
        label=row.label,
        remark=row.remark,
        gpa_points=decimal_out(row.gpa_points),
        is_pass=row.is_pass,
        color=row.color,
        sort_order=row.sort_order,
        row_version=row.row_version,
    )


def _band_state(row: GradeBand) -> dict[str, Any]:
    return {
        "band_id": str(row.id),
        "min_value": decimal_out(row.min_value),
        "max_value": decimal_out(row.max_value),
        "label": row.label,
        "remark": row.remark,
        "gpa_points": decimal_out(row.gpa_points),
        "is_pass": row.is_pass,
        "color": row.color,
        "sort_order": row.sort_order,
    }


def _scale_state(row: GradeScale, bands: list[GradeBand]) -> dict[str, Any]:
    return {
        "name": row.name,
        "name_am": row.name_am,
        "type": row.type,
        "description": row.description,
        "is_default": row.is_default,
        "lower_bound": decimal_out(row.lower_bound),
        "upper_bound": decimal_out(row.upper_bound),
        "precision": row.precision,
        "rounding": row.rounding,
        "version": row.version,
        "effective_from": row.effective_from.isoformat() if row.effective_from else None,
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "is_active": row.is_active,
        "notes": row.notes,
        "bands": [_band_state(band) for band in bands],
    }


def _scale_out(row: GradeScale, bands: list[GradeBand], assignment_count: int) -> GradeScaleOut:
    return GradeScaleOut(
        id=str(row.id),
        name=row.name,
        name_am=row.name_am,
        type=row.type,
        description=row.description,
        is_default=row.is_default,
        lower_bound=decimal_out(row.lower_bound) or "0",
        upper_bound=decimal_out(row.upper_bound) or "0",
        precision=row.precision,
        rounding=row.rounding,
        version=row.version,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        is_active=row.is_active,
        notes=row.notes,
        row_version=row.row_version,
        bands=[_band_out(band) for band in bands],
        assignment_count=assignment_count,
    )


async def _live_bands(session: AsyncSession, scale_id: uuid.UUID) -> list[GradeBand]:
    rows = (
        (
            await session.execute(
                select(GradeBand)
                .where(GradeBand.scale_id == scale_id, GradeBand.deleted_at.is_(None))
                .order_by(GradeBand.sort_order, GradeBand.min_value)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def live_scale(session: AsyncSession, scale_id: uuid.UUID) -> GradeScale:
    row = (
        await session.execute(
            select(GradeScale).where(GradeScale.id == scale_id, GradeScale.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The grade scale does not exist",
            message_key="assessment.error.scale_not_found",
        )
    return row


def _engine_scale(
    *,
    name: str,
    scale_type: str,
    lower_bound: Decimal,
    upper_bound: Decimal,
    precision: int,
    rounding: str,
    bands: Sequence[Any],
    version: int = 1,
    effective_from: date | None = None,
    effective_to: date | None = None,
) -> grading.GradeScale:
    try:
        return grading.GradeScale(
            name=name,
            type=grading.ScaleType(scale_type),
            bands=[
                grading.Band(
                    min_value=band.min_value,
                    max_value=band.max_value,
                    label=band.label,
                    remark=band.remark,
                    gpa_points=band.gpa_points,
                    is_pass=band.is_pass,
                    color=band.color,
                )
                for band in bands
            ],
            version=version,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            rounding=common.rounding_mode(rounding),
            precision=precision,
            effective_from=effective_from,
            effective_to=effective_to,
        )
    except (TypeError, ValueError) as exc:
        raise ValidationFailed(
            "The grade bands do not cover the scale without gaps or overlaps",
            message_key="assessment.error.grade_bands",
            details={"reason": str(exc)},
        ) from exc


def _validate_bands(
    *,
    name: str,
    scale_type: str,
    lower_bound: Decimal,
    upper_bound: Decimal,
    precision: int,
    rounding: str,
    bands: Sequence[Any],
    version: int = 1,
    effective_from: date | None = None,
    effective_to: date | None = None,
) -> None:
    scale = _engine_scale(
        name=name,
        scale_type=scale_type,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        precision=precision,
        rounding=rounding,
        bands=bands,
        version=version,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    try:
        grading.validate_scale(scale)
    except ValueError as exc:
        raise ValidationFailed(
            "The grade bands do not cover the scale without gaps or overlaps",
            message_key="assessment.error.grade_bands",
            details={"reason": str(exc)},
        ) from exc


async def _assert_unique_name(
    session: AsyncSession, name: str, *, exclude_id: uuid.UUID | None = None
) -> None:
    stmt = select(GradeScale.id).where(GradeScale.name == name, GradeScale.deleted_at.is_(None))
    if exclude_id is not None:
        stmt = stmt.where(GradeScale.id != exclude_id)
    if (await session.execute(stmt)).first() is not None:
        raise Conflict(
            "That grade scale name is already used",
            message_key="assessment.error.scale_name",
            details={"name": name},
        )


async def _clear_default(
    session: AsyncSession,
    principal: Principal,
    *,
    exclude_id: uuid.UUID | None = None,
    via: str,
) -> None:
    stmt = select(GradeScale).where(GradeScale.is_default.is_(True), GradeScale.deleted_at.is_(None))
    if exclude_id is not None:
        stmt = stmt.where(GradeScale.id != exclude_id)
    for row in (await session.execute(stmt)).scalars().all():
        row.is_default = False
        row.row_version = (row.row_version or 1) + 1
        await record(
            session,
            action="assessment.scale.update",
            module=MODULE,
            entity_type="grade_scale",
            entity_id=str(row.id),
            before={"is_default": True},
            after={"is_default": False, "reason": "another scale became the default"},
            actor=principal,
            via=via,
        )


async def _assignment_counts(session: AsyncSession) -> dict[uuid.UUID, int]:
    rows = (
        await session.execute(
            select(ScaleAssignment.scale_id, func.count())
            .where(ScaleAssignment.deleted_at.is_(None))
            .group_by(ScaleAssignment.scale_id)
        )
    ).all()
    return {scale_id: int(count) for scale_id, count in rows}


async def list_scales(session: AsyncSession, *, include_inactive: bool = False) -> GradeScaleList:
    stmt = select(GradeScale).where(GradeScale.deleted_at.is_(None))
    if not include_inactive:
        stmt = stmt.where(GradeScale.is_active.is_(True))
    rows = (
        (await session.execute(stmt.order_by(GradeScale.is_default.desc(), GradeScale.name.asc())))
        .scalars()
        .all()
    )
    counts = await _assignment_counts(session)
    items: list[GradeScaleOut] = []
    for row in rows:
        items.append(_scale_out(row, await _live_bands(session, row.id), counts.get(row.id, 0)))
    return GradeScaleList(items=items, total=len(items))


async def get_scale(session: AsyncSession, scale_id: uuid.UUID) -> GradeScaleOut:
    row = await live_scale(session, scale_id)
    counts = await _assignment_counts(session)
    return _scale_out(row, await _live_bands(session, row.id), counts.get(row.id, 0))


async def create_scale(
    session: AsyncSession,
    principal: Principal,
    data: GradeScaleCreate,
    *,
    via: str = "api",
) -> GradeScaleOut:
    await _assert_unique_name(session, data.name)
    _validate_bands(
        name=data.name,
        scale_type=data.type,
        lower_bound=data.lower_bound,
        upper_bound=data.upper_bound,
        precision=data.precision,
        rounding=data.rounding,
        bands=data.bands,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
    )
    if data.is_default:
        await _clear_default(session, principal, via=via)
    row = GradeScale(
        name=data.name,
        name_am=data.name_am,
        type=data.type,
        description=data.description,
        is_default=data.is_default,
        lower_bound=data.lower_bound,
        upper_bound=data.upper_bound,
        precision=data.precision,
        rounding=data.rounding,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        is_active=data.is_active,
        notes=data.notes,
    )
    session.add(row)
    await session.flush()
    bands = [
        GradeBand(
            scale_id=row.id,
            min_value=band.min_value,
            max_value=band.max_value,
            label=band.label,
            remark=band.remark,
            gpa_points=band.gpa_points,
            is_pass=band.is_pass,
            color=band.color,
            sort_order=band.sort_order if band.sort_order is not None else index * 10,
        )
        for index, band in enumerate(data.bands)
    ]
    session.add_all(bands)
    await session.flush()
    await record(
        session,
        action="assessment.scale.create",
        module=MODULE,
        entity_type="grade_scale",
        entity_id=str(row.id),
        after=_scale_state(row, list(bands)),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await get_scale(session, row.id)


async def update_scale(
    session: AsyncSession,
    principal: Principal,
    scale_id: uuid.UUID,
    data: GradeScaleUpdate,
    *,
    via: str = "api",
) -> GradeScaleOut:
    row = await live_scale(session, scale_id)
    current_bands = await _live_bands(session, row.id)
    before = _scale_state(row, current_bands)
    ensure_row_version(row, data.row_version, current_state=before)

    values = data.model_dump(exclude={"row_version", "reason", "bands"})
    touched: set[str] = set()
    for field, value in values.items():
        if value is not None and getattr(row, field) != value:
            setattr(row, field, value)
            touched.add(field)
    if data.name is not None and data.name != before["name"]:
        await _assert_unique_name(session, data.name, exclude_id=row.id)
    if data.effective_from and data.effective_to and data.effective_from > data.effective_to:
        raise ValidationFailed(
            "effective_from cannot be after effective_to",
            message_key="assessment.error.scale_dates",
        )

    bands_changed = data.bands is not None
    if bands_changed:
        for band in current_bands:
            mark_deleted(band, actor=principal)
        await session.flush()
        current_bands = [
            GradeBand(
                scale_id=row.id,
                min_value=band.min_value,
                max_value=band.max_value,
                label=band.label,
                remark=band.remark,
                gpa_points=band.gpa_points,
                is_pass=band.is_pass,
                color=band.color,
                sort_order=band.sort_order if band.sort_order is not None else index * 10,
            )
            for index, band in enumerate(data.bands or [])
        ]
        session.add_all(current_bands)
        await session.flush()

    if bands_changed or touched.intersection(CONVERSION_FIELDS):
        _validate_bands(
            name=row.name,
            scale_type=row.type,
            lower_bound=row.lower_bound,
            upper_bound=row.upper_bound,
            precision=row.precision,
            rounding=row.rounding,
            bands=current_bands,
            version=row.version,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
        )
        row.version = (row.version or 1) + 1

    if row.is_default:
        await _clear_default(session, principal, exclude_id=row.id, via=via)
    row.row_version = (row.row_version or 1) + 1
    await record(
        session,
        action="assessment.scale.update",
        module=MODULE,
        entity_type="grade_scale",
        entity_id=str(row.id),
        before=before,
        after=_scale_state(row, current_bands),
        actor=principal,
        reason=data.reason,
        via=via,
    )
    await session.commit()
    return await get_scale(session, row.id)


async def delete_scale(
    session: AsyncSession,
    principal: Principal,
    scale_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await live_scale(session, scale_id)
    if row.is_default:
        raise Conflict(
            "Choose another default scale before removing this one",
            message_key="assessment.error.scale_default",
            details={"scale_id": str(row.id)},
        )
    assigned = int(
        (
            await session.execute(
                select(func.count())
                .select_from(ScaleAssignment)
                .where(
                    ScaleAssignment.scale_id == row.id,
                    ScaleAssignment.deleted_at.is_(None),
                )
            )
        ).scalar_one()
    )
    if assigned:
        raise Conflict(
            "A scale that is assigned to a context cannot be removed",
            message_key="assessment.error.scale_in_use",
            details={"scale_id": str(row.id), "assignments": assigned},
        )
    for band in await _live_bands(session, row.id):
        mark_deleted(band, actor=principal)
    await soft_delete(
        session,
        row,
        action="assessment.scale.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="grade_scale",
    )
    await session.commit()
    return {"id": str(row.id), "deleted": True}


async def test_scale(session: AsyncSession, scale_id: uuid.UUID, value: Decimal) -> ScaleTestResult:
    row = await live_scale(session, scale_id)
    bands = await _live_bands(session, row.id)
    scale = _engine_scale(
        name=row.name,
        scale_type=row.type,
        lower_bound=row.lower_bound,
        upper_bound=row.upper_bound,
        precision=row.precision,
        rounding=row.rounding,
        bands=list(bands),
        version=row.version,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
    )
    try:
        result = grading.grade_for(scale, value)
    except ValueError as exc:
        raise ValidationFailed(
            "That mark is outside the grade scale range",
            message_key="assessment.error.value_out_of_range",
            details={"value": decimal_out(value), "reason": str(exc)},
        ) from exc
    return ScaleTestResult(
        value=decimal_out(value) or "0",
        label=result.label,
        remark=result.remark,
        gpa_points=decimal_out(result.gpa_points),
        is_pass=result.is_pass,
        color=result.color,
        band_min=decimal_out(result.band.min_value) or "0",
        band_max=decimal_out(result.band.max_value) or "0",
        scale_name=result.scale_name,
        scale_version=result.scale_version,
    )


def _scope_key(context: str, data: ScaleAssignmentInput) -> str:
    if context == "default":
        return "default"
    target = {
        "assessment": data.assessment_id,
        "subject": data.subject_id,
        "level": data.level_id,
        "stage": data.stage_id,
    }[context]
    return f"{context}:{target}"


async def _check_target(session: AsyncSession, data: ScaleAssignmentInput) -> None:
    target: Any
    label: str
    if data.context == "assessment":
        target = await session.get(Assessment, data.assessment_id)
        label = "assessment"
    elif data.context == "subject":
        target = await session.get(Subject, data.subject_id)
        label = "subject"
    elif data.context == "level":
        target = await session.get(GradeLevel, data.level_id)
        label = "level"
    elif data.context == "stage":
        target = await session.get(Stage, data.stage_id)
        label = "stage"
    else:
        return
    if target is None or getattr(target, "deleted_at", None) is not None:
        raise NotFound(
            f"The {label} does not exist",
            message_key=f"assessment.error.{label}_not_found",
            details={f"{label}_id": str(getattr(data, f"{label}_id"))},
        )


async def _assignment_out(
    session: AsyncSession, row: ScaleAssignment, scale: GradeScale
) -> ScaleAssignmentOut:
    assessment_title = None
    subject_name = None
    level_name = None
    stage_name = None
    if row.assessment_id is not None:
        assessment = await session.get(Assessment, row.assessment_id)
        assessment_title = assessment.title if assessment is not None else None
    if row.subject_id is not None:
        subject = await session.get(Subject, row.subject_id)
        subject_name = subject.name if subject is not None else None
    if row.level_id is not None:
        level = await session.get(GradeLevel, row.level_id)
        level_name = level.name if level is not None else None
    if row.stage_id is not None:
        stage = await session.get(Stage, row.stage_id)
        stage_name = stage.name if stage is not None else None
    return ScaleAssignmentOut(
        id=str(row.id),
        scale_id=str(row.scale_id),
        scale_name=scale.name,
        context=row.context,
        scope_key=row.scope_key,
        assessment_id=str(row.assessment_id) if row.assessment_id else None,
        assessment_title=assessment_title,
        subject_id=str(row.subject_id) if row.subject_id else None,
        subject_name=subject_name,
        level_id=str(row.level_id) if row.level_id else None,
        level_name=level_name,
        stage_id=str(row.stage_id) if row.stage_id else None,
        stage_name=stage_name,
        notes=row.notes,
        row_version=row.row_version,
    )


async def list_assignments(
    session: AsyncSession, *, scale_id: uuid.UUID | None = None
) -> ScaleAssignmentList:
    stmt = select(ScaleAssignment).where(ScaleAssignment.deleted_at.is_(None))
    if scale_id is not None:
        stmt = stmt.where(ScaleAssignment.scale_id == scale_id)
    rows = (await session.execute(stmt)).scalars().all()
    scale_rows = (
        (await session.execute(select(GradeScale).where(GradeScale.deleted_at.is_(None)))).scalars().all()
    )
    scales = {row.id: row for row in scale_rows}
    ordered = sorted(
        (row for row in rows if row.scale_id in scales),
        key=lambda row: (
            CONTEXT_ORDER.get(row.context, 99),
            scales[row.scale_id].name,
            row.scope_key,
        ),
    )
    items = [await _assignment_out(session, row, scales[row.scale_id]) for row in ordered]
    return ScaleAssignmentList(items=items, total=len(items))


async def create_assignment(
    session: AsyncSession,
    principal: Principal,
    data: ScaleAssignmentInput,
    *,
    via: str = "api",
) -> ScaleAssignmentOut:
    scale = await live_scale(session, data.scale_id)
    await _check_target(session, data)
    key = _scope_key(data.context, data)
    existing = (
        (
            await session.execute(
                select(ScaleAssignment).where(
                    ScaleAssignment.scope_key == key,
                    ScaleAssignment.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for row in existing:
        await soft_delete(
            session,
            row,
            action="assessment.scale.unassign",
            module=MODULE,
            actor=principal,
            reason="replaced by a new assignment",
            via=via,
            entity_type="scale_assignment",
        )
    row = ScaleAssignment(
        scale_id=scale.id,
        context=data.context,
        scope_key=key,
        assessment_id=data.assessment_id,
        subject_id=data.subject_id,
        level_id=data.level_id,
        stage_id=data.stage_id,
        notes=data.notes,
    )
    session.add(row)
    await session.flush()
    await record(
        session,
        action="assessment.scale.assign",
        module=MODULE,
        entity_type="scale_assignment",
        entity_id=str(row.id),
        after={
            "scale_id": str(scale.id),
            "context": row.context,
            "scope_key": row.scope_key,
            "notes": row.notes,
        },
        actor=principal,
        via=via,
    )
    await session.commit()
    return await _assignment_out(session, row, scale)


async def delete_assignment(
    session: AsyncSession,
    principal: Principal,
    assignment_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ScaleAssignment).where(
                ScaleAssignment.id == assignment_id,
                ScaleAssignment.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The scale assignment does not exist",
            message_key="assessment.error.assignment_not_found",
        )
    await soft_delete(
        session,
        row,
        action="assessment.scale.unassign",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="scale_assignment",
    )
    await session.commit()
    return {"id": str(row.id), "deleted": True}


__all__ = [
    "create_assignment",
    "create_scale",
    "delete_assignment",
    "delete_scale",
    "get_scale",
    "list_assignments",
    "list_scales",
    "live_scale",
    "test_scale",
    "update_scale",
]
