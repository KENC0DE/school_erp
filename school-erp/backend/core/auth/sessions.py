"""Session list and revocation (P1-04)."""

from __future__ import annotations

import uuid

from app.errors import NotFound
from core.audit.service import record
from core.auth.deps import authenticated
from core.auth.principal import Principal
from core.auth.service import list_sessions, revoke_all, revoke_family
from core.db.deps import get_session
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth/sessions", tags=["auth"])


async def _user_id(principal: Principal) -> uuid.UUID:
    return uuid.UUID(principal.actor_id)


@router.get("", dependencies=[Depends(authenticated)])
async def sessions(
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> dict:
    items = await list_sessions(session, await _user_id(principal), principal.session_id)
    return {"items": items, "next_cursor": None}


@router.delete("/{session_id}", dependencies=[Depends(authenticated)])
async def revoke_one(
    session_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> dict:
    changed = await revoke_family(session, await _user_id(principal), session_id)
    if not changed:
        raise NotFound("That session is not active", message_key="error.session_not_found")
    await record(
        session,
        action="auth.session_revoked",
        module="core",
        entity_type="session",
        entity_id=str(session_id),
        actor=principal,
        via=principal.via,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return {"ok": True}


@router.delete("", dependencies=[Depends(authenticated)])
async def revoke_others(
    request: Request,
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> dict:
    current = uuid.UUID(principal.session_id) if principal.session_id else None
    count = await revoke_all(session, await _user_id(principal), except_family=current)
    await record(
        session,
        action="auth.sessions_revoked",
        module="core",
        entity_type="session",
        entity_id=str(current) if current else "all",
        after={"revoked": count},
        actor=principal,
        via=principal.via,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return {"ok": True, "revoked": count}


__all__ = ["router"]
