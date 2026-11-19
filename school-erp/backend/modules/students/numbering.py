"""Student-number generation with a configurable format and atomic sequence.

The school can reset numbering every academic year or keep one global counter,
and can choose the first value. Allocation is a single dialect upsert, so two
concurrent registrations can never receive the same number. Because a number is
committed before the rest of registration runs, a failed registration leaves a
gap but never a duplicate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from app.errors import ValidationFailed
from core.db.base import uuid7
from core.settings.service import load_model
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics import years as year_service
from modules.academics.models import AcademicYear
from modules.students.models import StudentNumberSequence
from modules.students.number_formats import MAX_NUMBER_LENGTH, compile_format
from modules.students.settings import StudentSettings

MODULE = "students"
YEAR_SCOPE = "year"
GLOBAL_SCOPE = "global"


@dataclass(frozen=True)
class Allocation:
    """One rendered student number and the sequence state behind it."""

    student_number: str
    scope: str
    year: int
    sequence: int


async def load_settings(session: AsyncSession) -> StudentSettings:
    return await load_model(session, MODULE, StudentSettings)


async def _latest_year(session: AsyncSession) -> AcademicYear | None:
    """The open year if there is one, else the most recently started year."""
    base = select(AcademicYear).where(AcademicYear.deleted_at.is_(None))
    open_year = (
        await session.execute(
            base.where(AcademicYear.status == "open")
            .order_by(AcademicYear.start_date.desc(), AcademicYear.code)
            .limit(1)
        )
    ).scalar_one_or_none()
    if open_year is not None:
        return open_year
    return (
        await session.execute(base.order_by(AcademicYear.start_date.desc(), AcademicYear.code).limit(1))
    ).scalar_one_or_none()


async def resolve_context(
    session: AsyncSession,
    settings: StudentSettings,
    *,
    year_id: uuid.UUID | None = None,
) -> tuple[str, int]:
    """Resolve the sequence bucket and the year used by ``{year}``.

    An explicit year (the enrollment year) wins. Otherwise the school's open
    year is preferred, then the most recent year. Before any academic year
    exists the counter falls back to the calendar year so registration can
    still start.
    """
    if year_id is not None:
        year = await year_service.get_year(session, year_id)
        scope = f"{YEAR_SCOPE}:{year.id}" if settings.numbering.scope == YEAR_SCOPE else GLOBAL_SCOPE
        return scope, year.start_date.year

    latest = await _latest_year(session)
    if settings.numbering.scope == GLOBAL_SCOPE:
        return GLOBAL_SCOPE, latest.start_date.year if latest is not None else date.today().year
    if latest is None:
        return f"calendar:{date.today().year}", date.today().year
    return f"{YEAR_SCOPE}:{latest.id}", latest.start_date.year


def _render(
    settings: StudentSettings,
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
            message_key="students.error.numbering_too_long",
            details={"format": settings.numbering.format},
        ) from exc
    return Allocation(student_number=number, scope=scope, year=year, sequence=sequence)


async def peek_number(
    session: AsyncSession,
    *,
    year_id: uuid.UUID | None = None,
) -> Allocation:
    """Return the candidate number without reserving it.

    A preview is deliberately not a reservation: two forms open at once may see
    the same candidate. Registration allocates atomically.
    """
    settings = await load_settings(session)
    scope, year = await resolve_context(session, settings, year_id=year_id)
    current = (
        await session.execute(select(StudentNumberSequence.value).where(StudentNumberSequence.scope == scope))
    ).scalar_one_or_none()
    sequence = settings.numbering.start if current is None else current + 1
    return _render(settings, scope=scope, year=year, sequence=sequence)


async def _next_value(session: AsyncSession, scope: str, start: int) -> int:
    """Atomically bump one scope and return the issued value."""
    table = StudentNumberSequence.__table__
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        statement = pg_insert(table)
    elif dialect == "sqlite":
        statement = sqlite_insert(table)
    else:  # pragma: no cover - only the two supported databases reach here
        raise RuntimeError(f"Student numbering is not implemented for {dialect}")
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
    """Reserve the next number and commit it immediately.

    Call this before staging any other write: the short, independent
    transaction is what lets concurrent registrations proceed without holding
    the sequence row open.
    """
    settings = await load_settings(session)
    scope, year = await resolve_context(session, settings, year_id=year_id)
    await session.commit()  # end the settings read transaction before writing
    sequence = await _next_value(session, scope, settings.numbering.start)
    await session.commit()
    return _render(settings, scope=scope, year=year, sequence=sequence)


__all__ = [
    "Allocation",
    "GLOBAL_SCOPE",
    "MAX_NUMBER_LENGTH",
    "YEAR_SCOPE",
    "allocate_number",
    "load_settings",
    "peek_number",
    "resolve_context",
]
