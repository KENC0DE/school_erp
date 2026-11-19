"""Student medical record with dedicated view/manage permissions (ARCH §9.2)."""

from __future__ import annotations

import uuid

from core.audit.service import record
from core.auth.principal import Principal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.students.common import live_student, medical_state
from modules.students.models import StudentMedicalRecord
from modules.students.schemas import MedicalInput, MedicalOut
from modules.students.views import medical_out

MODULE = "students"


async def get_record(session: AsyncSession, student_id: uuid.UUID) -> StudentMedicalRecord | None:
    await live_student(session, student_id)
    return (
        await session.execute(
            select(StudentMedicalRecord).where(
                StudentMedicalRecord.student_id == student_id,
                StudentMedicalRecord.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def get_medical(session: AsyncSession, student_id: uuid.UUID) -> MedicalOut | None:
    row = await get_record(session, student_id)
    return medical_out(row) if row is not None else None


async def upsert_medical(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    data: MedicalInput,
    *,
    via: str = "api",
) -> StudentMedicalRecord:
    await live_student(session, student_id)
    row = (
        await session.execute(
            select(StudentMedicalRecord).where(
                StudentMedicalRecord.student_id == student_id,
                StudentMedicalRecord.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    payload = data.model_dump()
    if row is None:
        row = StudentMedicalRecord(student_id=student_id, **payload)
        session.add(row)
        await session.flush()
        await record(
            session,
            action="students.medical.create",
            module=MODULE,
            entity_type="student_medical_record",
            entity_id=str(row.id),
            after=medical_state(row),
            actor=principal,
            via=via,
        )
        return row

    before = medical_state(row)
    changed = False
    for key, value in payload.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed = True
    if changed:
        row.row_version = (row.row_version or 0) + 1
    await session.flush()
    if changed:
        await record(
            session,
            action="students.medical.update",
            module=MODULE,
            entity_type="student_medical_record",
            entity_id=str(row.id),
            before=before,
            after=medical_state(row),
            actor=principal,
            via=via,
        )
    return row


__all__ = ["get_medical", "get_record", "upsert_medical"]
