from __future__ import annotations

import uuid
from datetime import UTC, datetime

from core.auth.principal import Principal
from core.rbac.models import (
    Role,
    RolePermission,
    UserPermissionOverride,
    UserRole,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def effective_permissions(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[set[str], dict[str, set[str]]]:
    permissions: set[str] = set()
    scopes: dict[str, set[str]] = {}

    role_rows = await session.execute(
        select(RolePermission.permission, RolePermission.scope)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
    )
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
    for permission, scope, effect, expires_at in override_rows.all():
        if expires_at is not None:
            aware = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
            if aware < now:
                continue
        if effect == "deny":
            permissions.discard(permission)
            scopes.pop(permission, None)
        else:
            permissions.add(permission)
            scopes.setdefault(permission, set()).add(scope)
    return permissions, scopes


async def roles_for_user(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    rows = await session.execute(
        select(Role.key).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return [row[0] for row in rows.all()]


def principal_has(principal: Principal, permission: str) -> bool:
    return principal.can(permission)
