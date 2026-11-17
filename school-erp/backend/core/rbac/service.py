from __future__ import annotations

import uuid
from datetime import UTC, datetime

from core.auth.principal import Principal, _permission_matches
from core.rbac.models import (
    Role,
    RolePermission,
    UserPermissionOverride,
    UserRole,
)
from core.rbac.scopes import scope_covers
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _active(expires_at: datetime | None, now: datetime) -> bool:
    expiry = _aware(expires_at)
    return expiry is None or expiry >= now


async def effective_permissions(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[set[str], dict[str, set[str]]]:
    """Compute the effective (permission, scopes) set for a user.

    Denies always win, even when a role grants the same permission or the deny
    row was created first. Expired grants and denies are ignored. Inactive roles
    contribute nothing.
    """
    role_rows = await session.execute(
        select(RolePermission.permission, RolePermission.scope)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .join(Role, Role.id == RolePermission.role_id)
        .where(UserRole.user_id == user_id, Role.is_active.is_(True))
    )
    permissions: set[str] = set()
    scopes: dict[str, set[str]] = {}
    for permission, scope in role_rows.all():
        permissions.add(permission)
        scopes.setdefault(permission, set()).add(scope)

    override_rows = await session.execute(
        select(
            UserPermissionOverride.permission,
            UserPermissionOverride.scope,
            UserPermissionOverride.effect,
            UserPermissionOverride.expires_at,
        ).where(UserPermissionOverride.user_id == user_id)
    )
    now = datetime.now(UTC)
    denies: list[str] = []
    for permission, scope, effect, expires_at in override_rows.all():
        if not _active(expires_at, now):
            continue
        if effect == "deny":
            denies.append(permission)
            continue
        permissions.add(permission)
        scopes.setdefault(permission, set()).add(scope)

    for denied in denies:
        for permission in list(permissions):
            if _permission_matches(denied, permission):
                permissions.discard(permission)
                scopes.pop(permission, None)

    return permissions, scopes


async def roles_for_user(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    rows = await session.execute(
        select(Role.key)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, Role.is_active.is_(True))
        .order_by(Role.key)
    )
    return [row[0] for row in rows.all()]


async def role_permission_pairs(session: AsyncSession, role_id: uuid.UUID) -> list[tuple[str, str]]:
    rows = await session.execute(
        select(RolePermission.permission, RolePermission.scope)
        .where(RolePermission.role_id == role_id)
        .order_by(RolePermission.permission, RolePermission.scope)
    )
    return [(permission, scope) for permission, scope in rows.all()]


def holds(principal: Principal, permission: str, scope: str) -> bool:
    """A caller may only grant or deny what they hold with a covering scope."""
    if "*" in principal.permissions:
        return True
    if "*" in permission:
        return False
    if not principal.can(permission):
        return False
    granted_scopes: set[str] = set()
    for granted in principal.permissions:
        if _permission_matches(granted, permission):
            granted_scopes |= principal.scopes.get(granted, set())
    return any(scope_covers(candidate, scope) for candidate in granted_scopes)


__all__ = [
    "effective_permissions",
    "holds",
    "role_permission_pairs",
    "roles_for_user",
]
