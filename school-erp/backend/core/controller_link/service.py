"""Instance side of the controller link: enroll, heartbeat, audit shipping (ARCH §8)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
from app.settings import Settings
from erp_shared.audit import compute_hash
from erp_shared.license import generate_keypair
from erp_shared.signing import sign_detached
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.models import AuditLog, AuditOutbox
from core.audit.service import mark_failed, mark_shipped, unshipped
from core.modules.licensing import apply_license, get_license
from core.modules.models import InstanceIdentity


class ControllerLinkError(RuntimeError):
    pass


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=20)


def canonical_ts(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.isoformat(timespec="microseconds")


async def identity(session: AsyncSession) -> InstanceIdentity:
    row = (await session.execute(select(InstanceIdentity))).scalars().first()
    if row is None:
        pair = generate_keypair()
        row = InstanceIdentity(private_key=pair.private_key, public_key=pair.public_key)
        session.add(row)
        await session.flush()
    return row


async def enroll(
    session: AsyncSession,
    settings: Settings,
    *,
    enrollment_token: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict:
    token = enrollment_token or settings.enrollment_token
    if not token:
        raise ControllerLinkError("No enrollment token configured")
    ident = await identity(session)
    owns_client = client is None
    http = client or _client()
    try:
        response = await http.post(
            f"{settings.controller_url.rstrip('/')}/controller/v1/enroll",
            json={
                "enrollment_token": token,
                "instance_public_key": ident.public_key,
                "name": settings.app_name,
                "app_version": settings.app_version,
                "api_base_url": settings.public_base_url,
            },
        )
    finally:
        if owns_client:
            await http.aclose()
    if response.status_code >= 400:
        raise ControllerLinkError(f"Enrollment failed ({response.status_code}): {response.text}")
    data = response.json()
    await apply_license(session, data["license_token"], data["controller_public_key"], settings)
    ident.enrolled_at = datetime.now(UTC)
    await session.commit()
    return data


async def heartbeat(
    session: AsyncSession,
    settings: Settings,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    state = await get_license(session)
    if state is None or not state.token:
        if settings.enrollment_token:
            await enroll(session, settings, client=client)
            state = await get_license(session)
        else:
            return None
    if state is None or not state.instance_id:
        return None
    ident = await identity(session)
    head = (
        await session.execute(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1))
    ).scalar_one_or_none()
    payload = {
        "instance_id": state.instance_id,
        "app_version": settings.app_version,
        "uptime_seconds": 0,
        "error_count": 0,
        "queue_depth": 0,
        "db_size_bytes": 0,
        "storage_used_bytes": 0,
        "student_count": 0,
        "staff_count": 0,
        "last_backup_at": None,
        "audit_chain_head": head.hash if head else None,
        "audit_seq": head.seq if head else 0,
    }
    payload["signature"] = sign_detached(ident.private_key, payload)
    owns_client = client is None
    http = client or _client()
    try:
        response = await http.post(
            f"{settings.controller_url.rstrip('/')}/controller/v1/heartbeat", json=payload
        )
    finally:
        if owns_client:
            await http.aclose()
    if response.status_code >= 400:
        raise ControllerLinkError(f"Heartbeat failed ({response.status_code}): {response.text}")
    data = response.json()
    await apply_license(session, data["license_token"], state.controller_public_key, settings)
    await session.commit()
    return data


async def ship_audit(
    session: AsyncSession,
    settings: Settings,
    *,
    limit: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict | None:
    batch = await unshipped(session, limit or settings.audit_ship_batch)
    if not batch:
        return None
    state = await get_license(session)
    if state is None or not state.instance_id:
        return None
    ident = await identity(session)
    entries = []
    last_hash = None
    for outbox in batch:
        row = await session.get(AuditLog, outbox.audit_seq)
        if row is None:
            continue
        entry = {
            "seq": row.seq,
            "ts": canonical_ts(row.ts),
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
        # Guard against shipping a row whose hash would not verify upstream.
        if compute_hash(row.prev_hash, entry) != row.hash:
            raise ControllerLinkError(f"Local audit hash mismatch at seq {row.seq}")
        entries.append({"seq": row.seq, "entry": entry, "hash": row.hash, "prev_hash": row.prev_hash})
        last_hash = row.hash
    payload = {
        "instance_id": state.instance_id,
        "entries": entries,
        "chain_head": last_hash,
    }
    payload["signature"] = sign_detached(ident.private_key, payload)
    owns_client = client is None
    http = client or _client()
    try:
        try:
            response = await http.post(
                f"{settings.controller_url.rstrip('/')}/controller/v1/audit/ingest", json=payload
            )
        except Exception as exc:
            await _record_ship_failure(session, settings, batch, str(exc))
            raise
        if response.status_code >= 400:
            error = ControllerLinkError(f"Audit shipping failed ({response.status_code}): {response.text}")
            await _record_ship_failure(session, settings, batch, str(error))
            raise error
    finally:
        if owns_client:
            await http.aclose()

    batch_id = uuid.uuid4()
    await mark_shipped(session, [row.id for row in batch], batch_id)
    await session.commit()
    return response.json()


async def _record_ship_failure(
    session: AsyncSession,
    settings: Settings,
    batch: list[AuditOutbox],
    error: str,
) -> None:
    """Persist the retry state before the caller sees the exception.

    Without this commit the backoff would be rolled back together with the
    failed request, so a controller outage would spin every shipping tick.
    """
    await mark_failed(
        session,
        batch,
        error,
        base_seconds=settings.audit_retry_base_seconds,
        max_seconds=settings.audit_retry_max_seconds,
    )
    await session.commit()
