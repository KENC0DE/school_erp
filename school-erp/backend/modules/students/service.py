"""Student record services: registration, search, detail, update and restore."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from app.errors import Conflict, Forbidden, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.api.pagination import PageParams, contains, paginate
from core.audit.service import record
from core.auth.principal import Principal
from core.custom_fields.service import merge_custom, validate_entity_values
from core.db.soft_delete import get_including_deleted, restore, soft_delete
from core.people.models import Person, full_name, normalize_name
from core.people.service import create_person, prepare_person, update_person
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics import years as year_service
from modules.students import enrollment_service, guardian_service, medical_service
from modules.students.common import live_person, live_student, student_state
from modules.students.lookups import AcademicLabels
from modules.students.models import StudentEnrollment, StudentProfile
from modules.students.schemas import (
    STUDENT_STATUSES,
    DuplicateCheck,
    EnrollmentInput,
    GuardianOut,
    StudentList,
    StudentOut,
    StudentQuery,
    StudentRegister,
    StudentSummary,
    StudentUpdate,
)
from modules.students.views import (
    enrollment_out,
    guardian_out,
    student_out,
    student_summary,
)

MODULE = "students"
SORT_COLUMNS = {
    "created_at": StudentProfile.created_at,
    "student_number": StudentProfile.student_number,
    "status": StudentProfile.status,
}
STATUS_VALUES = set(STUDENT_STATUSES)


def _assert_status(value: str) -> None:
    if value not in STATUS_VALUES:
        raise ValidationFailed(
            "Unknown student status",
            message_key="error.students.status_invalid",
            details={"status": value},
        )


def _assert_medical_permission(principal: Principal, has_medical: bool) -> None:
    """Registration must not become a side door into medical records."""
    if has_medical and not principal.can("students.medical.manage"):
        raise Forbidden(
            "Editing medical information requires students.medical.manage",
            message_key="error.permission_denied",
            details={"permission": "students.medical.manage"},
        )


async def _assert_number_free(
    session: AsyncSession,
    student_number: str,
    *,
    current_id: uuid.UUID | None = None,
) -> None:
    stmt = select(StudentProfile.id).where(
        StudentProfile.student_number == student_number,
        StudentProfile.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(StudentProfile.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "A student with that number already exists",
            message_key="error.students.number_taken",
            details={"student_number": student_number},
        )


async def _assert_person_free(
    session: AsyncSession, person_id: uuid.UUID, *, current_id: uuid.UUID | None = None
) -> None:
    stmt = select(StudentProfile.id).where(
        StudentProfile.person_id == person_id,
        StudentProfile.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(StudentProfile.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "That person already has a student record",
            message_key="error.students.person_exists",
            details={"person_id": str(person_id)},
        )


def _enrollment_filter(query: StudentQuery) -> Any:
    sub = select(StudentEnrollment.id).where(
        StudentEnrollment.student_id == StudentProfile.id,
        StudentEnrollment.deleted_at.is_(None),
    )
    if query.year_id is not None:
        sub = sub.where(StudentEnrollment.year_id == query.year_id)
    if query.level_id is not None:
        sub = sub.where(StudentEnrollment.level_id == query.level_id)
    if query.section_id is not None:
        sub = sub.where(StudentEnrollment.section_id == query.section_id)
    return sub.exists()


async def list_students(
    session: AsyncSession,
    principal: Principal | None,
    query: StudentQuery,
) -> StudentList:
    stmt = (
        select(StudentProfile)
        .join(Person, Person.id == StudentProfile.person_id)
        .where(
            StudentProfile.deleted_at.is_(None),
            Person.deleted_at.is_(None),
        )
    )
    if query.status is not None:
        _assert_status(query.status)
        stmt = stmt.where(StudentProfile.status == query.status)
    if query.q:
        terms = normalize_name(query.q).split()
        matches = [contains(StudentProfile.student_number, query.q)]
        if terms:
            matches.append(and_(*[Person.search_name.like(f"%{term}%") for term in terms]))
        stmt = stmt.where(or_(*matches))
    if query.year_id or query.level_id or query.section_id:
        stmt = stmt.where(_enrollment_filter(query))

    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    params = PageParams(
        limit=query.limit,
        cursor=query.cursor,
        sort=query.sort,
        order=query.order,
    )
    rows, next_cursor = await paginate(
        session,
        stmt,
        params,
        sort_columns=SORT_COLUMNS,
        default_sort="created_at",
        id_column=StudentProfile.id,
    )
    student_ids = [row.id for row in rows]
    people = {
        person.id: person
        for person in (
            await session.execute(select(Person).where(Person.id.in_([row.person_id for row in rows])))
        )
        .scalars()
        .all()
    }
    enrollments: dict[uuid.UUID, list[StudentEnrollment]] = {sid: [] for sid in student_ids}
    if student_ids:
        for row in (
            await session.execute(
                select(StudentEnrollment).where(
                    StudentEnrollment.student_id.in_(student_ids),
                    StudentEnrollment.deleted_at.is_(None),
                )
            )
        ).scalars():
            enrollments.setdefault(row.student_id, []).append(row)

    years = await year_service.list_years(session)
    year_start = {item.id: item.start_date for item in years.items}
    labels = AcademicLabels(session)
    items: list[StudentSummary] = []
    for row in rows:
        person = people.get(row.person_id)
        if person is None:
            continue
        chosen = _pick_enrollment(
            enrollments.get(row.id, []),
            year_id=str(query.year_id) if query.year_id else None,
            current_year_id=years.current_year_id,
            year_start=year_start,
        )
        enrollment = await enrollment_out(chosen, labels) if chosen is not None else None
        items.append(
            student_summary(
                row,
                person,
                locale=principal.locale if principal else "en",
                enrollment=enrollment,
            )
        )
    return StudentList(items=items, next_cursor=next_cursor, total=total)


def _pick_enrollment(
    rows: list[StudentEnrollment],
    *,
    year_id: str | None,
    current_year_id: str | None,
    year_start: dict[str, date],
) -> StudentEnrollment | None:
    if not rows:
        return None
    if year_id is not None:
        return next((row for row in rows if str(row.year_id) == year_id), None)
    if current_year_id is not None:
        current = next((row for row in rows if str(row.year_id) == current_year_id), None)
        if current is not None:
            return current
    return max(rows, key=lambda row: year_start.get(str(row.year_id), date.min))


async def _guardians(session: AsyncSession, student_id: uuid.UUID, *, locale: str) -> list[GuardianOut]:
    rows = await guardian_service.list_guardians(session, student_id)
    return [guardian_out(row, person, locale=locale) for row, person in rows]


async def student_detail(
    session: AsyncSession,
    principal: Principal | None,
    profile: StudentProfile,
    *,
    include_medical: bool = False,
) -> StudentOut:
    person = await live_person(session, profile.person_id)
    labels = AcademicLabels(session)
    year_map = {item.id: item.start_date for item in (await year_service.list_years(session)).items}
    enrollment_rows = await enrollment_service.list_enrollments(session, profile.id)
    enrollment_rows.sort(
        key=lambda row: (year_map.get(str(row.year_id), date.min), str(row.id)),
        reverse=True,
    )
    enrollments = [await enrollment_out(row, labels) for row in enrollment_rows]
    guardians = await _guardians(session, profile.id, locale=principal.locale if principal else "en")
    medical = await medical_service.get_medical(session, profile.id) if include_medical else None
    return student_out(
        profile,
        person,
        locale=principal.locale if principal else "en",
        enrollments=enrollments,
        guardians=guardians,
        medical=medical,
    )


async def get_student(
    session: AsyncSession,
    principal: Principal | None,
    student_id: uuid.UUID,
    *,
    include_medical: bool = False,
) -> StudentOut:
    profile = await live_student(session, student_id)
    return await student_detail(session, principal, profile, include_medical=include_medical)


async def duplicate_warnings(session: AsyncSession, data: DuplicateCheck) -> list[dict[str, Any]]:
    _, warnings = await prepare_person(session, data.person.model_dump())
    return warnings


async def preview_registration(session: AsyncSession, data: StudentRegister) -> dict[str, Any]:
    person, warnings = await prepare_person(session, data.person.model_dump())
    return {
        "will_create": "student",
        "student_number": data.student_number,
        "full_name": full_name(person),
        "duplicate_warnings": warnings,
        "guardian_count": len(data.guardians),
        "has_enrollment": data.enrollment is not None,
        "has_medical": data.medical is not None,
    }


async def register_student(
    session: AsyncSession,
    principal: Principal,
    data: StudentRegister,
    *,
    via: str = "api",
) -> tuple[StudentProfile, list[dict[str, Any]]]:
    _assert_status(data.status or "applicant")
    _assert_medical_permission(principal, data.medical is not None)
    await _assert_number_free(session, data.student_number)
    custom = None
    if data.custom is not None:
        cleaned = await validate_entity_values(session, "student", data.custom)
        custom = merge_custom(None, cleaned)

    person, warnings = await create_person(
        session,
        principal,
        data.person.model_dump(),
        via=via,
        commit=False,
    )
    await _assert_person_free(session, person.id)
    status = data.status or ("active" if data.enrollment is not None else "applicant")
    profile = StudentProfile(
        person_id=person.id,
        student_number=data.student_number,
        status=status,
        admission_date=data.admission_date,
        notes=data.notes,
        custom=custom,
    )
    session.add(profile)
    await session.flush()

    enrollment_ids: list[str] = []
    if data.enrollment is not None:
        row = await enrollment_service.create_enrollment(
            session, principal, profile.id, data.enrollment, via=via
        )
        enrollment_ids.append(str(row.id))

    guardian_ids: list[str] = []
    for guardian in data.guardians:
        row = await guardian_service.add_guardian(session, principal, profile.id, guardian, via=via)
        guardian_ids.append(str(row.id))

    medical_id: str | None = None
    if data.medical is not None:
        row = await medical_service.upsert_medical(session, principal, profile.id, data.medical, via=via)
        medical_id = str(row.id)

    await record(
        session,
        action="students.register",
        module=MODULE,
        entity_type="student",
        entity_id=str(profile.id),
        after={
            **student_state(profile),
            "enrollment_ids": enrollment_ids,
            "guardian_ids": guardian_ids,
            "medical_id": medical_id,
        },
        actor=principal,
        via=via,
    )
    await session.commit()
    return profile, warnings


async def update_student(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    data: StudentUpdate,
    *,
    via: str = "api",
) -> StudentOut:
    profile = await live_student(session, student_id)
    before = student_state(profile)
    ensure_row_version(profile, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)

    if payload.get("person"):
        await update_person(
            session,
            principal,
            profile.person_id,
            payload.pop("person"),
            via=via,
            commit=False,
        )

    if "student_number" in payload:
        await _assert_number_free(session, payload["student_number"], current_id=profile.id)
    if "status" in payload:
        _assert_status(payload["status"])
    if "custom" in payload:
        cleaned = await validate_entity_values(session, "student", payload["custom"], partial=True)
        payload["custom"] = merge_custom(profile.custom, cleaned)

    changes: dict[str, Any] = {}
    for key in (
        "student_number",
        "status",
        "admission_date",
        "exit_date",
        "exit_reason",
        "notes",
        "custom",
    ):
        if key not in payload:
            continue
        value = payload[key]
        if getattr(profile, key) != value:
            setattr(profile, key, value)
            changes[key] = value
    if changes:
        profile.row_version = (profile.row_version or 0) + 1
    await session.flush()
    if changes:
        await record(
            session,
            action="students.update",
            module=MODULE,
            entity_type="student",
            entity_id=str(profile.id),
            before=before,
            after=student_state(profile),
            actor=principal,
            via=via,
        )
    await session.commit()
    return await student_detail(
        session,
        principal,
        profile,
        include_medical=principal.can("students.medical.view"),
    )


async def delete_student(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    *,
    row_version: int | None = None,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    profile = await live_student(session, student_id)
    if row_version is not None:
        ensure_row_version(profile, row_version, current_state=student_state(profile))
    changed = await soft_delete(
        session,
        profile,
        action="students.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="student",
    )
    await session.flush()
    await session.commit()
    return {"id": str(profile.id), "deleted": bool(changed), "row_version": profile.row_version}


async def restore_student(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> StudentOut:
    profile = await get_including_deleted(session, StudentProfile, student_id)
    if profile is None:
        raise NotFound(
            "The student does not exist",
            message_key="error.students.not_found",
        )
    await _assert_number_free(session, profile.student_number, current_id=profile.id)
    await _assert_person_free(session, profile.person_id, current_id=profile.id)
    await restore(
        session,
        profile,
        action="students.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="student",
    )
    await session.flush()
    await session.commit()
    return await student_detail(
        session,
        principal,
        profile,
        include_medical=principal.can("students.medical.view"),
    )


async def enroll_student(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    data: EnrollmentInput,
    *,
    via: str = "api",
) -> dict[str, Any]:
    row = await enrollment_service.create_enrollment(session, principal, student_id, data, via=via)
    await session.commit()
    return (await enrollment_service.enrollment_view(session, row)).model_dump(mode="json")


__all__ = [
    "delete_student",
    "duplicate_warnings",
    "enroll_student",
    "get_student",
    "list_students",
    "preview_registration",
    "register_student",
    "restore_student",
    "student_detail",
    "update_student",
]
