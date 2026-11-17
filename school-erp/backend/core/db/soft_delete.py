"""Soft-delete and restore helpers (ARCH §5.1).

Hard deletes are forbidden. ``soft_delete`` stamps ``deleted_at``/``deleted_by``,
bumps ``row_version`` and writes an audit entry; ``restore`` reverses it and
audits the restoration as a new entry (the original delete entry is untouched).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.errors import NotFound
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.service import record
from core.auth.principal import Principal
from core.db.base import SoftDeleteMixin


def actor_uuid(actor: Principal | None) -> uuid.UUID | None:
    if actor is None or actor.actor_type != "user":
        return None
    try:
        return uuid.UUID(actor.actor_id)
    except ValueError:
        return None


def _timestamp(value: datetime | None = None) -> datetime:
    return value or datetime.now(UTC)


def is_deleted(entity: Any) -> bool:
    return getattr(entity, "deleted_at", None) is not None


def mark_deleted(
    entity: Any,
    *,
    actor: Principal | None = None,
    when: datetime | None = None,
) -> dict[str, Any]:
    """Stamp the row. Returns the before-state for the audit entry."""
    if is_deleted(entity):
        return {}
    before = _state(entity)
    entity.deleted_at = _timestamp(when)
    entity.deleted_by = actor_uuid(actor)
    entity.row_version = (entity.row_version or 0) + 1
    return before


def mark_restored(entity: Any, *, actor: Principal | None = None) -> dict[str, Any]:
    """Clear the delete stamps. Returns the before-state for the audit entry."""
    if not is_deleted(entity):
        return {}
    before = _state(entity)
    entity.deleted_at = None
    entity.deleted_by = None
    entity.row_version = (entity.row_version or 0) + 1
    _ = actor  # the restore actor is recorded in the audit entry, not on the row
    return before


def _state(entity: Any) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for key in ("id", "deleted_at", "deleted_by", "row_version"):
        if hasattr(entity, key):
            value = getattr(entity, key)
            if isinstance(value, uuid.UUID):
                value = str(value)
            elif isinstance(value, datetime):
                value = value.isoformat()
            state[key] = value
    return state


async def soft_delete(
    session: AsyncSession,
    entity: Any,
    *,
    action: str,
    module: str,
    actor: Principal | None = None,
    reason: str | None = None,
    via: str | None = None,
    entity_type: str | None = None,
) -> bool:
    """Soft-delete ``entity`` and audit it. Returns False if already deleted."""
    if not isinstance(entity, SoftDeleteMixin) and not hasattr(entity, "deleted_at"):
        raise TypeError("soft_delete requires a SoftDeleteMixin entity")
    before = mark_deleted(entity, actor=actor)
    if not before:
        return False
    await record(
        session,
        action=action,
        module=module,
        entity_type=entity_type or getattr(entity, "__tablename__", type(entity).__name__),
        entity_id=str(entity.id),
        before=before,
        after=_state(entity),
        actor=actor,
        reason=reason,
        via=via,
    )
    return True


async def restore(
    session: AsyncSession,
    entity: Any,
    *,
    action: str,
    module: str,
    actor: Principal | None = None,
    reason: str | None = None,
    via: str | None = None,
    entity_type: str | None = None,
) -> bool:
    """Restore ``entity`` and audit it. Returns False if already live."""
    if not hasattr(entity, "deleted_at"):
        raise TypeError("restore requires a soft-deletable entity")
    before = mark_restored(entity, actor=actor)
    if not before:
        return False
    await record(
        session,
        action=action,
        module=module,
        entity_type=entity_type or getattr(entity, "__tablename__", type(entity).__name__),
        entity_id=str(entity.id),
        before=before,
        after=_state(entity),
        actor=actor,
        reason=reason,
        via=via,
    )
    return True


async def get_including_deleted(session: AsyncSession, model: Any, entity_id: Any) -> Any | None:
    """Fetch one row even when it is soft-deleted (restore/undo paths only)."""
    from sqlalchemy import select

    from core.db.filters import INCLUDE_DELETED

    return (
        await session.execute(
            select(model).where(model.id == entity_id).execution_options(**{INCLUDE_DELETED: True})
        )
    ).scalar_one_or_none()


async def get_live(session: AsyncSession, model: Any, entity_id: Any) -> Any:
    """Fetch a live row or raise ``NotFound``."""
    from sqlalchemy import select

    row = (await session.execute(select(model).where(model.id == entity_id))).scalar_one_or_none()
    if row is None:
        raise NotFound()
    return row


__all__ = [
    "actor_uuid",
    "get_including_deleted",
    "get_live",
    "is_deleted",
    "mark_deleted",
    "mark_restored",
    "restore",
    "soft_delete",
]
