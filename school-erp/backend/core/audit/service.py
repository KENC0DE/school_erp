from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.logging import request_id_var
from core.audit.models import AuditLog, AuditOutbox
from core.auth.principal import Principal
from erp_shared.audit import compute_hash
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _iso(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        if getattr(value, "tzinfo", None) is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value.isoformat(timespec="microseconds")
    return value


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
    reason: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    reverts_id: str | None = None,
    via: str | None = None,
) -> AuditLog:
    """Append one entry and queue it for shipping. Never mutates existing entries."""
    last = (
        await session.execute(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1))
    ).scalar_one_or_none()
    prev_hash = last.hash if last else None
    # seq must be known before insert because the hash covers it and the table is
    # append-only (no UPDATE to fill it in afterwards). SQLite serialises writers;
    # PostgreSQL moves to a dedicated sequence + advisory lock in P1.
    next_seq = (await session.execute(select(func.coalesce(func.max(AuditLog.seq), 0) + 1))).scalar_one()
    entry: dict[str, Any] = {
        "seq": next_seq,
        "ts": datetime.now(UTC),
        "actor_type": actor.actor_type if actor else "system",
        "actor_id": actor.actor_id if actor else None,
        "on_behalf_of": None,
        "via": via or (actor.via if actor else "api"),
        "ip": ip,
        "user_agent": user_agent,
        "module": module,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else None,
        "action": action,
        "before": before,
        "after": after,
        "reason": reason,
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
    return list(
        (
            await session.execute(
                select(AuditOutbox)
                .where(AuditOutbox.shipped_at.is_(None))
                .order_by(AuditOutbox.audit_seq)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def mark_shipped(session: AsyncSession, ids: list[uuid.UUID], batch_id: uuid.UUID) -> None:
    for row_id in ids:
        row = await session.get(AuditOutbox, row_id)
        if row is not None:
            row.shipped_at = datetime.now(UTC)
            row.batch_id = batch_id
    await session.flush()
