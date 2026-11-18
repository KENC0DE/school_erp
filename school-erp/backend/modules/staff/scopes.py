"""Data scope resolvers for the staff module.

The resolvers turn a user account into the rows a scoped permission applies to:
the sections a teacher teaches (``assigned_subjects``), the section they own as
homeroom teacher (``own_class``), and the staff in their department
(``department``). They return UUID sets; ``None`` means unrestricted.
"""

from __future__ import annotations

import uuid

from core.auth.principal import Principal
from core.rbac.scopes import (
    ALL,
    ASSIGNED_SUBJECTS,
    DEPARTMENT,
    OWN_CLASS,
    effective_scopes,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import Section
from modules.staff.models import StaffProfile, StaffTeachingAssignment


async def staff_for_user(session: AsyncSession, user_id: uuid.UUID) -> StaffProfile | None:
    return (
        await session.execute(
            select(StaffProfile).where(
                StaffProfile.user_id == user_id,
                StaffProfile.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def assigned_pairs(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    year_id: uuid.UUID | None = None,
) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """Return (section, subject) pairs the user teaches."""
    staff = await staff_for_user(session, user_id)
    if staff is None:
        return set()
    stmt = select(
        StaffTeachingAssignment.section_id,
        StaffTeachingAssignment.subject_id,
    ).where(
        StaffTeachingAssignment.staff_id == staff.id,
        StaffTeachingAssignment.deleted_at.is_(None),
    )
    if year_id is not None:
        stmt = stmt.where(StaffTeachingAssignment.year_id == year_id)
    return {(section_id, subject_id) for section_id, subject_id in (await session.execute(stmt)).all()}


async def assigned_section_ids(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    year_id: uuid.UUID | None = None,
) -> set[uuid.UUID]:
    return {section_id for section_id, _subject_id in await assigned_pairs(session, user_id, year_id=year_id)}


async def assigned_subject_ids(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    year_id: uuid.UUID | None = None,
) -> set[uuid.UUID]:
    return {subject_id for _section_id, subject_id in await assigned_pairs(session, user_id, year_id=year_id)}


async def own_class_section_ids(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    year_id: uuid.UUID | None = None,
) -> set[uuid.UUID]:
    stmt = select(Section.id).where(
        Section.homeroom_user_id == user_id,
        Section.deleted_at.is_(None),
        Section.is_active.is_(True),
    )
    if year_id is not None:
        stmt = stmt.where(Section.year_id == year_id)
    return set((await session.execute(stmt)).scalars().all())


async def department_id_for_user(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID | None:
    staff = await staff_for_user(session, user_id)
    return staff.department_id if staff is not None else None


async def department_staff_ids(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> set[uuid.UUID]:
    department_id = await department_id_for_user(session, user_id)
    if department_id is None:
        return set()
    return set(
        (
            await session.execute(
                select(StaffProfile.id).where(
                    StaffProfile.department_id == department_id,
                    StaffProfile.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )


async def visible_staff_ids(
    session: AsyncSession,
    principal: Principal,
    permission: str = "staff.view",
) -> set[uuid.UUID] | None:
    """The staff rows a caller may read, or ``None`` for every row."""
    scopes = effective_scopes(principal, permission)
    if scopes is None or ALL in scopes:
        return None
    allowed: set[uuid.UUID] = set()
    if DEPARTMENT in scopes:
        allowed |= await department_staff_ids(session, uuid.UUID(principal.user_id))
    return allowed


async def visible_student_section_ids(
    session: AsyncSession,
    principal: Principal,
    permission: str = "students.view",
) -> set[uuid.UUID] | None:
    """The sections a scoped student reader may see, or ``None`` for all."""
    scopes = effective_scopes(principal, permission)
    if scopes is None or ALL in scopes:
        return None
    allowed: set[uuid.UUID] = set()
    user_id = uuid.UUID(principal.user_id)
    if ASSIGNED_SUBJECTS in scopes:
        allowed |= await assigned_section_ids(session, user_id)
    if OWN_CLASS in scopes:
        allowed |= await own_class_section_ids(session, user_id)
    # ``department`` is a staff-record scope; it does not widen student access.
    return allowed


__all__ = [
    "assigned_pairs",
    "assigned_section_ids",
    "assigned_subject_ids",
    "department_id_for_user",
    "department_staff_ids",
    "own_class_section_ids",
    "staff_for_user",
    "visible_staff_ids",
    "visible_student_section_ids",
]
