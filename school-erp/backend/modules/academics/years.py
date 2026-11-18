"""Academic years and terms (ARCH §9.1).

Dates are stored in GC so ordering and reporting never depend on a display
preference. Responses also carry the Ethiopian equivalent and a formatted label
that follows the school's ``school_profile.calendar`` setting.

Term count is fixed when a year is created from the school's term system
(``semester`` → 2, ``quarter`` → 4). The year keeps that snapshot even if the
setting changes later, because results and document templates address terms by
number.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.calendar.ethiopian import format_dual, from_gregorian
from core.db.soft_delete import get_including_deleted, restore, soft_delete
from core.settings.core_schema import CoreSettings
from core.settings.service import effective_map
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear, Term
from modules.academics.schemas import (
    TermInput,
    TermOut,
    TermUpdate,
    YearCreate,
    YearList,
    YearOut,
    YearUpdate,
)

MODULE = "academics"
TERM_COUNTS = {"semester": 2, "quarter": 4}
TERM_LABELS = {
    "semester": ("Semester", "ሴሚስተር"),
    "quarter": ("Quarter", "ሩብ ዓመት"),
}


def _ec(value: date) -> str:
    year, month, day = from_gregorian(value)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _display(value: date, *, calendar: str, locale: str) -> str:
    preference = calendar if calendar in ("ethiopian", "gregorian") else "both"
    return format_dual(value, preference=preference, locale=locale)


async def _display_context(session: AsyncSession) -> tuple[str, str]:
    effective = await effective_map(session, "core", CoreSettings)
    return (
        str(effective["school_profile.calendar"].value),
        str(effective["school_profile.default_language"].value),
    )


async def term_system(session: AsyncSession) -> str:
    effective = await effective_map(session, "core", CoreSettings)
    return str(effective["academic_scope.term_system"].value)


def _term_out(term: Term, *, calendar: str, locale: str) -> TermOut:
    return TermOut(
        id=str(term.id),
        year_id=str(term.year_id),
        number=term.number,
        name=term.name,
        name_am=term.name_am,
        start_date=term.start_date,
        end_date=term.end_date,
        start_date_ec=_ec(term.start_date),
        end_date_ec=_ec(term.end_date),
        start_date_display=_display(term.start_date, calendar=calendar, locale=locale),
        end_date_display=_display(term.end_date, calendar=calendar, locale=locale),
        status=term.status,
        row_version=term.row_version,
    )


def _year_state(year: AcademicYear, terms: list[Term]) -> dict[str, Any]:
    return {
        "code": year.code,
        "name": year.name,
        "name_am": year.name_am,
        "start_date": year.start_date.isoformat(),
        "end_date": year.end_date.isoformat(),
        "term_system": year.term_system,
        "status": year.status,
        "terms": [{"number": term.number, "status": term.status} for term in terms],
        "row_version": year.row_version,
    }


def _term_state(term: Term) -> dict[str, Any]:
    return {
        "number": term.number,
        "name": term.name,
        "name_am": term.name_am,
        "start_date": term.start_date.isoformat(),
        "end_date": term.end_date.isoformat(),
        "status": term.status,
        "row_version": term.row_version,
    }


async def _terms(session: AsyncSession, year_id: uuid.UUID) -> list[Term]:
    return list(
        (await session.execute(select(Term).where(Term.year_id == year_id).order_by(Term.number))).scalars()
    )


async def _year_out(session: AsyncSession, year: AcademicYear, terms: list[Term] | None = None) -> YearOut:
    calendar, locale = await _display_context(session)
    rows = terms if terms is not None else await _terms(session, year.id)
    open_term = next((term for term in rows if term.status == "open"), None)
    return YearOut(
        id=str(year.id),
        code=year.code,
        name=year.name,
        name_am=year.name_am,
        start_date=year.start_date,
        end_date=year.end_date,
        start_date_ec=_ec(year.start_date),
        end_date_ec=_ec(year.end_date),
        start_date_display=_display(year.start_date, calendar=calendar, locale=locale),
        end_date_display=_display(year.end_date, calendar=calendar, locale=locale),
        term_system=year.term_system,  # type: ignore[arg-type]
        status=year.status,  # type: ignore[arg-type]
        current_term_id=str(open_term.id) if open_term is not None else None,
        terms=[_term_out(term, calendar=calendar, locale=locale) for term in rows],
        row_version=year.row_version,
    )


async def _live_year(session: AsyncSession, year_id: uuid.UUID) -> AcademicYear:
    year = (
        await session.execute(select(AcademicYear).where(AcademicYear.id == year_id))
    ).scalar_one_or_none()
    if year is None:
        raise NotFound(
            "The academic year does not exist",
            message_key="error.academics.year_not_found",
        )
    return year


async def _live_term(session: AsyncSession, year: AcademicYear, term_id: uuid.UUID) -> Term:
    term = (
        await session.execute(select(Term).where(Term.id == term_id, Term.year_id == year.id))
    ).scalar_one_or_none()
    if term is None:
        raise NotFound(
            "The term does not exist in that academic year",
            message_key="error.academics.term_not_found",
        )
    return term


async def _assert_code_free(session: AsyncSession, code: str, *, current_id: uuid.UUID | None = None) -> None:
    stmt = select(AcademicYear.id).where(AcademicYear.code == code)
    if current_id is not None:
        stmt = stmt.where(AcademicYear.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "An academic year with that code already exists",
            message_key="error.academics.year_code_taken",
            details={"code": code},
        )


def _validate_dates(year: AcademicYear, terms: list[tuple[TermInput, int]]) -> None:
    if year.start_date >= year.end_date:
        raise ValidationFailed(
            "The academic year must end after it starts",
            message_key="error.academics.year_dates",
            details={"start_date": year.start_date.isoformat(), "end_date": year.end_date.isoformat()},
        )
    previous_end: date | None = None
    for term_input, _number in terms:
        if term_input.start_date > term_input.end_date:
            raise ValidationFailed(
                "A term must end on or after it starts",
                message_key="error.academics.term_dates",
                details={"name": term_input.name},
            )
        if term_input.start_date < year.start_date or term_input.end_date > year.end_date:
            raise ValidationFailed(
                "Terms must fall inside the academic year",
                message_key="error.academics.term_outside_year",
                details={"name": term_input.name},
            )
        if previous_end is not None and term_input.start_date <= previous_end:
            raise ValidationFailed(
                "Terms must be in order and must not overlap",
                message_key="error.academics.term_overlap",
                details={"name": term_input.name},
            )
        previous_end = term_input.end_date


def _default_terms(year: AcademicYear, system: str) -> list[TermInput]:
    count = TERM_COUNTS[system]
    total_days = (year.end_date - year.start_date).days + 1
    if total_days < count:
        raise ValidationFailed(
            "That academic year is too short for its term system",
            message_key="error.academics.year_too_short",
            details={"term_system": system, "days": total_days},
        )
    base, extra = divmod(total_days, count)
    english, amharic = TERM_LABELS[system]
    cursor = year.start_date
    terms: list[TermInput] = []
    for index in range(count):
        length = base + (1 if index < extra else 0)
        term_end = cursor + timedelta(days=length - 1)
        number = index + 1
        terms.append(
            TermInput(
                name=f"{english} {number}",
                name_am=f"{amharic} {number}",
                start_date=cursor,
                end_date=term_end,
            )
        )
        cursor = term_end + timedelta(days=1)
    return terms


async def list_years(
    session: AsyncSession,
    *,
    status: str | None = None,
) -> YearList:
    stmt = select(AcademicYear)
    if status is not None:
        stmt = stmt.where(AcademicYear.status == status)
    years = (
        (await session.execute(stmt.order_by(AcademicYear.start_date.desc(), AcademicYear.code)))
        .scalars()
        .all()
    )
    items = [await _year_out(session, year) for year in years]
    current = next((item for item in items if item.status == "open"), None)
    return YearList(
        items=items,
        total=len(items),
        current_year_id=current.id if current is not None else None,
    )


async def get_year(session: AsyncSession, year_id: uuid.UUID) -> YearOut:
    return await _year_out(session, await _live_year(session, year_id))


async def create_year(
    session: AsyncSession,
    principal: Principal,
    data: YearCreate,
    *,
    via: str = "api",
) -> YearOut:
    await _assert_code_free(session, data.code)
    if data.start_date >= data.end_date:
        raise ValidationFailed(
            "The academic year must end after it starts",
            message_key="error.academics.year_dates",
        )
    system = await term_system(session)
    year = AcademicYear(
        code=data.code,
        name=data.name,
        name_am=data.name_am,
        start_date=data.start_date,
        end_date=data.end_date,
        term_system=system,
        status="draft",
    )
    provided = data.terms or _default_terms(year, system)
    expected = TERM_COUNTS[system]
    if len(provided) != expected:
        raise ValidationFailed(
            "The number of terms must match the school's term system",
            message_key="error.academics.term_count",
            details={"expected": expected, "received": len(provided), "term_system": system},
        )
    if any(
        first.start_date > second.start_date for first, second in zip(provided, provided[1:], strict=False)
    ):
        raise ValidationFailed(
            "Terms must be supplied in date order",
            message_key="error.academics.term_order",
        )
    ordered = provided
    _validate_dates(year, [(item, index + 1) for index, item in enumerate(ordered)])
    session.add(year)
    await session.flush()
    for index, item in enumerate(ordered):
        session.add(
            Term(
                year_id=year.id,
                number=index + 1,
                name=item.name,
                name_am=item.name_am,
                start_date=item.start_date,
                end_date=item.end_date,
                status="pending",
            )
        )
    await session.flush()
    terms = await _terms(session, year.id)
    await record(
        session,
        action="academics.years.create",
        module=MODULE,
        entity_type="academic_year",
        entity_id=str(year.id),
        after=_year_state(year, terms),
        actor=principal,
        via=via,
    )
    return await _year_out(session, year, terms)


async def update_year(
    session: AsyncSession,
    principal: Principal,
    year_id: uuid.UUID,
    data: YearUpdate,
    *,
    via: str = "api",
    reason: str | None = None,
) -> YearOut:
    year = await _live_year(session, year_id)
    terms = await _terms(session, year.id)
    if year.status == "closed":
        raise Conflict(
            "A closed academic year cannot be edited",
            message_key="error.academics.year_closed",
        )
    before = _year_state(year, terms)
    ensure_row_version(year, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    changes: dict[str, Any] = {}
    for key in ("name", "name_am", "start_date", "end_date"):
        if key not in payload:
            continue
        value = payload[key]
        if value is None and key != "name_am":
            continue
        if getattr(year, key) != value:
            setattr(year, key, value)
            changes[key] = value.isoformat() if isinstance(value, date) else value
    if changes:
        _validate_dates(
            year,
            [
                (
                    TermInput(
                        name=term.name,
                        name_am=term.name_am,
                        start_date=term.start_date,
                        end_date=term.end_date,
                    ),
                    term.number,
                )
                for term in terms
            ],
        )
        year.row_version = (year.row_version or 0) + 1
    await session.flush()
    if changes:
        await record(
            session,
            action="academics.years.update",
            module=MODULE,
            entity_type="academic_year",
            entity_id=str(year.id),
            before=before,
            after=_year_state(year, terms),
            actor=principal,
            reason=reason,
            via=via,
        )
    return await _year_out(session, year, terms)


async def delete_year(
    session: AsyncSession,
    principal: Principal,
    year_id: uuid.UUID,
    *,
    row_version: int | None = None,
    reason: str | None = None,
    via: str = "api",
) -> YearOut:
    year = await _live_year(session, year_id)
    terms = await _terms(session, year.id)
    if year.status != "draft":
        raise Conflict(
            "Only a draft academic year can be deleted; close it instead",
            message_key="error.academics.year_not_draft",
        )
    if row_version is not None:
        ensure_row_version(year, row_version, current_state=_year_state(year, terms))
    await soft_delete(
        session,
        year,
        action="academics.years.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="academic_year",
    )
    await session.flush()
    return await _year_out(session, year, terms)


async def restore_year(
    session: AsyncSession,
    principal: Principal,
    year_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> YearOut:
    year = await get_including_deleted(session, AcademicYear, year_id)
    if year is None:
        raise NotFound(
            "The academic year does not exist",
            message_key="error.academics.year_not_found",
        )
    await _assert_code_free(session, year.code, current_id=year.id)
    await restore(
        session,
        year,
        action="academics.years.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="academic_year",
    )
    await session.flush()
    return await _year_out(session, year)


async def open_year(
    session: AsyncSession,
    principal: Principal,
    year_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> YearOut:
    year = await _live_year(session, year_id)
    terms = await _terms(session, year.id)
    if year.status == "open":
        return await _year_out(session, year, terms)
    other = (
        await session.execute(
            select(AcademicYear).where(
                AcademicYear.status == "open",
                AcademicYear.id != year.id,
            )
        )
    ).scalar_one_or_none()
    if other is not None:
        raise Conflict(
            "Another academic year is already open; close it first",
            message_key="error.academics.year_already_open",
            details={"code": other.code},
        )
    before = _year_state(year, terms)
    year.status = "open"
    year.row_version = (year.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="academics.years.open",
        module=MODULE,
        entity_type="academic_year",
        entity_id=str(year.id),
        before=before,
        after=_year_state(year, terms),
        actor=principal,
        reason=reason,
        via=via,
    )
    return await _year_out(session, year, terms)


async def close_year(
    session: AsyncSession,
    principal: Principal,
    year_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> YearOut:
    year = await _live_year(session, year_id)
    terms = await _terms(session, year.id)
    if year.status == "draft":
        raise Conflict(
            "Only an open academic year can be closed",
            message_key="error.academics.year_not_open",
        )
    if year.status == "closed":
        return await _year_out(session, year, terms)
    before = _year_state(year, terms)
    year.status = "closed"
    year.row_version = (year.row_version or 0) + 1
    for term in terms:
        if term.status != "closed":
            term.status = "closed"
            term.row_version = (term.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="academics.years.close",
        module=MODULE,
        entity_type="academic_year",
        entity_id=str(year.id),
        before=before,
        after=_year_state(year, terms),
        actor=principal,
        reason=reason,
        via=via,
    )
    return await _year_out(session, year, terms)


async def update_term(
    session: AsyncSession,
    principal: Principal,
    year_id: uuid.UUID,
    term_id: uuid.UUID,
    data: TermUpdate,
    *,
    via: str = "api",
    reason: str | None = None,
) -> YearOut:
    year = await _live_year(session, year_id)
    terms = await _terms(session, year.id)
    term = await _live_term(session, year, term_id)
    if year.status == "closed":
        raise Conflict(
            "A closed academic year cannot be edited",
            message_key="error.academics.year_closed",
        )
    before = _term_state(term)
    ensure_row_version(term, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    changes: dict[str, Any] = {}
    for key in ("name", "name_am", "start_date", "end_date"):
        if key not in payload:
            continue
        value = payload[key]
        if value is None and key != "name_am":
            continue
        if getattr(term, key) != value:
            setattr(term, key, value)
            changes[key] = value.isoformat() if isinstance(value, date) else value
    if changes:
        _validate_dates(
            year,
            [
                (
                    TermInput(
                        name=item.name,
                        name_am=item.name_am,
                        start_date=item.start_date,
                        end_date=item.end_date,
                    ),
                    item.number,
                )
                for item in sorted(terms, key=lambda row: row.number)
            ],
        )
        term.row_version = (term.row_version or 0) + 1
    await session.flush()
    if changes:
        await record(
            session,
            action="academics.terms.update",
            module=MODULE,
            entity_type="academic_term",
            entity_id=str(term.id),
            before=before,
            after=_term_state(term),
            actor=principal,
            reason=reason,
            via=via,
        )
    return await _year_out(session, year, terms)


async def open_term(
    session: AsyncSession,
    principal: Principal,
    year_id: uuid.UUID,
    term_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> YearOut:
    year = await _live_year(session, year_id)
    terms = await _terms(session, year.id)
    term = await _live_term(session, year, term_id)
    if year.status != "open":
        raise Conflict(
            "Open the academic year before opening a term",
            message_key="error.academics.year_not_open",
        )
    if term.status == "open":
        return await _year_out(session, year, terms)
    other = next((item for item in terms if item.status == "open" and item.id != term.id), None)
    if other is not None:
        raise Conflict(
            "Another term is already open; close it first",
            message_key="error.academics.term_already_open",
            details={"number": other.number},
        )
    before = _term_state(term)
    term.status = "open"
    term.row_version = (term.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="academics.terms.open",
        module=MODULE,
        entity_type="academic_term",
        entity_id=str(term.id),
        before=before,
        after=_term_state(term),
        actor=principal,
        reason=reason,
        via=via,
    )
    return await _year_out(session, year, terms)


async def close_term(
    session: AsyncSession,
    principal: Principal,
    year_id: uuid.UUID,
    term_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> YearOut:
    year = await _live_year(session, year_id)
    terms = await _terms(session, year.id)
    term = await _live_term(session, year, term_id)
    if term.status == "pending":
        raise Conflict(
            "Only an open term can be closed",
            message_key="error.academics.term_not_open",
        )
    if term.status == "closed":
        return await _year_out(session, year, terms)
    before = _term_state(term)
    term.status = "closed"
    term.row_version = (term.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="academics.terms.close",
        module=MODULE,
        entity_type="academic_term",
        entity_id=str(term.id),
        before=before,
        after=_term_state(term),
        actor=principal,
        reason=reason,
        via=via,
    )
    return await _year_out(session, year, terms)


__all__ = [
    "TERM_COUNTS",
    "close_term",
    "close_year",
    "create_year",
    "delete_year",
    "get_year",
    "list_years",
    "open_term",
    "open_year",
    "restore_year",
    "term_system",
    "update_term",
    "update_year",
]
