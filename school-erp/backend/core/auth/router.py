"""Authentication API (ARCH §5.2, P1-04)."""

from __future__ import annotations

import secrets
import uuid

from app.errors import Conflict, Forbidden, NotFound, Unauthorized, ValidationFailed
from app.settings import Settings
from core.audit.service import record
from core.auth.deps import authenticated, get_current_principal, public_access, require
from core.auth.models import User
from core.auth.principal import Principal
from core.auth.recovery import send_reset_link
from core.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserUpdate,
)
from core.auth.security import create_access_token, hash_password
from core.auth.service import authenticate, revoke_all, rotate_refresh
from core.db.deps import get_session
from core.modules.licensing import get_license, module_states
from core.rbac.models import Role, RolePermission, UserRole
from core.rbac.service import assert_can_grant, roles_for_user
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
        "theme_key": user.theme_key if user else None,
        "theme_mode": user.theme_mode if user else "light",
        "roles": principal.roles,
        "permissions": sorted(principal.permissions),
        "scopes": {key: sorted(value) for key, value in sorted(principal.scopes.items())},
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
    if principal.can("users.view") or principal.can("users.manage"):
        items.append(
            {
                "key": "users",
                "label_key": "nav.users",
                "path": "/users",
                "icon": "users",
                "module": "core",
            }
        )
    if principal.can("roles.view") or principal.can("roles.manage"):
        items.append(
            {
                "key": "roles",
                "label_key": "nav.roles",
                "path": "/roles",
                "icon": "shield",
                "module": "core",
            }
        )
    if principal.can("audit.activity.view"):
        items.append(
            {
                "key": "activity",
                "label_key": "nav.activity",
                "path": "/activity",
                "icon": "history",
                "module": "core",
            }
        )
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
    if principal.can("modules.view") or principal.can("modules.manage"):
        items.append(
            {
                "key": "modules",
                "label_key": "nav.modules",
                "path": "/settings/modules",
                "icon": "box",
                "module": "core",
            }
        )
    if principal.can("i18n.view") or principal.can("i18n.manage"):
        items.append(
            {
                "key": "languages",
                "label_key": "nav.languages",
                "path": "/settings/languages",
                "icon": "languages",
                "module": "core",
            }
        )
    if principal.can("themes.view") or principal.can("themes.manage"):
        items.append(
            {
                "key": "themes",
                "label_key": "nav.themes",
                "path": "/settings/themes",
                "icon": "palette",
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


async def _get_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("The user does not exist", message_key="error.user_not_found")
    return user


async def _user_payload(session: AsyncSession, user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "phone": user.phone,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "locale": user.locale,
        "must_change_password": user.must_change_password,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "roles": await roles_for_user(session, user.id),
    }


def _user_meta(request: Request) -> dict:
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


@router.get("/users", dependencies=[Depends(require("users.view"))])
async def list_users(session: AsyncSession = Depends(get_session)) -> dict:
    users = (await session.execute(select(User).order_by(User.email))).scalars().all()
    role_rows = (
        await session.execute(
            select(UserRole.user_id, Role.key)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.is_active.is_(True))
            .order_by(Role.key)
        )
    ).all()
    by_user: dict[uuid.UUID, list[str]] = {}
    for user_id, role_key in role_rows:
        by_user.setdefault(user_id, []).append(role_key)
    return {
        "items": [
            {
                "id": str(user.id),
                "email": user.email,
                "phone": user.phone,
                "display_name": user.display_name,
                "is_active": user.is_active,
                "locale": user.locale,
                "must_change_password": user.must_change_password,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                "locked_until": user.locked_until.isoformat() if user.locked_until else None,
                "roles": by_user.get(user.id, []),
            }
            for user in users
        ],
        "next_cursor": None,
    }


@router.post("/users", status_code=201, dependencies=[Depends(require("users.manage"))])
async def invite_user(
    payload: UserCreate,
    request: Request,
    principal: Principal = Depends(require("users.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create an account and email a single-use password link."""
    settings: Settings = request.app.state.settings
    email = payload.email.lower()
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise Conflict("That email is already in use", message_key="error.email_exists")
    if payload.phone:
        phone_taken = (
            await session.execute(select(User).where(User.phone == payload.phone))
        ).scalar_one_or_none()
        if phone_taken is not None:
            raise Conflict("That phone number is already in use", message_key="error.phone_exists")

    roles: list[Role] = []
    if payload.role_ids:
        if not principal.can("roles.manage"):
            raise Forbidden(
                "Assigning roles requires roles.manage",
                message_key="error.permission_denied",
                details={"permission": "roles.manage"},
            )
        try:
            role_ids = [uuid.UUID(value) for value in payload.role_ids]
        except ValueError as exc:
            raise ValidationFailed(
                "One of the roles does not exist",
                code="UNKNOWN_ROLE",
                message_key="error.role_not_found",
            ) from exc
        roles = list(
            (await session.execute(select(Role).where(Role.id.in_(role_ids), Role.is_active.is_(True))))
            .scalars()
            .all()
        )
        if len(roles) != len(role_ids):
            raise Conflict("One of the roles is missing or deactivated", message_key="error.role_inactive")
        pairs = (
            await session.execute(
                select(RolePermission.permission, RolePermission.scope).where(
                    RolePermission.role_id.in_(role_ids)
                )
            )
        ).all()
        assert_can_grant(principal, [(permission, scope) for permission, scope in pairs])

    user = User(
        email=email,
        phone=payload.phone,
        display_name=payload.display_name,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        locale=payload.locale,
        is_active=True,
        must_change_password=True,
    )
    session.add(user)
    await session.flush()
    for role in roles:
        session.add(UserRole(user_id=user.id, role_id=role.id))
    link = await send_reset_link(
        session,
        settings,
        user,
        request,
        subject="You are invited to School ERP",
        intro=(
            "An account has been created for you. Choose your password with the "
            "single-use link below, then sign in."
        ),
    )
    await record(
        session,
        action="auth.user.invited",
        module="core",
        entity_type="user",
        entity_id=str(user.id),
        after={"email": user.email, "roles": [role.key for role in roles]},
        actor=principal,
        via=principal.via,
        **_user_meta(request),
    )
    await session.commit()
    body = await _user_payload(session, user)
    body["invitation_sent"] = True
    if settings.dev_mode:
        body["invitation_link"] = link
    return body


@router.patch("/users/{user_id}", dependencies=[Depends(require("users.manage"))])
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    principal: Principal = Depends(require("users.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await _get_user(session, user_id)
    changes = payload.model_dump(exclude_unset=True)

    if changes.get("is_active") is False and principal.actor_id == str(user.id):
        raise Conflict(
            "You cannot deactivate your own account",
            code="CANNOT_DEACTIVATE_SELF",
            message_key="error.cannot_deactivate_self",
        )
    phone = changes.get("phone")
    if phone:
        taken = (
            await session.execute(select(User).where(User.phone == phone, User.id != user.id))
        ).scalar_one_or_none()
        if taken is not None:
            raise Conflict("That phone number is already in use", message_key="error.phone_exists")

    before = {
        "display_name": user.display_name,
        "phone": user.phone,
        "locale": user.locale,
        "is_active": user.is_active,
    }
    for key, value in changes.items():
        setattr(user, key, value)
    if changes.get("is_active") is False:
        await revoke_all(session, user.id)
        user.locked_until = None
        user.failed_login_count = 0
    await record(
        session,
        action="auth.user.updated",
        module="core",
        entity_type="user",
        entity_id=str(user.id),
        before=before,
        after={
            "display_name": user.display_name,
            "phone": user.phone,
            "locale": user.locale,
            "is_active": user.is_active,
        },
        actor=principal,
        via=principal.via,
        **_user_meta(request),
    )
    await session.commit()
    return await _user_payload(session, user)
