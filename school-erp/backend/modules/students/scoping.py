"""Student data scopes: keep a scoped reader inside their own sections.

``students.view`` may be granted with ``assigned_subjects`` and/or ``own_class``
scopes. The actual section set comes from the staff module's teaching
assignments and homeroom column; this module only applies it to student rows.
"""

from __future__ import annotations

import uuid

from app.errors import Forbidden
from core.auth.deps import get_current_principal
from core.auth.principal import Principal
from core.db.deps import get_session
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.staff import scopes as staff_scopes
from modules.students.models import StudentEnrollment


async def visible_section_ids(
    session: AsyncSession,
    principal: Principal,
) -> set[uuid.UUID] | None:
    return await staff_scopes.visible_student_section_ids(session, principal)


async def student_is_visible(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
) -> bool:
    allowed = await visible_section_ids(session, principal)
    if allowed is None:
        return True
    if not allowed:
        return False
    exists = (
        await session.execute(
            select(StudentEnrollment.id).where(
                StudentEnrollment.student_id == student_id,
                StudentEnrollment.deleted_at.is_(None),
                StudentEnrollment.section_id.in_(allowed),
            )
        )
    ).first()
    return exists is not None


async def assert_student_visible(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
) -> None:
    if not await student_is_visible(session, principal, student_id):
        raise Forbidden(
            "This student is outside your assigned sections",
            message_key="error.scope_denied",
            details={"student_id": str(student_id)},
        )


async def student_scope_guard(
    request: Request,
    student_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Principal:
    """Route dependency for every ``/students/{student_id}`` read."""
    await assert_student_visible(session, principal, student_id)
    return principal


__all__ = [
    "assert_student_visible",
    "student_is_visible",
    "student_scope_guard",
    "visible_section_ids",
]
