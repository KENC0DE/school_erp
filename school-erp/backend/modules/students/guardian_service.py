"""Guardian links for a student (many-to-many, ARCH §9.2)."""

from __future__ import annotations

import uuid

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import get_including_deleted, restore, soft_delete
from core.people.models import Person
from core.people.service import create_person
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.students.common import guardian_state, live_person, live_student
from modules.students.models import StudentGuardian
from modules.students.schemas import GuardianInput, GuardianOut, GuardianUpdate
from modules.students.views import guardian_out

MODULE = "students"


async def _live_guardian(
    session: AsyncSession, student_id: uuid.UUID, guardian_id: uuid.UUID
) -> StudentGuardian:
    row = (
        await session.execute(
            select(StudentGuardian).where(
                StudentGuardian.id == guardian_id,
                StudentGuardian.student_id == student_id,
                StudentGuardian.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The guardian link does not exist",
            message_key="students.error.guardian_not_found",
        )
    return row


async def _assert_person_free(
    session: AsyncSession,
    student_id: uuid.UUID,
    person_id: uuid.UUID,
    *,
    current_id: uuid.UUID | None = None,
) -> None:
    stmt = select(StudentGuardian.id).where(
        StudentGuardian.student_id == student_id,
        StudentGuardian.person_id == person_id,
        StudentGuardian.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(StudentGuardian.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "That person is already a guardian of this student",
            message_key="students.error.guardian_exists",
            details={"person_id": str(person_id)},
        )


async def _assert_not_student(session: AsyncSession, student_id: uuid.UUID, person_id: uuid.UUID) -> None:
    student = await live_student(session, student_id)
    if student.person_id == person_id:
        raise ValidationFailed(
            "A student cannot be their own guardian",
            message_key="students.error.guardian_is_student",
        )


async def _clear_primary(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    keep_id: uuid.UUID,
    *,
    via: str,
) -> None:
    rows = (
        (
            await session.execute(
                select(StudentGuardian).where(
                    StudentGuardian.student_id == student_id,
                    StudentGuardian.is_primary.is_(True),
                    StudentGuardian.id != keep_id,
                    StudentGuardian.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        before = guardian_state(row)
        row.is_primary = False
        row.row_version = (row.row_version or 0) + 1
        await session.flush()
        await record(
            session,
            action="students.guardians.update",
            module=MODULE,
            entity_type="student_guardian",
            entity_id=str(row.id),
            before=before,
            after=guardian_state(row),
            actor=principal,
            via=via,
        )


async def list_guardians(
    session: AsyncSession, student_id: uuid.UUID
) -> list[tuple[StudentGuardian, Person]]:
    rows = (
        await session.execute(
            select(StudentGuardian, Person)
            .join(Person, Person.id == StudentGuardian.person_id)
            .where(
                StudentGuardian.student_id == student_id,
                StudentGuardian.deleted_at.is_(None),
                Person.deleted_at.is_(None),
            )
            .order_by(StudentGuardian.is_primary.desc(), StudentGuardian.created_at, StudentGuardian.id)
        )
    ).all()
    return [(row[0], row[1]) for row in rows]


async def guardian_view(session: AsyncSession, row: StudentGuardian, *, locale: str = "en") -> GuardianOut:
    person = await live_person(session, row.person_id)
    return guardian_out(row, person, locale)


async def add_guardian(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    data: GuardianInput,
    *,
    via: str = "api",
) -> StudentGuardian:
    await live_student(session, student_id)
    if data.person_id is not None:
        person = await live_person(session, data.person_id)
    else:
        person, _ = await create_person(
            session,
            principal,
            data.person.model_dump() if data.person else {},
            via=via,
            commit=False,
        )
    await _assert_not_student(session, student_id, person.id)
    await _assert_person_free(session, student_id, person.id)
    row = StudentGuardian(
        student_id=student_id,
        person_id=person.id,
        relationship=data.relationship,
        is_primary=data.is_primary,
        can_pickup=data.can_pickup,
        notes=data.notes,
    )
    session.add(row)
    await session.flush()
    if data.is_primary:
        await _clear_primary(session, principal, student_id, row.id, via=via)
    await record(
        session,
        action="students.guardians.add",
        module=MODULE,
        entity_type="student_guardian",
        entity_id=str(row.id),
        after={**guardian_state(row), "person": str(person.id)},
        actor=principal,
        via=via,
    )
    return row


async def update_guardian(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    data: GuardianUpdate,
    *,
    via: str = "api",
) -> StudentGuardian:
    row = await _live_guardian(session, student_id, guardian_id)
    before = guardian_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    changes = False
    for key in ("relationship", "is_primary", "can_pickup", "notes"):
        if key not in payload:
            continue
        value = payload[key]
        if getattr(row, key) != value:
            setattr(row, key, value)
            changes = True
    if changes:
        row.row_version = (row.row_version or 0) + 1
    await session.flush()
    if row.is_primary:
        await _clear_primary(session, principal, student_id, row.id, via=via)
    if changes:
        await record(
            session,
            action="students.guardians.update",
            module=MODULE,
            entity_type="student_guardian",
            entity_id=str(row.id),
            before=before,
            after=guardian_state(row),
            actor=principal,
            via=via,
        )
    return row


async def remove_guardian(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    *,
    row_version: int | None = None,
    reason: str | None = None,
    via: str = "api",
) -> StudentGuardian:
    row = await _live_guardian(session, student_id, guardian_id)
    if row_version is not None:
        ensure_row_version(row, row_version, current_state=guardian_state(row))
    await soft_delete(
        session,
        row,
        action="students.guardians.remove",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="student_guardian",
    )
    await session.flush()
    return row


async def restore_guardian(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> StudentGuardian:
    row = await get_including_deleted(session, StudentGuardian, guardian_id)
    if row is None or row.student_id != student_id:
        raise NotFound(
            "The guardian link does not exist",
            message_key="students.error.guardian_not_found",
        )
    await _assert_person_free(session, student_id, row.person_id, current_id=row.id)
    await restore(
        session,
        row,
        action="students.guardians.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="student_guardian",
    )
    await session.flush()
    return row


__all__ = [
    "add_guardian",
    "guardian_view",
    "list_guardians",
    "remove_guardian",
    "restore_guardian",
    "update_guardian",
]
