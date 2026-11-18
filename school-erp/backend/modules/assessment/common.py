"""Shared lookups and conversion helpers for assessment services.

The pure rules live in :mod:`modules.assessment.engine`; this module is the
only place that maps database rows onto those rules. Marks stay ``Decimal``
throughout, so a converted value never passes through a binary float.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.errors import NotFound, ValidationFailed
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear, GradeLevel, Section, Stage, Subject, Term
from modules.assessment.engine import (
    RoundingMode,
    ScoreStatus,
    converted_score,
)
from modules.assessment.engine import (
    Score as EngineScore,
)
from modules.assessment.models import (
    AssessmentComponent,
    AssessmentStructure,
    GradeScale,
)

MODULE = "assessment"


def utcnow() -> datetime:
    return datetime.now(UTC)


async def live_year(session: AsyncSession, year_id: uuid.UUID) -> AcademicYear:
    row = (
        await session.execute(
            select(AcademicYear).where(
                AcademicYear.id == year_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The academic year does not exist",
            message_key="assessment.error.year_not_found",
        )
    return row


async def live_term(session: AsyncSession, term_id: uuid.UUID) -> Term:
    row = (
        await session.execute(select(Term).where(Term.id == term_id, Term.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The term does not exist",
            message_key="assessment.error.term_not_found",
        )
    return row


async def live_section(session: AsyncSession, section_id: uuid.UUID) -> Section:
    row = (
        await session.execute(select(Section).where(Section.id == section_id, Section.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The section does not exist",
            message_key="assessment.error.section_not_found",
        )
    return row


async def live_subject(session: AsyncSession, subject_id: uuid.UUID) -> Subject:
    row = (
        await session.execute(select(Subject).where(Subject.id == subject_id, Subject.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The subject does not exist",
            message_key="assessment.error.subject_not_found",
        )
    return row


async def live_level(session: AsyncSession, level_id: uuid.UUID) -> GradeLevel:
    row = (
        await session.execute(
            select(GradeLevel).where(
                GradeLevel.id == level_id,
                GradeLevel.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The grade level does not exist",
            message_key="assessment.error.level_not_found",
        )
    return row


async def live_stage(session: AsyncSession, stage_id: uuid.UUID) -> Stage:
    row = (
        await session.execute(select(Stage).where(Stage.id == stage_id, Stage.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The stage does not exist",
            message_key="assessment.error.stage_not_found",
        )
    return row


async def live_structure(session: AsyncSession, structure_id: uuid.UUID) -> AssessmentStructure:
    row = (
        await session.execute(
            select(AssessmentStructure).where(
                AssessmentStructure.id == structure_id,
                AssessmentStructure.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The mark structure does not exist",
            message_key="assessment.error.structure_not_found",
        )
    return row


async def live_scale(session: AsyncSession, scale_id: uuid.UUID) -> GradeScale:
    row = (
        await session.execute(
            select(GradeScale).where(
                GradeScale.id == scale_id,
                GradeScale.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The grade scale does not exist",
            message_key="assessment.error.scale_not_found",
        )
    return row


async def structure_components(
    session: AsyncSession,
    structure_id: uuid.UUID,
) -> list[AssessmentComponent]:
    rows = (
        await session.execute(
            select(AssessmentComponent)
            .where(
                AssessmentComponent.structure_id == structure_id,
                AssessmentComponent.deleted_at.is_(None),
            )
            .order_by(AssessmentComponent.sort_order, AssessmentComponent.key)
        )
    ).scalars()
    return list(rows)


def scope_key(
    scope_type: str,
    *,
    level_id: uuid.UUID | None = None,
    stage_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
) -> str:
    """Deterministic key for the live unique index on (year, scope)."""
    if scope_type == "school":
        return "school"
    if scope_type == "level" and level_id is not None:
        return f"level:{level_id}"
    if scope_type == "stage" and stage_id is not None:
        return f"stage:{stage_id}"
    if scope_type == "subject" and subject_id is not None:
        return f"subject:{subject_id}"
    raise ValidationFailed(
        "A structure scope needs exactly one matching target",
        message_key="assessment.error.structure_scope",
        details={"scope_type": scope_type},
    )


def score_status(value: str) -> ScoreStatus:
    try:
        return ScoreStatus(value)
    except ValueError as exc:  # pragma: no cover - guarded by the database writers
        raise ValidationFailed(
            "Unknown score status",
            message_key="assessment.error.score_status",
            details={"status": value},
        ) from exc


def rounding_mode(value: str) -> RoundingMode:
    try:
        return RoundingMode(value)
    except ValueError as exc:
        raise ValidationFailed(
            "Unknown rounding mode",
            message_key="assessment.error.rounding",
            details={"rounding": value},
        ) from exc


def converted_for(
    *,
    raw: Decimal | None,
    out_of: Decimal,
    status: str,
    component: AssessmentComponent,
    structure: AssessmentStructure,
) -> Decimal | None:
    """The converted value one score receives under a structure's rules."""
    engine_score = EngineScore(
        out_of=out_of,
        raw=raw,
        status=score_status(status),
    )
    return converted_score(
        engine_score,
        max_points=component.max_points,
        absent_counts_as_zero=component.absent_counts_as_zero,
        precision=structure.precision,
        rounding=rounding_mode(structure.rounding),
    )


def decimal_out(value: Decimal | None) -> str | None:
    """Serialise an exact mark as a decimal string, never a JSON float.

    Trailing zeros are dropped (``10.000000`` becomes ``10``) so the same value
    is written the same way whether it came from storage or from the engine.
    """
    if value is None:
        return None
    text = format(value.normalize(), "f")
    return "0" if text == "-0" else text


def structure_state(row: AssessmentStructure) -> dict[str, Any]:
    return {
        "year_id": str(row.year_id),
        "scope_type": row.scope_type,
        "scope_key": row.scope_key,
        "name": row.name,
        "name_am": row.name_am,
        "term_system": row.term_system,
        "year_mode": row.year_mode,
        "year_weights": row.year_weights,
        "precision": row.precision,
        "rounding": row.rounding,
        "intended_total": decimal_out(row.intended_total),
        "descriptive_mode": row.descriptive_mode,
        "version": row.version,
        "is_active": row.is_active,
        "row_version": row.row_version,
        "deleted": row.deleted_at is not None,
    }


def component_state(row: AssessmentComponent) -> dict[str, Any]:
    return {
        "key": row.key,
        "name": row.name,
        "name_am": row.name_am,
        "max_points": decimal_out(row.max_points),
        "aggregation": row.aggregation,
        "absent_counts_as_zero": row.absent_counts_as_zero,
        "best_n": row.best_n,
        "cap": decimal_out(row.cap),
        "sort_order": row.sort_order,
        "is_active": row.is_active,
    }


__all__ = [
    "MODULE",
    "component_state",
    "converted_for",
    "decimal_out",
    "live_level",
    "live_scale",
    "live_section",
    "live_stage",
    "live_structure",
    "live_subject",
    "live_term",
    "live_year",
    "rounding_mode",
    "scope_key",
    "score_status",
    "structure_components",
    "structure_state",
    "utcnow",
]
