"""Shared lookups and audit snapshots for student records."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import NotFound
from core.people.models import Person
from core.people.service import person_view
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.students.models import (
    StudentEnrollment,
    StudentGuardian,
    StudentMedicalRecord,
    StudentProfile,
)


async def live_student(session: AsyncSession, student_id: uuid.UUID) -> StudentProfile:
    student = (
        await session.execute(
            select(StudentProfile).where(
                StudentProfile.id == student_id,
                StudentProfile.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if student is None:
        raise NotFound(
            "The student does not exist",
            message_key="error.students.not_found",
        )
    return student


async def live_person(session: AsyncSession, person_id: uuid.UUID) -> Person:
    person = (
        await session.execute(select(Person).where(Person.id == person_id, Person.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if person is None:
        raise NotFound(
            "The person does not exist",
            message_key="error.students.person_not_found",
        )
    return person


def student_state(profile: StudentProfile) -> dict[str, Any]:
    return {
        "person_id": str(profile.person_id),
        "student_number": profile.student_number,
        "status": profile.status,
        "admission_date": profile.admission_date.isoformat() if profile.admission_date else None,
        "exit_date": profile.exit_date.isoformat() if profile.exit_date else None,
        "exit_reason": profile.exit_reason,
        "notes": profile.notes,
        "custom": profile.custom or {},
        "row_version": profile.row_version,
        "deleted": profile.deleted_at is not None,
    }


def person_state(person: Person) -> dict[str, Any]:
    return person_view(person)


def enrollment_state(row: StudentEnrollment) -> dict[str, Any]:
    return {
        "student_id": str(row.student_id),
        "year_id": str(row.year_id),
        "level_id": str(row.level_id),
        "section_id": str(row.section_id) if row.section_id else None,
        "roll_number": row.roll_number,
        "status": row.status,
        "notes": row.notes,
        "row_version": row.row_version,
    }


def guardian_state(row: StudentGuardian) -> dict[str, Any]:
    return {
        "student_id": str(row.student_id),
        "person_id": str(row.person_id),
        "relationship": row.relationship,
        "is_primary": row.is_primary,
        "can_pickup": row.can_pickup,
        "notes": row.notes,
        "row_version": row.row_version,
    }


def medical_state(row: StudentMedicalRecord) -> dict[str, Any]:
    return {
        "student_id": str(row.student_id),
        "blood_type": row.blood_type,
        "allergies": row.allergies,
        "chronic_conditions": row.chronic_conditions,
        "medications": row.medications,
        "emergency_contact_name": row.emergency_contact_name,
        "emergency_contact_phone": row.emergency_contact_phone,
        "notes": row.notes,
        "consent_to_treat": row.consent_to_treat,
        "row_version": row.row_version,
    }


__all__ = [
    "enrollment_state",
    "guardian_state",
    "live_person",
    "live_student",
    "medical_state",
    "person_state",
    "student_state",
]
