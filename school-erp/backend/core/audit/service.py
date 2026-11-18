"""Append-only audit chain, read auditing and outbox shipping helpers (ARCH §5.4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.logging import request_id_var
from core.audit.constants import ACTOR_TYPES, VIA_CHANNELS
from core.audit.models import AuditLog, AuditOutbox
from core.auth.principal import Principal
from erp_shared.audit import compute_hash
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Stable key for the PostgreSQL transaction-scoped advisory lock that serialises
# sequence allocation. Any instance of the app shares the same key.
AUDIT_CHAIN_LOCK_KEY = 0x41554449  # "AUDI"

# Retry errors are shown in the controller vault UI; keep them bounded.
MAX_ERROR_LENGTH = 500


def _iso(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        if getattr(value, "tzinfo", None) is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value.isoformat(timespec="microseconds")
    return value


def chain_lock_statement(dialect_name: str) -> str | None:
    """The sequence-allocation lock for the active database dialect.

    On PostgreSQL an advisory transaction lock makes ``max(seq) + 1`` safe: the
    next writer cannot read the head until the previous transaction commits.

    SQLite only takes its write lock on the first write statement, and the two
    SELECTs that read the head do not take it. A no-op UPDATE (which matches no
    rows, so the append-only trigger never fires) upgrades the transaction to a
    writer before the head is read; a concurrent writer then waits instead of
    choosing the same sequence number.
    """
    if dialect_name == "postgresql":
        return "SELECT pg_advisory_xact_lock(:key)"
    if dialect_name == "sqlite":
        return "UPDATE audit_log SET seq = seq WHERE 0"
    return None


def _validate_actor(actor_type: str, via: str) -> None:
    if actor_type not in ACTOR_TYPES:
        raise ValueError(f"Unknown audit actor type {actor_type!r}")
    if via not in VIA_CHANNELS:
        raise ValueError(f"Unknown audit via channel {via!r}")


async def record(
    session: AsyncSession,
    *,
    action: str,
    module: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    actor: Principal | None = None,
    on_behalf_of: str | None = None,
    reason: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    reverts_id: str | None = None,
    via: str | None = None,
) -> AuditLog:
    """Append one entry and queue it for shipping. Never mutates existing entries."""
    actor_type = actor.actor_type if actor else "system"
    channel = via or (actor.via if actor else "api")
    _validate_actor(actor_type, channel)

    lock = chain_lock_statement(session.get_bind().dialect.name)
    if lock is not None:
        await session.execute(text(lock), {"key": AUDIT_CHAIN_LOCK_KEY})

    last = (
        await session.execute(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1))
    ).scalar_one_or_none()
    prev_hash = last.hash if last else None
    # seq must be known before insert because the hash covers it and the table is
    # append-only (no UPDATE to fill it in afterwards).
    next_seq = (await session.execute(select(func.coalesce(func.max(AuditLog.seq), 0) + 1))).scalar_one()
    entry: dict[str, Any] = {
        "seq": next_seq,
        "ts": datetime.now(UTC),
        "actor_type": actor_type,
        "actor_id": actor.actor_id if actor else None,
        "on_behalf_of": on_behalf_of or (actor.on_behalf_of if actor else None),
        "via": channel,
        "ip": ip,
        "user_agent": user_agent,
        "module": module,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else None,
        "action": action,
        "before": before,
        "after": after,
        "reason": reason or (actor.reason if actor else None),
        "request_id": request_id_var.get() or None,
        "reverts_id": reverts_id,
    }
    row = AuditLog(
        seq=next_seq,
        prev_hash=prev_hash,
        hash=compute_hash(prev_hash, {**entry, "ts": _iso(entry["ts"])}),
        **{key: value for key, value in entry.items() if key != "seq"},
    )
    session.add(row)
    await session.flush()
    session.add(AuditOutbox(audit_seq=row.seq))
    return row


async def record_read(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: str | None = None,
    actor: Principal | None = None,
    action: str | None = None,
    module: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    reason: str | None = None,
    via: str | None = None,
) -> AuditLog:
    """Audit access to a sensitive record (ARCH §5.4 tier A history).

    Callers must commit: read endpoints normally rely on a later mutation to
    commit, which never happens for a pure GET.
    """
    return await record(
        session,
        action=action or f"{entity_type}.read",
        module=module,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        reason=reason,
        ip=ip,
        user_agent=user_agent,
        via=via,
    )


async def verify_chain(session: AsyncSession) -> dict[str, Any]:
    rows = (await session.execute(select(AuditLog).order_by(AuditLog.seq))).scalars().all()
    prev_hash: str | None = None
    for row in rows:
        entry = {
            "seq": row.seq,
            "ts": _iso(row.ts),
            "actor_type": row.actor_type,
            "actor_id": row.actor_id,
            "on_behalf_of": row.on_behalf_of,
            "via": row.via,
            "ip": row.ip,
            "user_agent": row.user_agent,
            "module": row.module,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "action": row.action,
            "before": row.before,
            "after": row.after,
            "reason": row.reason,
            "request_id": row.request_id,
            "reverts_id": row.reverts_id,
        }
        expected = compute_hash(prev_hash, entry)
        if row.prev_hash != prev_hash or row.hash != expected:
            return {
                "ok": False,
                "entries": len(rows),
                "broken_seq": row.seq,
                "chain_head": rows[-1].hash if rows else None,
            }
        prev_hash = row.hash
    return {"ok": True, "entries": len(rows), "broken_seq": None, "chain_head": prev_hash}


async def unshipped(session: AsyncSession, limit: int = 100) -> list[AuditOutbox]:
    """Rows that are neither shipped nor waiting for a retry slot."""
    now = datetime.now(UTC)
    return list(
        (
            await session.execute(
                select(AuditOutbox)
                .where(
                    AuditOutbox.shipped_at.is_(None),
                    (AuditOutbox.available_at.is_(None)) | (AuditOutbox.available_at <= now),
                )
                .order_by(AuditOutbox.audit_seq)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


def retry_delay(attempts: int, *, base_seconds: int, max_seconds: int) -> timedelta:
    """Exponential backoff: base, 2×base, 4×base … capped at max."""
    exponent = max(attempts - 1, 0)
    return timedelta(seconds=min(base_seconds * (2**exponent), max_seconds))


async def mark_shipped(session: AsyncSession, ids: list[uuid.UUID], batch_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    for row_id in ids:
        row = await session.get(AuditOutbox, row_id)
        if row is not None:
            row.shipped_at = now
            row.batch_id = batch_id
            row.last_error = None
            row.available_at = None
    await session.flush()


async def mark_failed(
    session: AsyncSession,
    rows: list[AuditOutbox],
    error: str,
    *,
    base_seconds: int,
    max_seconds: int,
) -> None:
    """Record a failed shipping attempt and schedule the next one with backoff."""
    now = datetime.now(UTC)
    for row in rows:
        row.attempts = (row.attempts or 0) + 1
        row.last_attempt_at = now
        row.last_error = error[:MAX_ERROR_LENGTH]
        row.available_at = now + retry_delay(row.attempts, base_seconds=base_seconds, max_seconds=max_seconds)
    await session.flush()


__all__ = [
    "AUDIT_CHAIN_LOCK_KEY",
    "chain_lock_statement",
    "mark_failed",
    "mark_shipped",
    "record",
    "record_read",
    "retry_delay",
    "unshipped",
    "verify_chain",
]
