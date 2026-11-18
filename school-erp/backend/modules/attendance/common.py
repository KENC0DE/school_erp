"""Shared lookups, settings and audit snapshots for the attendance module."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from app.errors import NotFound
from core.people.models import Person, full_name
from core.settings.service import load_model
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear, Section, Subject
from modules.attendance.models import AttendanceRecord, AttendanceSession
from modules.attendance.settings import AttendanceSettings
from modules.students.models import StudentEnrollment, StudentProfile

MODULE = "attendance"


def utcnow() -> datetime:
    return datetime.now(UTC)


async def attendance_settings(session: AsyncSession) -> AttendanceSettings:
    return await load_model(session, MODULE, AttendanceSettings)


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
        raise NotFound("The academic year does not exist", message_key="attendance.error.year_not_found")
    return row


async def live_section(session: AsyncSession, section_id: uuid.UUID) -> Section:
    row = (
        await session.execute(
            select(Section).where(
                Section.id == section_id,
                Section.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The section does not exist",
            message_key="attendance.error.section_not_found",
        )
    return row


async def live_subject(session: AsyncSession, subject_id: uuid.UUID) -> Subject:
    row = (
        await session.execute(
            select(Subject).where(
                Subject.id == subject_id,
                Subject.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The subject does not exist",
            message_key="attendance.error.subject_not_found",
        )
    return row


async def live_session(session: AsyncSession, session_id: uuid.UUID) -> AttendanceSession:
    row = (
        await session.execute(
            select(AttendanceSession).where(
                AttendanceSession.id == session_id,
                AttendanceSession.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The attendance register does not exist",
            message_key="attendance.error.session_not_found",
        )
    return row


async def live_record(
    session: AsyncSession,
    session_id: uuid.UUID,
    record_id: uuid.UUID,
) -> AttendanceRecord:
    row = (
        await session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.id == record_id,
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The attendance entry does not exist",
            message_key="attendance.error.record_not_found",
        )
    return row


async def enrolled_students(
    session: AsyncSession,
    year_id: uuid.UUID,
    section_id: uuid.UUID,
) -> list[tuple[StudentProfile, Person, StudentEnrollment]]:
    """Live students actively enrolled in one section for the year."""
    rows = (
        await session.execute(
            select(StudentProfile, Person, StudentEnrollment)
            .join(Person, Person.id == StudentProfile.person_id)
            .join(StudentEnrollment, StudentEnrollment.student_id == StudentProfile.id)
            .where(
                StudentProfile.deleted_at.is_(None),
                Person.deleted_at.is_(None),
                StudentEnrollment.deleted_at.is_(None),
                StudentEnrollment.year_id == year_id,
                StudentEnrollment.section_id == section_id,
                StudentEnrollment.status == "active",
            )
        )
    ).all()
    rows.sort(key=lambda row: (row[2].roll_number or "", row[0].student_number))
    return [(profile, person, enrollment) for profile, person, enrollment in rows]


def student_name_am(person: Person) -> str | None:
    value = full_name(person, "am")
    return value or None


def session_state(row: AttendanceSession) -> dict[str, Any]:
    return {
        "year_id": str(row.year_id),
        "section_id": str(row.section_id),
        "date": row.date.isoformat(),
        "mode": row.mode,
        "period": row.period,
        "subject_id": str(row.subject_id) if row.subject_id else None,
        "status": row.status,
        "notes": row.notes,
        "row_version": row.row_version,
        "deleted": row.deleted_at is not None,
    }


def record_state(row: AttendanceRecord) -> dict[str, Any]:
    return {
        "session_id": str(row.session_id),
        "student_id": str(row.student_id),
        "status": row.status,
        "reason": row.reason,
        "late_minutes": row.late_minutes,
        "note": row.note,
        "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
        "row_version": row.row_version,
    }


def is_future(value: date) -> bool:
    return value > datetime.now(UTC).date()


__all__ = [
    "MODULE",
    "attendance_settings",
    "enrolled_students",
    "is_future",
    "live_record",
    "live_section",
    "live_session",
    "live_subject",
    "live_year",
    "record_state",
    "session_state",
    "student_name_am",
    "utcnow",
]
