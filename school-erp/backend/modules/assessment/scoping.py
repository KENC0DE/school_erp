"""Data scope for marks: which section and subject pairs a caller may touch.

``assigned_subjects`` resolves to the pairs a teacher teaches, ``own_class`` to
the section they own as homeroom teacher (any subject), and ``department`` to
the pairs taught by the staff in the caller's department, so a department head
can review their teachers' marks. The router keeps the permission check; this
module narrows the rows and builds the SQL condition for list endpoints.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.errors import Forbidden
from core.auth.principal import Principal
from core.rbac.scopes import (
    ALL,
    ASSIGNED_SUBJECTS,
    DEPARTMENT,
    OWN_CLASS,
    effective_scopes,
)
from sqlalchemy import ColumnElement, and_, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.assessment.models import Assessment
from modules.staff import scopes as staff_scopes
from modules.staff.models import StaffTeachingAssignment

Pair = tuple[uuid.UUID, uuid.UUID]


@dataclass(frozen=True)
class MarkAccess:
    """The marks a scoped caller may reach.

    ``pairs`` names exact (section, subject) teaching assignments; ``sections``
    covers a homeroom section for every subject. An empty access allows nothing.
    """

    pairs: frozenset[Pair] = frozenset()
    sections: frozenset[uuid.UUID] = frozenset()

    def allows(self, section_id: uuid.UUID, subject_id: uuid.UUID) -> bool:
        return section_id in self.sections or (section_id, subject_id) in self.pairs


async def _pairs_for_staff(
    session: AsyncSession,
    staff_ids: set[uuid.UUID],
) -> set[Pair]:
    if not staff_ids:
        return set()
    rows = (
        await session.execute(
            select(StaffTeachingAssignment.section_id, StaffTeachingAssignment.subject_id).where(
                StaffTeachingAssignment.staff_id.in_(staff_ids),
                StaffTeachingAssignment.deleted_at.is_(None),
            )
        )
    ).all()
    return {(section_id, subject_id) for section_id, subject_id in rows}


async def visible_access(
    session: AsyncSession,
    principal: Principal,
    permission: str,
) -> MarkAccess | None:
    """The marks a caller may reach, or ``None`` for unrestricted."""
    scopes = effective_scopes(principal, permission)
    if scopes is None or ALL in scopes:
        return None
    user_id = uuid.UUID(principal.user_id)
    pairs: set[Pair] = set()
    sections: set[uuid.UUID] = set()
    if ASSIGNED_SUBJECTS in scopes:
        pairs |= await staff_scopes.assigned_pairs(session, user_id)
    if OWN_CLASS in scopes:
        sections |= await staff_scopes.own_class_section_ids(session, user_id)
    if DEPARTMENT in scopes:
        pairs |= await _pairs_for_staff(session, await staff_scopes.department_staff_ids(session, user_id))
    return MarkAccess(pairs=frozenset(pairs), sections=frozenset(sections))


def condition(
    access: MarkAccess | None,
    model: Any = Assessment,
) -> ColumnElement[bool] | None:
    """A SQL condition that narrows mark rows to a scope.

    ``model`` is the table to narrow; assessments, submissions and corrections
    all carry ``section_id`` and ``subject_id``.
    """
    if access is None:
        return None
    clauses = []
    if access.pairs:
        clauses.append(
            or_(
                *(
                    and_(model.section_id == section_id, model.subject_id == subject_id)
                    for section_id, subject_id in sorted(
                        access.pairs, key=lambda pair: (str(pair[0]), str(pair[1]))
                    )
                )
            )
        )
    if access.sections:
        clauses.append(model.section_id.in_(sorted(access.sections)))
    if not clauses:
        return false()
    return or_(*clauses)


async def assert_visible(
    session: AsyncSession,
    principal: Principal,
    permission: str,
    *,
    section_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> None:
    access = await visible_access(session, principal, permission)
    if access is not None and not access.allows(section_id, subject_id):
        raise Forbidden(
            "These marks are outside your assessment scope",
            message_key="error.scope_denied",
            details={"section_id": str(section_id), "subject_id": str(subject_id)},
        )


__all__ = ["MarkAccess", "assert_visible", "condition", "visible_access"]
