"""Response builders for attendance sessions and records."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from core.auth.models import User
from core.people.models import Person, full_name
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear, GradeLevel, Section, Subject
from modules.attendance.models import AttendanceRecord, AttendanceSession
from modules.attendance.schemas import (
    RecordOut,
    RosterEntry,
    SessionCounts,
    SessionDetail,
    SessionOut,
)
from modules.students.models import StudentEnrollment, StudentProfile


@dataclass
class SessionLabels:
    years: dict[uuid.UUID, AcademicYear] = field(default_factory=dict)
    sections: dict[uuid.UUID, Section] = field(default_factory=dict)
    levels: dict[uuid.UUID, GradeLevel] = field(default_factory=dict)
    subjects: dict[uuid.UUID, Subject] = field(default_factory=dict)
    users: dict[uuid.UUID, str] = field(default_factory=dict)


async def load_labels(session: AsyncSession, rows: list[AttendanceSession]) -> SessionLabels:
    labels = SessionLabels()
    if not rows:
        return labels
    year_ids = {row.year_id for row in rows}
    section_ids = {row.section_id for row in rows}
    subject_ids = {row.subject_id for row in rows if row.subject_id is not None}
    user_ids = {row.status_changed_by for row in rows if row.status_changed_by is not None}

    labels.years = {
        row.id: row
        for row in (await session.execute(select(AcademicYear).where(AcademicYear.id.in_(year_ids))))
        .scalars()
        .all()
    }
    labels.sections = {
        row.id: row
        for row in (await session.execute(select(Section).where(Section.id.in_(section_ids)))).scalars().all()
    }
    level_ids = {row.level_id for row in labels.sections.values()}
    if level_ids:
        labels.levels = {
            row.id: row
            for row in (await session.execute(select(GradeLevel).where(GradeLevel.id.in_(level_ids))))
            .scalars()
            .all()
        }
    if subject_ids:
        labels.subjects = {
            row.id: row
            for row in (await session.execute(select(Subject).where(Subject.id.in_(subject_ids))))
            .scalars()
            .all()
        }
    if user_ids:
        labels.users = {
            row.id: row.display_name
            for row in (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        }
    return labels


def counts_for(records: list[AttendanceRecord]) -> SessionCounts:
    counts = SessionCounts(total=len(records))
    for row in records:
        if row.status == "present":
            counts.present += 1
        elif row.status == "absent":
            counts.absent += 1
        elif row.status == "late":
            counts.late += 1
        elif row.status == "excused":
            counts.excused += 1
    return counts


def session_out(row: AttendanceSession, labels: SessionLabels, counts: SessionCounts) -> SessionOut:
    year = labels.years[row.year_id]
    section = labels.sections[row.section_id]
    level = labels.levels[section.level_id]
    subject = labels.subjects.get(row.subject_id) if row.subject_id else None
    return SessionOut(
        id=str(row.id),
        year_id=str(year.id),
        year_code=year.code,
        section_id=str(section.id),
        section_code=section.code,
        section_name=section.name,
        level_id=str(level.id),
        level_code=level.code,
        level_name=level.name,
        date=row.date,
        mode=row.mode,  # type: ignore[arg-type]
        period=row.period,
        subject_id=str(subject.id) if subject else None,
        subject_code=subject.code if subject else None,
        subject_name=subject.name if subject else None,
        status=row.status,  # type: ignore[arg-type]
        notes=row.notes,
        counts=counts,
        status_changed_at=row.status_changed_at,
        status_changed_by=str(row.status_changed_by) if row.status_changed_by else None,
        status_changed_by_name=labels.users.get(row.status_changed_by) if row.status_changed_by else None,
        row_version=row.row_version,
    )


@dataclass
class StudentLabels:
    profiles: dict[uuid.UUID, StudentProfile] = field(default_factory=dict)
    people: dict[uuid.UUID, Person] = field(default_factory=dict)
    enrollments: dict[uuid.UUID, StudentEnrollment] = field(default_factory=dict)

    def name(self, student_id: uuid.UUID, locale: str = "en") -> str:
        person = self.people[self.profiles[student_id].person_id]
        return full_name(person, locale)


async def load_students(session: AsyncSession, student_ids: set[uuid.UUID]) -> StudentLabels:
    labels = StudentLabels()
    if not student_ids:
        return labels
    labels.profiles = {
        row.id: row
        for row in (await session.execute(select(StudentProfile).where(StudentProfile.id.in_(student_ids))))
        .scalars()
        .all()
    }
    person_ids = {row.person_id for row in labels.profiles.values()}
    labels.people = {
        row.id: row
        for row in (await session.execute(select(Person).where(Person.id.in_(person_ids)))).scalars().all()
    }
    return labels


async def load_enrollments(
    session: AsyncSession,
    year_id: uuid.UUID,
    section_id: uuid.UUID,
    student_ids: set[uuid.UUID],
) -> dict[uuid.UUID, StudentEnrollment]:
    if not student_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(StudentEnrollment).where(
                    StudentEnrollment.deleted_at.is_(None),
                    StudentEnrollment.year_id == year_id,
                    StudentEnrollment.section_id == section_id,
                    StudentEnrollment.student_id.in_(student_ids),
                    StudentEnrollment.status == "active",
                )
            )
        )
        .scalars()
        .all()
    )
    return {row.student_id: row for row in rows}


def record_out(
    row: AttendanceRecord,
    students: StudentLabels,
    enrollments: dict[uuid.UUID, StudentEnrollment],
    users: dict[uuid.UUID, str],
) -> RecordOut:
    enrollment = enrollments.get(row.student_id)
    return RecordOut(
        id=str(row.id),
        session_id=str(row.session_id),
        student_id=str(row.student_id),
        student_number=students.profiles[row.student_id].student_number,
        student_name=students.name(row.student_id, "en"),
        student_name_am=students.name(row.student_id, "am") or None,
        roll_number=enrollment.roll_number if enrollment else None,
        status=row.status,  # type: ignore[arg-type]
        reason=row.reason,
        late_minutes=row.late_minutes,
        note=row.note,
        recorded_at=row.recorded_at,
        recorded_by=str(row.recorded_by) if row.recorded_by else None,
        recorded_by_name=users.get(row.recorded_by) if row.recorded_by else None,
        row_version=row.row_version,
    )


def detail_out(
    row: AttendanceSession,
    labels: SessionLabels,
    records: list[AttendanceRecord],
    roster: list[tuple[StudentProfile, Person, StudentEnrollment]],
    users: dict[uuid.UUID, str],
) -> SessionDetail:
    students = StudentLabels()
    for profile, person, enrollment in roster:
        students.profiles[profile.id] = profile
        students.people[person.id] = person
        students.enrollments[profile.id] = enrollment
    by_student = {record.student_id: record for record in records}
    entries = [record_out(record, students, students.enrollments, users) for record in records]
    return SessionDetail(
        **session_out(row, labels, counts_for(records)).model_dump(),
        records=entries,
        roster=[
            RosterEntry(
                student_id=str(profile.id),
                student_number=profile.student_number,
                full_name=full_name(person, "en"),
                roll_number=enrollment.roll_number,
                status=by_student[profile.id].status if profile.id in by_student else None,
                record_id=str(by_student[profile.id].id) if profile.id in by_student else None,
            )
            for profile, person, enrollment in roster
        ],
    )


__all__ = [
    "SessionLabels",
    "StudentLabels",
    "counts_for",
    "detail_out",
    "load_enrollments",
    "load_labels",
    "load_students",
    "record_out",
    "session_out",
]
