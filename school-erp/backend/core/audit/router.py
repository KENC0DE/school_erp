"""School activity history (Tier A, ARCH §5.4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.errors import Forbidden, NotFound
from core.audit.models import AuditLog
from core.audit.service import record_read, verify_chain
from core.audit.visibility import (
    ACTIVITY_PERMISSION,
    ADMIN_ACTIONS_PERMISSION,
    actor_names,
    apply_visibility,
    as_utc,
    scoped_modules,
    serialize_entry,
    super_admin_actor_ids,
    user_names,
)
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/audit", tags=["audit"])


def _request_meta(request: Request) -> dict[str, str | None]:
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


async def _hidden_actors(principal: Principal, session: AsyncSession) -> set[str]:
    if principal.can(ADMIN_ACTIONS_PERMISSION):
        return set()
    return await super_admin_actor_ids(session)


@router.get("/activity", dependencies=[Depends(require(ACTIVITY_PERMISSION))])
async def activity(
    principal: Principal = Depends(require(ACTIVITY_PERMISSION)),
    session: AsyncSession = Depends(get_session),
    actor_id: str | None = Query(default=None),
    module: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    modules = scoped_modules(principal)
    if module and modules is not None and module not in modules:
        raise Forbidden(
            "That module is outside your activity scope",
            message_key="error.permission_denied",
            details={"module": module},
        )

    stmt = apply_visibility(
        select(AuditLog),
        modules=modules,
        hide_actor_ids=await _hidden_actors(principal, session),
    )
    if module:
        stmt = stmt.where(AuditLog.module == module)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if date_from:
        stmt = stmt.where(AuditLog.ts >= as_utc(date_from))
    if date_to:
        stmt = stmt.where(AuditLog.ts <= as_utc(date_to))

    rows = list(
        (await session.execute(stmt.order_by(AuditLog.seq.desc()).limit(limit))).scalars().all()
    )
    names = await actor_names(session, rows)
    return {"items": [serialize_entry(row, names) for row in rows], "next_cursor": None}


@router.get("/activity/options", dependencies=[Depends(require(ACTIVITY_PERMISSION))])
async def activity_options(
    principal: Principal = Depends(require(ACTIVITY_PERMISSION)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    modules = scoped_modules(principal)
    hide = await _hidden_actors(principal, session)

    def visible(stmt: Any) -> Any:
        return apply_visibility(stmt, modules=modules, hide_actor_ids=hide)

    module_rows = (
        await session.execute(
            visible(select(AuditLog.module).order_by(AuditLog.module).distinct())
        )
    ).scalars()
    action_rows = (
        await session.execute(
            visible(select(AuditLog.action).order_by(AuditLog.action).distinct())
        )
    ).scalars()
    actor_rows = (
        await session.execute(
            visible(select(AuditLog.actor_id, AuditLog.actor_type))
            .order_by(AuditLog.actor_type, AuditLog.actor_id)
            .distinct()
            .limit(200)
        )
    ).all()

    ids: set[uuid.UUID] = set()
    for value, _actor_type in actor_rows:
        if not value:
            continue
        try:
            ids.add(uuid.UUID(value))
        except ValueError:
            continue
    names = await user_names(session, ids)
    return {
        "modules": [key for key in module_rows if key],
        "actions": [key for key in action_rows if key],
        "actors": [
            {
                "id": value,
                "actor_type": actor_type,
                "name": names.get(value) if value else None,
            }
            for value, actor_type in actor_rows
            if value
        ],
    }


@router.get("/activity/{seq}", dependencies=[Depends(require(ACTIVITY_PERMISSION))])
async def activity_entry(
    seq: int,
    request: Request,
    principal: Principal = Depends(require(ACTIVITY_PERMISSION)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = (
        await session.execute(
            apply_visibility(
                select(AuditLog).where(AuditLog.seq == seq),
                modules=scoped_modules(principal),
                hide_actor_ids=await _hidden_actors(principal, session),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("Audit entry not found")

    names = await actor_names(session, [row])
    await record_read(
        session,
        action="audit.activity.read",
        module="core",
        entity_type="audit_entry",
        entity_id=str(row.seq),
        actor=principal,
        via=principal.via,
        **_request_meta(request),
    )
    await session.commit()
    return serialize_entry(row, names)


@router.get("/verify", dependencies=[Depends(require("audit.verify"))])
async def verify(session: AsyncSession = Depends(get_session)) -> dict:
    return await verify_chain(session)
