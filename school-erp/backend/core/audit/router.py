from __future__ import annotations

from core.audit.models import AuditLog
from core.audit.service import record_read, verify_chain
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/audit", tags=["audit"])


def _entry(row: AuditLog) -> dict:
    return {
        "seq": row.seq,
        "ts": row.ts.isoformat() if row.ts else None,
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "on_behalf_of": row.on_behalf_of,
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


@router.get("/activity", dependencies=[Depends(require("audit.activity.view"))])
async def activity(
    principal: Principal = Depends(require("audit.activity.view")),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, le=200),
) -> dict:
    stmt = select(AuditLog).order_by(AuditLog.seq.desc()).limit(limit)
    if not principal.can("audit.activity.view_admin_actions"):
        # Hide the Super Admin's own actions from ordinary activity viewers.
        stmt = stmt.where(AuditLog.actor_type != "controller")
    rows = (await session.execute(stmt)).scalars().all()
    return {"items": [_entry(row) for row in rows], "next_cursor": None}


@router.get("/activity/{seq}", dependencies=[Depends(require("audit.activity.view"))])
async def activity_entry(
    seq: int,
    request: Request,
    principal: Principal = Depends(require("audit.activity.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await session.get(AuditLog, seq)
    if row is None:
        from app.errors import NotFound

        raise NotFound("Audit entry not found")
    await record_read(
        session,
        action="audit.activity.read",
        module="core",
        entity_type="audit_entry",
        entity_id=str(row.seq),
        actor=principal,
        via=principal.via,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return _entry(row)


@router.get("/verify", dependencies=[Depends(require("audit.verify"))])
async def verify(session: AsyncSession = Depends(get_session)) -> dict:
    return await verify_chain(session)
