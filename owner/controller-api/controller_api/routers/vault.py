from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from controller_api.deps import CPPrincipal, current_user, get_session
from controller_api.errors import not_found
from controller_api.models import School, VaultChainHead, VaultEntry

router = APIRouter(prefix="/controller/v1", tags=["controller-vault"])


@router.get("/vault")
async def list_vault(
    school_id: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(VaultEntry).order_by(VaultEntry.school_id, VaultEntry.seq.desc()).limit(limit)
    if school_id:
        stmt = stmt.where(VaultEntry.school_id == school_id)
    rows = (await session.execute(stmt)).scalars().all()
    schools = {row.id: row.name for row in (await session.execute(select(School))).scalars().all()}
    return {
        "items": [
            {
                "id": row.id,
                "school_id": row.school_id,
                "school_name": schools.get(row.school_id),
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
            for row in rows
        ],
        "next_cursor": None,
    }


@router.get("/vault/status")
async def chain_status(
    school_id: str,
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    school = await session.get(School, school_id)
    if school is None:
        raise not_found("School not found")
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
        "school_id": school_id,
        "last_seq": head.last_seq if head else 0,
        "chain_head": head.last_hash if head else None,
        "entries": total,
        "broken_entries": broken,
        "ok": broken == 0,
    }
