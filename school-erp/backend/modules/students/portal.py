"""The students behind a portal account (P4-16).

A student account links straight from ``student_profiles.user_id``. A parent
account links from every ``student_guardians`` row it owns, which is what makes
the multi-child portal work without a second family table. Both lookups are
live-row only and return the profile with its person so callers can render a
name without another query per child.
"""

from __future__ import annotations

import uuid

from core.people.models import Person
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.students.models import StudentGuardian, StudentProfile


async def portal_student_ids(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Every live student the account may see, in student-number order."""
    direct = select(StudentProfile.id).where(
        StudentProfile.user_id == user_id,
        StudentProfile.deleted_at.is_(None),
    )
    guarded = select(StudentGuardian.student_id).where(
        StudentGuardian.user_id == user_id,
        StudentGuardian.deleted_at.is_(None),
    )
    ids = set((await session.execute(direct)).scalars().all())
    ids |= set((await session.execute(guarded)).scalars().all())
    if not ids:
        return []
    ordered = (
        (
            await session.execute(
                select(StudentProfile.id)
                .where(
                    StudentProfile.id.in_(ids),
                    StudentProfile.deleted_at.is_(None),
                )
                .order_by(StudentProfile.student_number)
            )
        )
        .scalars()
        .all()
    )
    return list(ordered)


async def portal_students(session: AsyncSession, user_id: uuid.UUID) -> list[tuple[StudentProfile, Person]]:
    """The linked student profiles with their person rows."""
    ids = await portal_student_ids(session, user_id)
    if not ids:
        return []
    rows = (
        await session.execute(
            select(StudentProfile, Person)
            .join(Person, Person.id == StudentProfile.person_id)
            .where(
                StudentProfile.id.in_(ids),
                StudentProfile.deleted_at.is_(None),
                Person.deleted_at.is_(None),
            )
            .order_by(StudentProfile.student_number)
        )
    ).all()
    return [(profile, person) for profile, person in rows]


__all__ = ["portal_student_ids", "portal_students"]
