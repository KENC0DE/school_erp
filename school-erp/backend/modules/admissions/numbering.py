"""Application numbers with a configurable format and atomic sequence.

The pattern mirrors student numbering: the school owns the format and scope,
and allocation is one dialect upsert so concurrent applications never share a
number. A failed create can leave a gap, never a duplicate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.errors import ValidationFailed
from core.db.base import uuid7
from core.settings.service import load_model
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics import years as year_service
from modules.admissions.models import AdmissionNumberSequence
from modules.admissions.settings import AdmissionSettings
from modules.students.number_formats import MAX_NUMBER_LENGTH, compile_format

MODULE = "admissions"
YEAR_SCOPE = "year"
GLOBAL_SCOPE = "global"


@dataclass(frozen=True)
class Allocation:
    application_number: str
    scope: str
    year: int
    sequence: int


async def load_settings(session: AsyncSession) -> AdmissionSettings:
    return await load_model(session, MODULE, AdmissionSettings)


async def resolve_context(
    session: AsyncSession,
    settings: AdmissionSettings,
    *,
    year_id: uuid.UUID | None = None,
) -> tuple[str, int]:
    target = year_id
    if target is None:
        years = await year_service.list_years(session)
        target = uuid.UUID(years.current_year_id) if years.current_year_id else None
        if target is None and years.items:
            target = uuid.UUID(years.items[0].id)
    if target is None:
        raise ValidationFailed(
            "Create an academic year before taking applications",
            message_key="admissions.error.year_required",
        )
    year = await year_service.get_year(session, target)
    if settings.numbering.scope == GLOBAL_SCOPE:
        return GLOBAL_SCOPE, year.start_date.year
    return f"{YEAR_SCOPE}:{year.id}", year.start_date.year


def _render(
    settings: AdmissionSettings,
    *,
    scope: str,
    year: int,
    sequence: int,
) -> Allocation:
    try:
        number = compile_format(settings.numbering.format).render(year=year, seq=sequence)
    except ValueError as exc:
        raise ValidationFailed(
            str(exc),
            message_key="admissions.error.numbering_too_long",
            details={"format": settings.numbering.format},
        ) from exc
    if len(number) > MAX_NUMBER_LENGTH:
        raise ValidationFailed(
            "The generated application number is too long",
            message_key="admissions.error.numbering_too_long",
            details={"format": settings.numbering.format},
        )
    return Allocation(application_number=number, scope=scope, year=year, sequence=sequence)


async def peek_number(
    session: AsyncSession,
    *,
    year_id: uuid.UUID | None = None,
) -> Allocation:
    settings = await load_settings(session)
    scope, year = await resolve_context(session, settings, year_id=year_id)
    current = (
        await session.execute(
            select(AdmissionNumberSequence.value).where(AdmissionNumberSequence.scope == scope)
        )
    ).scalar_one_or_none()
    sequence = settings.numbering.start if current is None else current + 1
    return _render(settings, scope=scope, year=year, sequence=sequence)


async def _next_value(session: AsyncSession, scope: str, start: int) -> int:
    table = AdmissionNumberSequence.__table__
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        statement = pg_insert(table)
    elif dialect == "sqlite":
        statement = sqlite_insert(table)
    else:  # pragma: no cover - only the two supported databases reach here
        raise RuntimeError(f"Admission numbering is not implemented for {dialect}")
    statement = (
        statement.values(id=uuid7(), scope=scope, value=start)
        .on_conflict_do_update(
            index_elements=[table.c.scope],
            set_={"value": table.c.value + 1, "updated_at": func.now()},
        )
        .returning(table.c.value)
    )
    return int((await session.execute(statement)).scalar_one())


async def allocate_number(
    session: AsyncSession,
    *,
    year_id: uuid.UUID | None = None,
) -> Allocation:
    """Reserve the next number in its own short transaction."""
    settings = await load_settings(session)
    scope, year = await resolve_context(session, settings, year_id=year_id)
    await session.commit()
    sequence = await _next_value(session, scope, settings.numbering.start)
    await session.commit()
    return _render(settings, scope=scope, year=year, sequence=sequence)


__all__ = [
    "Allocation",
    "GLOBAL_SCOPE",
    "YEAR_SCOPE",
    "allocate_number",
    "load_settings",
    "peek_number",
    "resolve_context",
]
