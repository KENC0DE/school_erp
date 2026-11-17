from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.errors import Unauthorized
from app.settings import Settings
from core.audit.service import record
from core.auth.deps import authenticated, get_current_principal, public_access, require
from core.auth.models import RefreshToken, User
from core.auth.principal import Principal
from core.auth.security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    refresh_expiry,
    verify_password,
)
from core.db.deps import get_session
from core.modules.licensing import get_license, module_states
from core.rbac.service import effective_permissions, roles_for_user
from erp_shared.license import LicenseError, verify_payload
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    locale: str
    roles: list[str]
    permissions: list[str]


class LoginResponse(BaseModel):
    tokens: TokenPair
    user: UserOut


async def _issue_tokens(
    session: AsyncSession,
    settings: Settings,
    user: User,
    *,
    family_id: uuid.UUID | None = None,
    request: Request | None = None,
) -> TokenPair:
    access = create_access_token(settings, str(user.id))
    raw_refresh = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            family_id=family_id or uuid.uuid4(),
            expires_at=refresh_expiry(settings),
            ip=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )
    )
    return TokenPair(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(public_access)])
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    settings: Settings = request.app.state.settings
    user = (
        await session.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise Unauthorized("Email or password is incorrect", message_key="auth.invalid")
    license_state = await get_license(session)
    if license_state is not None and license_state.status == "suspended":
        permissions, _ = await effective_permissions(session, user.id)
        if "*" not in permissions:
            raise Unauthorized(
                "This school is suspended. Contact the platform owner.",
                message_key="error.instance_suspended",
                status_code=403,
            )
    user.last_login_at = datetime.now(UTC)
    tokens = await _issue_tokens(session, settings, user, request=request)
    permissions, _ = await effective_permissions(session, user.id)
    roles = await roles_for_user(session, user.id)
    await session.commit()
    return LoginResponse(
        tokens=tokens,
        user=UserOut(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            locale=user.locale,
            roles=roles,
            permissions=sorted(permissions),
        ),
    )


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenPair, dependencies=[Depends(public_access)])
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    settings: Settings = request.app.state.settings
    token_hash = hash_refresh_token(payload.refresh_token)
    row = (
        await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if row is None:
        raise Unauthorized("Invalid refresh token", message_key="error.invalid_refresh")
    now = datetime.now(UTC)
    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if row.revoked_at is not None or expires_at < now:
        raise Unauthorized("Refresh token has expired", message_key="error.refresh_expired")
    if row.used_at is not None:
        # Reuse of a rotated token: revoke the whole family.
        family = (
            (await session.execute(select(RefreshToken).where(RefreshToken.family_id == row.family_id)))
            .scalars()
            .all()
        )
        for sibling in family:
            sibling.revoked_at = now
        await session.commit()
        raise Unauthorized("Refresh token reuse detected", message_key="error.refresh_reuse")
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise Unauthorized("User is inactive", message_key="error.user_inactive")
    row.used_at = now
    tokens = await _issue_tokens(session, settings, user, family_id=row.family_id, request=request)
    row.replaced_by = hash_refresh_token(tokens.refresh_token)
    await session.commit()
    return tokens


@router.post("/logout", dependencies=[Depends(authenticated)])
async def logout(
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if principal.actor_type == "user":
        rows = (
            (
                await session.execute(
                    select(RefreshToken).where(
                        RefreshToken.user_id == uuid.UUID(principal.actor_id),
                        RefreshToken.revoked_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        now = datetime.now(UTC)
        for row in rows:
            row.revoked_at = now
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
