"""Revertible entities and audited rollback (P1-11).

Modules opt in by registering a :class:`Reverter` for their entity type. A
revert never edits history: it applies the earlier state through the entity's
own service and appends a *new* audit entry whose ``reverts_id`` points at the
original entry.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.errors import Conflict, Forbidden, NotFound, ValidationFailed
from core.audit.models import AuditLog
from core.audit.service import record
from core.audit.visibility import ACTIVITY_PERMISSION, apply_visibility, scoped_modules
from core.auth.principal import Principal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class RevertContext:
    session: AsyncSession
    principal: Principal
    entity_id: str
    before: dict | None
    after: dict | None
    reason: str
    via: str


ApplyFn = Callable[[RevertContext], Awaitable[dict]]
RestoreFn = Callable[[RevertContext], Awaitable[dict]]


@dataclass
class Reverter:
    entity_type: str
    module: str
    permission: str
    apply: ApplyFn
    restore: RestoreFn | None = None


_reverters: dict[str, Reverter] = {}


def register_reverter(reverter: Reverter) -> Reverter:
    if reverter.entity_type in _reverters:
        raise ValueError(f"Duplicate reverter for {reverter.entity_type}")
    _reverters[reverter.entity_type] = reverter
    return reverter


def get_reverter(entity_type: str | None) -> Reverter | None:
    if not entity_type:
        return None
    return _reverters.get(entity_type)


def is_revertible(entity_type: str | None, action: str) -> bool:
    reverter = get_reverter(entity_type)
    if reverter is None:
        return False
    if action.endswith(".delete") and reverter.restore is None:
        return False
    return True


async def _load_entry(session: AsyncSession, principal: Principal, seq: int) -> AuditLog:
    row = (
        await session.execute(
            apply_visibility(
                select(AuditLog).where(AuditLog.seq == seq),
                modules=scoped_modules(principal),
                hide_actor_ids=set(),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("Audit entry not found")
    return row


async def revert_entry(
    session: AsyncSession,
    principal: Principal,
    seq: int,
    *,
    reason: str,
    restore: bool = False,
) -> dict:
    """Apply the earlier state of one audit entry and audit the rollback."""
    if not reason or not reason.strip():
        raise ValidationFailed("A reason is required to revert a change", message_key="error.reason_required")
    row = await _load_entry(session, principal, seq)
    reverter = get_reverter(row.entity_type)
    if reverter is None or not row.entity_id:
        raise Conflict(
            "This entry cannot be reverted automatically",
            message_key="error.not_revertible",
            details={"entity_type": row.entity_type},
        )
    if not principal.can(reverter.permission):
        raise Forbidden(
            "You may not change this kind of record",
            message_key="error.permission_denied",
            details={"permission": reverter.permission},
        )
    is_delete = row.action.endswith(".delete")
    if restore and not is_delete:
        raise Conflict("Only a deletion can be restored", message_key="error.not_revertible")
    if restore and reverter.restore is None:
        raise Conflict("This record has no restore handler", message_key="error.not_revertible")

    ctx = RevertContext(
        session=session,
        principal=principal,
        entity_id=row.entity_id,
        before=row.before,
        after=row.after,
        reason=reason.strip(),
        via=principal.via,
    )
    state = await (reverter.restore(ctx) if restore else reverter.apply(ctx))

    entry = await record(
        session,
        action=f"{reverter.entity_type}.{'restore' if restore else 'revert'}",
        module=reverter.module,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        before=row.after,
        after=state,
        actor=principal,
        reason=reason.strip(),
        reverts_id=str(seq),
        via=principal.via,
    )
    await session.commit()
    return {
        "reverted_seq": seq,
        "audit_seq": entry.seq,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "reason": reason.strip(),
    }


def new_entity_id() -> str:
    return str(uuid.uuid4())


__all__ = [
    "ACTIVITY_PERMISSION",
    "RevertContext",
    "Reverter",
    "get_reverter",
    "is_revertible",
    "new_entity_id",
    "register_reverter",
    "revert_entry",
]
