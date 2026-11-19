"""Scope resolvers for leave, built on the staff department and account links."""

from __future__ import annotations

import uuid

from app.errors import Forbidden
from core.auth.principal import Principal
from core.rbac.scopes import ALL, DEPARTMENT, SELF, effective_scopes
from sqlalchemy.ext.asyncio import AsyncSession

from modules.staff import scopes as staff_scopes


async def visible_leave_staff_ids(
    session: AsyncSession,
    principal: Principal,
    permission: str = "staff.leave.view",
) -> set[uuid.UUID] | None:
    """Staff whose leave a caller may read, or ``None`` for everyone."""
    scopes = effective_scopes(principal, permission)
    if scopes is None or ALL in scopes:
        return None
    allowed: set[uuid.UUID] = set()
    user_id = uuid.UUID(principal.user_id)
    if SELF in scopes:
        profile = await staff_scopes.staff_for_user(session, user_id)
        if profile is not None:
            allowed.add(profile.id)
    if DEPARTMENT in scopes:
        allowed |= await staff_scopes.department_staff_ids(session, user_id)
    return allowed


async def assert_leave_staff_visible(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    *,
    permission: str = "staff.leave.view",
) -> None:
    allowed = await visible_leave_staff_ids(session, principal, permission)
    if allowed is not None and staff_id not in allowed:
        raise Forbidden(
            "This leave record is outside your scope",
            message_key="error.scope_denied",
            details={"staff_id": str(staff_id)},
        )


async def assert_can_request_for(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
) -> None:
    """A ``self`` requester may only file their own leave."""
    scopes = effective_scopes(principal, "staff.leave.request")
    if scopes is None or ALL in scopes:
        return
    profile = await staff_scopes.staff_for_user(session, uuid.UUID(principal.user_id))
    if SELF not in scopes or profile is None or profile.id != staff_id:
        raise Forbidden(
            "You can only request leave for yourself",
            message_key="error.scope_denied",
            details={"staff_id": str(staff_id)},
        )


async def assert_can_decide_for(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
) -> None:
    """``department`` approvers decide for their department, ``all`` for anyone."""
    scopes = effective_scopes(principal, "staff.leave.approve")
    if scopes is None or ALL in scopes:
        return
    if DEPARTMENT in scopes:
        allowed = await staff_scopes.department_staff_ids(session, uuid.UUID(principal.user_id))
        if staff_id in allowed:
            return
    raise Forbidden(
        "This leave request is outside your approval scope",
        message_key="error.scope_denied",
        details={"staff_id": str(staff_id)},
    )


__all__ = [
    "assert_can_decide_for",
    "assert_can_request_for",
    "assert_leave_staff_visible",
    "visible_leave_staff_ids",
]
