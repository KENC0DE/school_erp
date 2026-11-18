"""Enrollment CRUD for a student (ARCH §9.2)."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import get_including_deleted, restore, soft_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics import section_service
from modules.academics import service as catalog
from modules.academics import years as year_service
from modules.students.common import enrollment_state, live_student
from modules.students.lookups import AcademicLabels
from modules.students.models import StudentEnrollment
from modules.students.schemas import EnrollmentInput, EnrollmentOut, EnrollmentUpdate
from modules.students.views import enrollment_out

MODULE = "students"


async def _validate_placement(
    session: AsyncSession,
    year_id: uuid.UUID,
    level_id: uuid.UUID,
    section_id: uuid.UUID | None,
) -> None:
    year = await year_service.get_year(session, year_id)
    if year.status == "closed":
        raise Conflict(
            "A closed academic year cannot receive new enrollments",
            message_key="students.error.year_closed",
            details={"year_id": str(year_id)},
        )
    level = await catalog.get_level(session, level_id)
    if not level.is_active:
        raise ValidationFailed(
            "An inactive grade level cannot receive enrollments",
            message_key="students.error.level_inactive",
            details={"level_id": str(level_id)},
        )
    if section_id is None:
        return
    section = await section_service.get_section(session, section_id)
    if section.year_id != str(year_id) or section.level_id != str(level_id):
        raise ValidationFailed(
            "The section does not belong to that academic year and level",
            message_key="students.error.section_mismatch",
            details={"section_id": str(section_id)},
        )
    if not section.is_active:
        raise ValidationFailed(
            "An inactive section cannot receive enrollments",
            message_key="students.error.section_inactive",
            details={"section_id": str(section_id)},
        )


async def _live_enrollment(
    session: AsyncSession, student_id: uuid.UUID, enrollment_id: uuid.UUID
) -> StudentEnrollment:
    row = (
        await session.execute(
            select(StudentEnrollment).where(
                StudentEnrollment.id == enrollment_id,
                StudentEnrollment.student_id == student_id,
                StudentEnrollment.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The enrollment does not exist",
            message_key="students.error.enrollment_not_found",
        )
    return row


async def _assert_year_free(
    session: AsyncSession,
    student_id: uuid.UUID,
    year_id: uuid.UUID,
    *,
    current_id: uuid.UUID | None = None,
) -> None:
    stmt = select(StudentEnrollment.id).where(
        StudentEnrollment.student_id == student_id,
        StudentEnrollment.year_id == year_id,
        StudentEnrollment.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(StudentEnrollment.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "This student is already enrolled for that academic year",
            message_key="students.error.enrollment_exists",
            details={"year_id": str(year_id)},
        )


async def list_enrollments(
    session: AsyncSession,
    student_id: uuid.UUID,
    *,
    include_inactive: bool = False,
) -> list[StudentEnrollment]:
    await live_student(session, student_id)
    stmt = select(StudentEnrollment).where(StudentEnrollment.student_id == student_id)
    if not include_inactive:
        stmt = stmt.where(StudentEnrollment.deleted_at.is_(None))
    return list(
        (await session.execute(stmt.order_by(StudentEnrollment.created_at.desc(), StudentEnrollment.id)))
        .scalars()
        .all()
    )


async def create_enrollment(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    data: EnrollmentInput,
    *,
    via: str = "api",
) -> StudentEnrollment:
    await live_student(session, student_id)
    await _validate_placement(session, data.year_id, data.level_id, data.section_id)
    await _assert_year_free(session, student_id, data.year_id)
    row = StudentEnrollment(
        student_id=student_id,
        year_id=data.year_id,
        level_id=data.level_id,
        section_id=data.section_id,
        roll_number=data.roll_number,
        status=data.status,
        notes=data.notes,
    )
    session.add(row)
    await session.flush()
    await record(
        session,
        action="students.enrollments.create",
        module=MODULE,
        entity_type="student_enrollment",
        entity_id=str(row.id),
        after=enrollment_state(row),
        actor=principal,
        via=via,
    )
    return row


async def update_enrollment(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    data: EnrollmentUpdate,
    *,
    via: str = "api",
) -> StudentEnrollment:
    row = await _live_enrollment(session, student_id, enrollment_id)
    before = enrollment_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)

    year_id = payload.get("year_id", row.year_id)
    level_id = payload.get("level_id", row.level_id)
    section_id = payload.get("section_id", row.section_id)
    if payload.get("section_id") is None and ("year_id" in payload or "level_id" in payload):
        section_id = None
    if (year_id, level_id, section_id) != (row.year_id, row.level_id, row.section_id):
        await _validate_placement(session, year_id, level_id, section_id)
    if year_id != row.year_id:
        await _assert_year_free(session, student_id, year_id, current_id=row.id)

    changes: dict[str, Any] = {}
    for key in ("year_id", "level_id", "section_id", "roll_number", "status", "notes"):
        if key not in payload:
            continue
        value = payload[key]
        if key == "section_id" and ("year_id" in payload or "level_id" in payload):
            value = section_id
        if getattr(row, key) != value:
            setattr(row, key, value)
            changes[key] = value
    if changes:
        row.row_version = (row.row_version or 0) + 1
    await session.flush()
    if changes:
        await record(
            session,
            action="students.enrollments.update",
            module=MODULE,
            entity_type="student_enrollment",
            entity_id=str(row.id),
            before=before,
            after=enrollment_state(row),
            actor=principal,
            via=via,
        )
    return row


async def delete_enrollment(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    *,
    row_version: int | None = None,
    reason: str | None = None,
    via: str = "api",
) -> StudentEnrollment:
    row = await _live_enrollment(session, student_id, enrollment_id)
    if row_version is not None:
        ensure_row_version(row, row_version, current_state=enrollment_state(row))
    await soft_delete(
        session,
        row,
        action="students.enrollments.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="student_enrollment",
    )
    await session.flush()
    return row


async def restore_enrollment(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> StudentEnrollment:
    row = await get_including_deleted(session, StudentEnrollment, enrollment_id)
    if row is None or row.student_id != student_id:
        raise NotFound(
            "The enrollment does not exist",
            message_key="students.error.enrollment_not_found",
        )
    await _assert_year_free(session, student_id, row.year_id, current_id=row.id)
    await restore(
        session,
        row,
        action="students.enrollments.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="student_enrollment",
    )
    await session.flush()
    return row


async def enrollment_view(
    session: AsyncSession, row: StudentEnrollment, *, labels: AcademicLabels | None = None
) -> EnrollmentOut:
    labels = labels or AcademicLabels(session)
    return await enrollment_out(row, labels)


__all__ = [
    "create_enrollment",
    "delete_enrollment",
    "enrollment_view",
    "list_enrollments",
    "restore_enrollment",
    "update_enrollment",
]
