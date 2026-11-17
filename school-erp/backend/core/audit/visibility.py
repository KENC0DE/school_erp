"""Tier A visibility rules for the school activity history (ARCH §5.4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from core.audit.models import AuditLog
from core.auth.models import User
from core.auth.principal import Principal
from core.rbac.models import Role, UserRole
from sqlalchemy import false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# Tier B: technical and security events. They live in the same append-only chain
# for the controller vault, but the school activity API must never return them.
TIER_B_ACTIONS = frozenset(
    {
        "auth.controller_session",
        "auth.password_reset",
        "auth.password_reset_requested",
        "auth.session_revoked",
        "auth.sessions_revoked",
        "auth.totp_disabled",
        "auth.totp_enabled",
    }
)
TIER_B_PREFIXES = ("jobs.", "system.", "worker.", "infra.")

ACTIVITY_PERMISSION = "audit.activity.view"
ADMIN_ACTIONS_PERMISSION = "audit.activity.view_admin_actions"


def is_tier_b(action: str, module: str | None) -> bool:
    if module is None:
        return True
    if action in TIER_B_ACTIONS:
        return True
    return action.startswith(TIER_B_PREFIXES)


def scoped_modules(principal: Principal, permission: str = ACTIVITY_PERMISSION) -> set[str] | None:
    """Module keys this principal may see, or ``None`` for every module."""
    matching = {grant for grant in principal.permissions if grant == "*" or grant == permission}
    if "*" in matching:
        return None
    allowed = set(principal.scopes.get(permission, set()))
    if "all" in allowed:
        return None
    return allowed


async def super_admin_actor_ids(session: AsyncSession) -> set[str]:
    rows = (
        await session.execute(
            select(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.key == "super_admin", Role.is_active.is_(True))
        )
    ).scalars()
    return {str(user_id) for user_id in rows}


def apply_visibility(
    stmt: Any,
    *,
    modules: set[str] | None,
    hide_actor_ids: set[str],
) -> Any:
    """Apply scope, admin-action hiding and the Tier B exclusion to a query."""
    stmt = stmt.where(AuditLog.module.is_not(None))
    stmt = stmt.where(~AuditLog.action.in_(TIER_B_ACTIONS))
    for prefix in TIER_B_PREFIXES:
        stmt = stmt.where(~AuditLog.action.like(f"{prefix}%"))
    if modules is not None:
        if not modules:
            return stmt.where(false())
        stmt = stmt.where(AuditLog.module.in_(modules))
    if hide_actor_ids:
        stmt = stmt.where(
            or_(AuditLog.actor_id.is_(None), ~AuditLog.actor_id.in_(hide_actor_ids))
        )
    return stmt


async def user_names(session: AsyncSession, ids: set[uuid.UUID]) -> dict[str, str]:
    if not ids:
        return {}
    users = (await session.execute(select(User.id, User.display_name).where(User.id.in_(ids)))).all()
    return {str(user_id): display_name for user_id, display_name in users}


async def actor_names(session: AsyncSession, rows: list[AuditLog]) -> dict[str, str]:
    """Resolve user display names for actors and delegated actors."""
    ids: set[uuid.UUID] = set()
    for row in rows:
        for value in (row.actor_id, row.on_behalf_of):
            if not value:
                continue
            try:
                ids.add(uuid.UUID(value))
            except ValueError:
                continue
    return await user_names(session, ids)


def serialize_entry(row: AuditLog, names: dict[str, str]) -> dict[str, Any]:
    """Business-facing fields only: no IP, user-agent, hashes or request ids."""
    return {
        "seq": row.seq,
        "ts": row.ts.isoformat() if row.ts else None,
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "actor_name": names.get(row.actor_id) if row.actor_id else None,
        "on_behalf_of": row.on_behalf_of,
        "on_behalf_of_name": names.get(row.on_behalf_of) if row.on_behalf_of else None,
        "via": row.via,
        "module": row.module,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "action": row.action,
        "before": row.before,
        "after": row.after,
        "reason": row.reason,
        "reverts_id": row.reverts_id,
    }


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "ACTIVITY_PERMISSION",
    "ADMIN_ACTIONS_PERMISSION",
    "TIER_B_ACTIONS",
    "TIER_B_PREFIXES",
    "actor_names",
    "apply_visibility",
    "as_utc",
    "is_tier_b",
    "scoped_modules",
    "serialize_entry",
    "super_admin_actor_ids",
    "user_names",
]
