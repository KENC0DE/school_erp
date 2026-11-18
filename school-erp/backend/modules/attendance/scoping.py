"""Data scope for attendance: which sections a caller may register.

``assigned_subjects`` resolves to every section a teacher teaches (any subject)
and ``own_class`` to the section they own as homeroom teacher. The router keeps
the permission check; this module narrows the rows.
"""

from __future__ import annotations

import uuid

from app.errors import Forbidden
from core.auth.principal import Principal
from core.rbac.scopes import ALL, ASSIGNED_SUBJECTS, OWN_CLASS, effective_scopes
from sqlalchemy.ext.asyncio import AsyncSession

from modules.staff import scopes as staff_scopes


async def visible_section_ids(
    session: AsyncSession,
    principal: Principal,
    permission: str,
) -> set[uuid.UUID] | None:
    """The sections a scoped caller may touch, or ``None`` for unrestricted."""
    scopes = effective_scopes(principal, permission)
    if scopes is None or ALL in scopes:
        return None
    user_id = uuid.UUID(principal.user_id)
    allowed: set[uuid.UUID] = set()
    if ASSIGNED_SUBJECTS in scopes:
        allowed |= await staff_scopes.assigned_section_ids(session, user_id)
    if OWN_CLASS in scopes:
        allowed |= await staff_scopes.own_class_section_ids(session, user_id)
    return allowed


async def assert_section_visible(
    session: AsyncSession,
    principal: Principal,
    permission: str,
    section_id: uuid.UUID,
) -> None:
    allowed = await visible_section_ids(session, principal, permission)
    if allowed is not None and section_id not in allowed:
        raise Forbidden(
            "This section is outside your attendance scope",
            message_key="error.scope_denied",
            details={"section_id": str(section_id)},
        )


__all__ = ["assert_section_visible", "visible_section_ids"]
