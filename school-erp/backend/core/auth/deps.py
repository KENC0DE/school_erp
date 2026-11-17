"""Request authentication and the single `require()` guard (ARCH §5.3)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import jwt
from app.errors import Forbidden, TOTPEnrollmentRequired, Unauthorized
from app.settings import Settings
from core.auth.principal import Principal
from core.auth.security import decode_access_token
from core.db.deps import get_session
from core.rbac.service import effective_permissions, roles_for_user
from fastapi import Depends, Request
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

bearer = HTTPBearer(auto_error=False)


async def _principal_from_token(
    request: Request,
    token: str,
    session: AsyncSession,
    settings: Settings,
) -> Principal:
    try:
        claims = decode_access_token(settings, token)
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Access token has expired", message_key="error.token_expired") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid access token", message_key="error.invalid_token") from exc

    if claims.get("actor_type") == "controller":
        return Principal(
            actor_id=str(claims.get("sub")),
            actor_type="controller",
            via="controller",
            display_name="Controller support",
            permissions={"*"},
            is_controller=True,
            read_only=bool(claims.get("read_only")),
            reason=claims.get("reason"),
        )

    try:
        user_id = uuid.UUID(str(claims["sub"]))
    except (ValueError, KeyError) as exc:
        raise Unauthorized("Invalid subject", message_key="error.invalid_token") from exc

    from core.auth.models import User

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise Unauthorized("User is not active", message_key="error.user_inactive")

    permissions, scopes = await effective_permissions(session, user.id)
    roles = await roles_for_user(session, user.id)
    return Principal(
        actor_id=str(user.id),
        actor_type="user",
        via="web",
        display_name=user.display_name,
        email=user.email,
        locale=user.locale,
        roles=roles,
        permissions=permissions,
        scopes=scopes,
        session_id=claims.get("sid"),
        must_enroll_2fa=await _must_enroll(session, user),
    )


async def _must_enroll(session: AsyncSession, user: Any) -> bool:
    if user.totp_enabled:
        return False
    from core.auth.service import role_requires_totp

    return await role_requires_totp(session, user.id)


def _bearer_value(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


async def get_current_principal(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Principal:
    token = _bearer_value(request)
    if not token:
        raise Unauthorized("Authentication required", message_key="error.auth_required")
    principal = await _principal_from_token(request, token, session, request.app.state.settings)
    principal.via = request.headers.get("x-client-via", principal.via)
    request.state.principal = principal
    request.state.actor_type = principal.actor_type
    return principal


async def get_optional_principal(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Principal | None:
    token = _bearer_value(request)
    if not token:
        return None
    try:
        return await _principal_from_token(request, token, session, request.app.state.settings)
    except Unauthorized:
        return None


async def authenticated(principal: Principal = Depends(get_current_principal)) -> Principal:
    """A session is required, but no specific permission. Used by /me and similar."""
    return principal


authenticated.__auth_only__ = True  # type: ignore[attr-defined]


def public_access() -> None:
    """Marker dependency for routes that are intentionally public."""


public_access.__public__ = True  # type: ignore[attr-defined]


def authenticated_access() -> None:
    """Marker for routes that only need a session, with no specific permission."""


authenticated_access.__auth_only__ = True  # type: ignore[attr-defined]


def require(permission: str, *, scope: str | None = None) -> Callable[..., Any]:
    """Guard one endpoint. The marker is inspected by the coverage test."""

    async def dependency(
        request: Request,
        principal: Principal = Depends(get_current_principal),
    ) -> Principal:
        if principal.must_enroll_2fa and not request.url.path.startswith("/api/v1/auth/2fa"):
            raise TOTPEnrollmentRequired(
                "Two-factor authentication enrollment is required for your role",
                message_key="error.totp_enrollment_required",
            )
        if principal.is_controller and principal.read_only and request.method not in {"GET", "HEAD"}:
            raise Forbidden(
                "This controller session is read-only",
                message_key="error.read_only_session",
                code="READ_ONLY_SESSION",
            )
        if not principal.can(permission):
            raise Forbidden(
                f"Missing permission {permission}",
                message_key="error.permission_denied",
                details={"permission": permission},
            )
        request.state.permission = permission
        return principal

    dependency.__permission__ = permission  # type: ignore[attr-defined]
    dependency.__scope__ = scope  # type: ignore[attr-defined]
    return dependency
