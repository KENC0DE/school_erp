from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from controller_api.deps import CPPrincipal, current_user, get_session
from controller_api.errors import not_found
from controller_api.models import Alert, School, VaultChainHead, VaultEntry
from controller_api.vault_scan import scan_school

router = APIRouter(prefix="/controller/v1", tags=["controller-vault"])


def _serialize(row: VaultEntry, school_name: str | None) -> dict:
    return {
        "id": row.id,
        "school_id": row.school_id,
        "school_name": school_name,
        "seq": row.seq,
        "action": row.entry.get("action"),
        "module": row.entry.get("module"),
        "actor_type": row.entry.get("actor_type"),
        "actor_id": row.entry.get("actor_id"),
        "via": row.entry.get("via"),
        "entity_type": row.entry.get("entity_type"),
        "entity_id": row.entry.get("entity_id"),
        "ts": row.entry.get("ts"),
        "chain_ok": row.chain_ok,
    }


@router.get("/vault")
async def list_vault(
    school_id: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    action: str | None = Query(default=None, max_length=120),
    module: str | None = Query(default=None, max_length=60),
    chain_ok: bool | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(VaultEntry)
    if school_id:
        stmt = stmt.where(VaultEntry.school_id == school_id)
    if action:
        stmt = stmt.where(VaultEntry.entry["action"].as_string() == action)
    if module:
        stmt = stmt.where(VaultEntry.entry["module"].as_string() == module)
    if chain_ok is not None:
        stmt = stmt.where(VaultEntry.chain_ok.is_(chain_ok))
    if date_from:
        stmt = stmt.where(VaultEntry.received_at >= date_from)
    if date_to:
        stmt = stmt.where(VaultEntry.received_at <= date_to)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                VaultEntry.entry["action"].as_string().ilike(like),
                VaultEntry.entry["entity_id"].as_string().ilike(like),
                VaultEntry.entry["actor_id"].as_string().ilike(like),
                VaultEntry.entry["entity_type"].as_string().ilike(like),
            )
        )
    stmt = stmt.order_by(VaultEntry.school_id, VaultEntry.seq.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    schools = {row.id: row.name for row in (await session.execute(select(School))).scalars().all()}
    return {
        "items": [_serialize(row, schools.get(row.school_id)) for row in rows],
        "next_cursor": None,
    }


@router.get("/vault/status")
async def chain_status(
    school_id: str | None = Query(default=None),
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if school_id:
        school = await session.get(School, school_id)
        if school is None:
            raise not_found("School not found")
        return {
            "school_id": school_id,
            "school_name": school.name,
            **await _school_status(session, school_id),
        }
    schools = (await session.execute(select(School).order_by(School.name))).scalars().all()
    items = []
    for school in schools:
        items.append(
            {"school_id": school.id, "school_name": school.name, **await _school_status(session, school.id)}
        )
    return {"items": items, "ok": all(item["ok"] for item in items)}


async def _school_status(session: AsyncSession, school_id: str) -> dict:
    head = await session.get(VaultChainHead, school_id)
    total = (
        await session.execute(select(func.count(VaultEntry.id)).where(VaultEntry.school_id == school_id))
    ).scalar_one()
    broken = (
        await session.execute(
            select(func.count(VaultEntry.id)).where(
                VaultEntry.school_id == school_id, VaultEntry.chain_ok.is_(False)
            )
        )
    ).scalar_one()
    return {
        "last_seq": head.last_seq if head else 0,
        "chain_head": head.last_hash if head else None,
        "entries": total,
        "broken_entries": broken,
        "ok": broken == 0,
    }


@router.get("/vault/alerts")
async def list_alerts(
    school_id: str | None = Query(default=None),
    include_resolved: bool = Query(default=False),
    limit: int = Query(default=100, le=500),
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if school_id:
        stmt = stmt.where(Alert.school_id == school_id)
    if not include_resolved:
        stmt = stmt.where(Alert.resolved_at.is_(None))
    rows = (await session.execute(stmt)).scalars().all()
    schools = {row.id: row.name for row in (await session.execute(select(School))).scalars().all()}
    return {
        "items": [
            {
                "id": row.id,
                "school_id": row.school_id,
                "school_name": schools.get(row.school_id),
                "kind": row.kind,
                "message": row.message,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            }
            for row in rows
        ],
        "next_cursor": None,
    }


@router.post("/vault/scan")
async def scan_vault(
    request: Request,
    school_id: str | None = Query(default=None),
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if school_id:
        school = await session.get(School, school_id)
        if school is None:
            raise not_found("School not found")
        ids = [school_id]
    else:
        ids = list((await session.execute(select(School.id))).scalars().all())
    alerts = []
    for identifier in ids:
        alerts.extend(await scan_school(session, identifier, request.app.state.settings))
    await session.commit()
    return {
        "created": len(alerts),
        "items": [
            {"id": alert.id, "school_id": alert.school_id, "kind": alert.kind, "message": alert.message}
            for alert in alerts
        ],
    }


@router.post("/vault/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    alert = await session.get(Alert, alert_id)
    if alert is None:
        raise not_found("Alert not found")
    from datetime import UTC

    alert.resolved_at = datetime.now(UTC)
    await session.commit()
    return {"id": alert.id, "resolved": True}
