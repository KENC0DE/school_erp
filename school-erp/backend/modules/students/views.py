"""Response builders for student records."""

from __future__ import annotations

from core.people.models import Person
from core.people.service import person_view

from modules.students.lookups import AcademicLabels
from modules.students.models import (
    StudentEnrollment,
    StudentGuardian,
    StudentMedicalRecord,
    StudentProfile,
)
from modules.students.schemas import (
    EnrollmentOut,
    GuardianOut,
    MedicalOut,
    PersonOut,
    StudentOut,
    StudentSummary,
)


def person_out(person: Person, locale: str = "en") -> PersonOut:
    return PersonOut(**person_view(person, locale))


async def enrollment_out(row: StudentEnrollment, labels: AcademicLabels) -> EnrollmentOut:
    year = await labels.year(row.year_id)
    level = await labels.level(row.level_id)
    section = await labels.section(row.section_id) if row.section_id else None
    return EnrollmentOut(
        id=str(row.id),
        student_id=str(row.student_id),
        year_id=str(row.year_id),
        year_code=year.code if year else None,
        year_name=year.name if year else None,
        level_id=str(row.level_id),
        level_code=level.code if level else None,
        level_name=level.name if level else None,
        section_id=str(row.section_id) if row.section_id else None,
        section_code=section.code if section else None,
        roll_number=row.roll_number,
        status=row.status,
        notes=row.notes,
        row_version=row.row_version,
    )


def guardian_out(row: StudentGuardian, person: Person, locale: str = "en") -> GuardianOut:
    return GuardianOut(
        id=str(row.id),
        student_id=str(row.student_id),
        person_id=str(row.person_id),
        relationship=row.relationship,
        is_primary=row.is_primary,
        can_pickup=row.can_pickup,
        notes=row.notes,
        person=person_out(person, locale),
        row_version=row.row_version,
    )


def medical_out(row: StudentMedicalRecord) -> MedicalOut:
    return MedicalOut(
        id=str(row.id),
        student_id=str(row.student_id),
        blood_type=row.blood_type,
        allergies=row.allergies,
        chronic_conditions=row.chronic_conditions,
        medications=row.medications,
        emergency_contact_name=row.emergency_contact_name,
        emergency_contact_phone=row.emergency_contact_phone,
        notes=row.notes,
        consent_to_treat=row.consent_to_treat,
        row_version=row.row_version,
    )


def student_summary(
    profile: StudentProfile,
    person: Person,
    *,
    locale: str,
    enrollment: EnrollmentOut | None,
) -> StudentSummary:
    return StudentSummary(
        id=str(profile.id),
        student_number=profile.student_number,
        status=profile.status,
        admission_date=profile.admission_date,
        person=person_out(person, locale),
        enrollment=enrollment,
        row_version=profile.row_version,
    )


def student_out(
    profile: StudentProfile,
    person: Person,
    *,
    locale: str,
    enrollments: list[EnrollmentOut],
    guardians: list[GuardianOut],
    medical: MedicalOut | None,
) -> StudentOut:
    return StudentOut(
        **student_summary(
            profile,
            person,
            locale=locale,
            enrollment=enrollments[0] if enrollments else None,
        ).model_dump(),
        exit_date=profile.exit_date,
        exit_reason=profile.exit_reason,
        notes=profile.notes,
        custom=profile.custom or {},
        enrollments=enrollments,
        guardians=guardians,
        medical=medical,
    )


__all__ = [
    "enrollment_out",
    "guardian_out",
    "medical_out",
    "person_out",
    "student_out",
    "student_summary",
]
