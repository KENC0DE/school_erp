"""Attendance reports by student and by section (ARCH §9.4).

Every report is a parameterized aggregate: no raw SQL and no client-built
filters. Scopes narrow the sections before aggregation, and the threshold is an
integer percentage so a report never depends on float rounding.
"""

from __future__ import annotations

from typing import Any

from app.errors import ValidationFailed
from core.auth.principal import Principal
from core.people.models import Person, full_name
from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear, GradeLevel, Section
from modules.attendance import scoping
from modules.attendance.models import AttendanceRecord, AttendanceSession
from modules.attendance.schemas import (
    AttendanceReportQuery,
    SectionAttendanceReport,
    SectionAttendanceReportRow,
    StudentAttendanceReport,
    StudentAttendanceReportRow,
)
from modules.students.models import StudentProfile


def _rate(attended: int, total: int) -> int:
    if total <= 0:
        return 0
    return (attended * 100 + total // 2) // total


def _counts(row: Any) -> dict[str, int]:
    """Unpack (total, present, absent, late, excused) aggregate columns."""
    total, present, absent, late, excused = (int(value or 0) for value in row)
    return {
        "total_records": total,
        "present": present,
        "absent": absent,
        "late": late,
        "excused": excused,
        "attended": present + late,
    }


def _sum_columns():
    return (
        func.coalesce(func.sum(case((AttendanceRecord.status == "present", 1), else_=0)), 0),
        func.coalesce(func.sum(case((AttendanceRecord.status == "absent", 1), else_=0)), 0),
        func.coalesce(func.sum(case((AttendanceRecord.status == "late", 1), else_=0)), 0),
        func.coalesce(func.sum(case((AttendanceRecord.status == "excused", 1), else_=0)), 0),
    )


async def _clauses(
    session: AsyncSession,
    principal: Principal,
    query: AttendanceReportQuery,
) -> list[Any] | None:
    """Shared WHERE clauses, or ``None`` when the caller may see no section."""
    if query.to_date < query.from_date:
        raise ValidationFailed(
            "The end date must not be before the start date",
            message_key="attendance.error.report_range",
            details={
                "from_date": query.from_date.isoformat(),
                "to_date": query.to_date.isoformat(),
            },
        )
    if (query.to_date - query.from_date).days > 366:
        raise ValidationFailed(
            "An attendance report covers at most 366 days",
            message_key="attendance.error.report_too_long",
            details={"max_days": 366},
        )
    clauses: list[Any] = [
        AttendanceRecord.deleted_at.is_(None),
        AttendanceSession.deleted_at.is_(None),
        AttendanceSession.date >= query.from_date,
        AttendanceSession.date <= query.to_date,
    ]
    allowed = await scoping.visible_section_ids(session, principal, "attendance.view")
    if allowed is not None:
        if not allowed:
            return None
        clauses.append(AttendanceSession.section_id.in_(allowed))
    if query.year_id is not None:
        clauses.append(AttendanceSession.year_id == query.year_id)
    if query.section_id is not None:
        clauses.append(AttendanceSession.section_id == query.section_id)
    if query.student_id is not None:
        clauses.append(AttendanceRecord.student_id == query.student_id)
    return clauses


async def student_report(
    session: AsyncSession,
    principal: Principal,
    query: AttendanceReportQuery,
) -> StudentAttendanceReport:
    clauses = await _clauses(session, principal, query)
    if clauses is None:
        return StudentAttendanceReport(
            from_date=query.from_date,
            to_date=query.to_date,
            threshold=query.threshold,
            below_only=query.below_only,
            total=0,
            items=[],
        )

    rows = (
        await session.execute(
            select(
                AttendanceRecord.student_id,
                AttendanceSession.year_id,
                AttendanceSession.section_id,
                func.count(AttendanceRecord.id),
                *_sum_columns(),
            )
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .where(*clauses)
            .group_by(
                AttendanceRecord.student_id,
                AttendanceSession.year_id,
                AttendanceSession.section_id,
            )
        )
    ).all()

    student_ids = {row[0] for row in rows}
    year_ids = {row[1] for row in rows}
    section_ids = {row[2] for row in rows}
    profiles = (
        {
            row.id: row
            for row in (
                await session.execute(select(StudentProfile).where(StudentProfile.id.in_(student_ids)))
            )
            .scalars()
            .all()
        }
        if student_ids
        else {}
    )
    people = (
        {
            row.id: row
            for row in (
                await session.execute(
                    select(Person).where(Person.id.in_({profile.person_id for profile in profiles.values()}))
                )
            )
            .scalars()
            .all()
        }
        if profiles
        else {}
    )
    years = (
        {
            row.id: row
            for row in (await session.execute(select(AcademicYear).where(AcademicYear.id.in_(year_ids))))
            .scalars()
            .all()
        }
        if year_ids
        else {}
    )
    sections = (
        {
            row.id: row
            for row in (await session.execute(select(Section).where(Section.id.in_(section_ids))))
            .scalars()
            .all()
        }
        if section_ids
        else {}
    )

    items: list[StudentAttendanceReportRow] = []
    for row in rows:
        student_id, year_id, section_id = row[0], row[1], row[2]
        profile = profiles.get(student_id)
        year = years.get(year_id)
        section = sections.get(section_id)
        if profile is None or year is None or section is None:
            continue
        person = people.get(profile.person_id)
        counts = _counts(row[3:])
        rate = _rate(counts["attended"], counts["total_records"])
        items.append(
            StudentAttendanceReportRow(
                student_id=str(student_id),
                student_number=profile.student_number,
                student_name=full_name(person, "en") if person else profile.student_number,
                student_name_am=(full_name(person, "am") or None) if person else None,
                year_id=str(year_id),
                year_code=year.code,
                section_id=str(section_id),
                section_code=section.code,
                section_name=section.name,
                total_records=counts["total_records"],
                present=counts["present"],
                absent=counts["absent"],
                late=counts["late"],
                excused=counts["excused"],
                attended=counts["attended"],
                rate_percent=rate,
                below_threshold=rate < query.threshold,
            )
        )

    if query.below_only:
        items = [item for item in items if item.below_threshold]
    items.sort(key=lambda item: (item.rate_percent, item.student_name, item.student_number))
    total = len(items)
    return StudentAttendanceReport(
        from_date=query.from_date,
        to_date=query.to_date,
        threshold=query.threshold,
        below_only=query.below_only,
        total=total,
        items=items[: query.limit],
    )


async def section_report(
    session: AsyncSession,
    principal: Principal,
    query: AttendanceReportQuery,
) -> SectionAttendanceReport:
    clauses = await _clauses(session, principal, query)
    if clauses is None:
        return SectionAttendanceReport(
            from_date=query.from_date,
            to_date=query.to_date,
            threshold=query.threshold,
            below_only=query.below_only,
            total=0,
            items=[],
        )

    rows = (
        await session.execute(
            select(
                AttendanceSession.year_id,
                AttendanceSession.section_id,
                func.count(distinct(AttendanceRecord.student_id)),
                func.count(distinct(AttendanceSession.id)),
                func.count(AttendanceRecord.id),
                *_sum_columns(),
            )
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .where(*clauses)
            .group_by(AttendanceSession.year_id, AttendanceSession.section_id)
        )
    ).all()

    years = (
        {
            row.id: row
            for row in (
                await session.execute(
                    select(AcademicYear).where(AcademicYear.id.in_({row[0] for row in rows}))
                )
            )
            .scalars()
            .all()
        }
        if rows
        else {}
    )
    sections = (
        {
            row.id: row
            for row in (
                await session.execute(select(Section).where(Section.id.in_({row[1] for row in rows})))
            )
            .scalars()
            .all()
        }
        if rows
        else {}
    )
    levels = (
        {
            row.id: row
            for row in (
                await session.execute(
                    select(GradeLevel).where(
                        GradeLevel.id.in_({section.level_id for section in sections.values()})
                    )
                )
            )
            .scalars()
            .all()
        }
        if sections
        else {}
    )

    items: list[SectionAttendanceReportRow] = []
    for row in rows:
        year_id, section_id, student_count, session_count = row[0], row[1], int(row[2]), int(row[3])
        year = years.get(year_id)
        section = sections.get(section_id)
        level = levels.get(section.level_id) if section else None
        if year is None or section is None or level is None:
            continue
        counts = _counts(row[4:])
        rate = _rate(counts["attended"], counts["total_records"])
        items.append(
            SectionAttendanceReportRow(
                year_id=str(year_id),
                year_code=year.code,
                section_id=str(section_id),
                section_code=section.code,
                section_name=section.name,
                level_id=str(level.id),
                level_code=level.code,
                level_name=level.name,
                student_count=student_count,
                session_count=session_count,
                total_records=counts["total_records"],
                present=counts["present"],
                absent=counts["absent"],
                late=counts["late"],
                excused=counts["excused"],
                attended=counts["attended"],
                rate_percent=rate,
                below_threshold=rate < query.threshold,
            )
        )

    if query.below_only:
        items = [item for item in items if item.below_threshold]
    items.sort(key=lambda item: (item.rate_percent, item.section_code, item.year_code))
    total = len(items)
    return SectionAttendanceReport(
        from_date=query.from_date,
        to_date=query.to_date,
        threshold=query.threshold,
        below_only=query.below_only,
        total=total,
        items=items[: query.limit],
    )


__all__ = ["section_report", "student_report"]
