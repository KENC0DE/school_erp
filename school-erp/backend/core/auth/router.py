"""Authentication API (ARCH §5.2, P1-04)."""

from __future__ import annotations

import uuid

from app.errors import Unauthorized
from app.settings import Settings
from core.audit.service import record
from core.auth.deps import authenticated, get_current_principal, public_access, require
from core.auth.models import User
from core.auth.principal import Principal
from core.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenPair,
)
from core.auth.security import create_access_token
from core.auth.service import authenticate, revoke_all, rotate_refresh
from core.db.deps import get_session
from core.modules.licensing import get_license, module_states
from erp_shared.license import LicenseError, verify_payload
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(public_access)])
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    settings: Settings = request.app.state.settings
    issued = await authenticate(session, settings, payload, request)
    return LoginResponse(tokens=issued.tokens, user=issued.user)


@router.post("/refresh", response_model=TokenPair, dependencies=[Depends(public_access)])
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    settings: Settings = request.app.state.settings
    issued = await rotate_refresh(session, settings, payload.refresh_token, request)
    return issued.tokens


@router.post("/logout", dependencies=[Depends(authenticated)])
async def logout(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if principal.actor_type == "user":
        await revoke_all(session, uuid.UUID(principal.actor_id))
        await session.commit()
    return {"ok": True}


@router.get("/me", dependencies=[Depends(authenticated)])
async def me(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = None
    if principal.actor_type == "user":
        user = await session.get(User, uuid.UUID(principal.actor_id))
    return {
        "id": principal.actor_id,
        "actor_type": principal.actor_type,
        "email": principal.email,
        "display_name": principal.display_name,
        "locale": principal.locale,
        "roles": principal.roles,
        "permissions": sorted(principal.permissions),
        "is_controller": principal.is_controller,
        "read_only": principal.read_only,
        "must_change_password": bool(user.must_change_password) if user else False,
        "totp_enabled": bool(user.totp_enabled) if user else False,
        "must_enroll_2fa": principal.must_enroll_2fa,
    }


@router.get("/me/navigation", dependencies=[Depends(authenticated)])
async def navigation(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    registry = request.app.state.registry
    states = await module_states(session, registry, request.app.state.settings)
    items = [
        {
            "key": "dashboard",
            "label_key": "nav.dashboard",
            "path": "/",
            "icon": "home",
            "module": "core",
        }
    ]
    if principal.can("settings.view"):
        items.append(
            {
                "key": "settings",
                "label_key": "nav.settings",
                "path": "/settings",
                "icon": "settings",
                "module": "core",
            }
        )
    for manifest in registry.all():
        state = states.get(manifest.key)
        if not state or not state["available"]:
            continue
        for nav in sorted(manifest.nav, key=lambda n: n.order):
            if nav.perm and not principal.can(nav.perm):
                continue
            items.append(
                {
                    "key": nav.key,
                    "label_key": nav.label_key,
                    "path": nav.path,
                    "icon": nav.icon,
                    "module": manifest.key,
                }
            )
    available = [key for key, state in states.items() if state["available"]]
    return {
        "items": items,
        "modules": available,
        "locale": principal.locale,
        "languages": ["en", "am"],
    }


class ControllerSessionRequest(BaseModel):
    token: str


@router.post("/controller-session", dependencies=[Depends(public_access)])
async def controller_session(
    payload: ControllerSessionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    settings: Settings = request.app.state.settings
    state = await get_license(session)
    public_key = (state.controller_public_key if state else None) or settings.controller_public_key
    if not public_key:
        raise Unauthorized("Controller trust is not configured", message_key="error.controller_trust")
    try:
        claims = verify_payload(payload.token, public_key)
    except LicenseError as exc:
        raise Unauthorized(
            "Invalid controller session", message_key="error.invalid_controller_session"
        ) from exc
    if claims.get("instance_id") and settings.instance_id and claims["instance_id"] != settings.instance_id:
        raise Unauthorized("Token is for another instance", message_key="error.invalid_controller_session")
    actor = Principal(
        actor_id=f"controller:{claims.get('cp_user_id', 'unknown')}",
        actor_type="controller",
        via="controller",
        display_name=f"Controller support ({claims.get('cp_user_id', '')})",
        permissions={"*"},
        is_controller=True,
        read_only=bool(claims.get("read_only")),
        reason=claims.get("reason"),
    )
    await record(
        session,
        action="auth.controller_session",
        module="core",
        entity_type="session",
        actor=actor,
        reason=claims.get("reason"),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    access = create_access_token(
        settings,
        actor.actor_id,
        extra={
            "actor_type": "controller",
            "reason": claims.get("reason"),
            "read_only": actor.read_only,
            "instance_id": claims.get("instance_id"),
        },
    )
    return {
        "access_token": access,
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
        "user": {
            "id": actor.actor_id,
            "display_name": actor.display_name,
            "actor_type": "controller",
            "read_only": actor.read_only,
            "reason": actor.reason,
        },
    }


@router.get("/users", dependencies=[Depends(require("users.view"))])
async def list_users(session: AsyncSession = Depends(get_session)) -> dict:
    users = (await session.execute(select(User).order_by(User.email))).scalars().all()
    return {
        "items": [
            {
                "id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "is_active": user.is_active,
                "locale": user.locale,
            }
            for user in users
        ],
        "next_cursor": None,
    }
