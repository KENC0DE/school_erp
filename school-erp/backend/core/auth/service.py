"""Authentication service: lockout, tokens, rotation and sessions (P1-04)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.errors import AccountLocked, TOTPInvalid, TOTPRequired, Unauthorized
from app.settings import Settings
from core.auth.crypto import decrypt_secret
from core.auth.models import RefreshToken, User
from core.auth.rate_limit import login_limiter
from core.auth.schemas import TokenPair, UserOut
from core.auth.security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    refresh_expiry,
    verify_password,
)
from core.auth.totp import consume_recovery_code, verify_code
from core.modules.licensing import get_license
from core.rbac.models import Role, UserRole
from core.rbac.service import effective_permissions, roles_for_user
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class IssuedSession:
    tokens: TokenPair
    user: UserOut
    family_id: uuid.UUID


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


async def role_requires_totp(session: AsyncSession, user_id: uuid.UUID) -> bool:
    row = (
        await session.execute(
            select(Role.require_totp)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, Role.require_totp.is_(True))
            .limit(1)
        )
    ).first()
    return row is not None


async def build_user_out(session: AsyncSession, user: User, *, must_enroll: bool = False) -> UserOut:
    permissions, _ = await effective_permissions(session, user.id)
    return UserOut(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        locale=user.locale,
        roles=await roles_for_user(session, user.id),
        permissions=sorted(permissions),
        must_change_password=bool(user.must_change_password),
        totp_enabled=bool(user.totp_enabled),
        must_enroll_2fa=must_enroll,
    )


async def issue_tokens(
    session: AsyncSession,
    settings: Settings,
    user: User,
    *,
    family_id: uuid.UUID | None = None,
    request: Request | None = None,
    extra: dict[str, Any] | None = None,
) -> tuple[TokenPair, uuid.UUID]:
    family = family_id or uuid.uuid4()
    claims = {"sid": str(family)}
    claims.update(extra or {})
    access = create_access_token(settings, str(user.id), extra=claims)
    raw_refresh = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            family_id=family,
            expires_at=refresh_expiry(settings),
            ip=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
        )
    )
    return (
        TokenPair(
            access_token=access,
            refresh_token=raw_refresh,
            expires_in=settings.access_token_minutes * 60,
        ),
        family,
    )


async def _register_failure(session: AsyncSession, settings: Settings, user: User, now: datetime) -> None:
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= settings.login_max_failures:
        user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
    await session.commit()


async def authenticate(
    session: AsyncSession,
    settings: Settings,
    payload: Any,
    request: Request,
) -> IssuedSession:
    ip = request.client.host if request.client else "unknown"
    login_limiter.hit(
        f"login:{ip}",
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window_seconds,
    )
    now = datetime.now(UTC)
    user = (
        await session.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()

    locked_until = _aware(user.locked_until) if user else None
    if user is not None and locked_until is not None:
        if locked_until > now:
            raise AccountLocked(
                "This account is temporarily locked",
                message_key="error.account_locked",
                details={"locked_until": locked_until.isoformat()},
            )
        user.failed_login_count = 0
        user.locked_until = None

    valid = user is not None and user.is_active and verify_password(payload.password, user.password_hash)
    if not valid:
        if user is not None and user.is_active:
            await _register_failure(session, settings, user, now)
        raise Unauthorized("Email or password is incorrect", message_key="auth.invalid")

    assert user is not None
    if user.totp_enabled:
        if payload.totp_code:
            secret = decrypt_secret(settings, user.totp_secret)
            if not secret or not verify_code(secret, payload.totp_code, window=settings.totp_window):
                await _register_failure(session, settings, user, now)
                raise TOTPInvalid("The verification code is invalid", message_key="error.totp_invalid")
        elif payload.recovery_code:
            remaining = consume_recovery_code(list(user.totp_recovery_hashes or []), payload.recovery_code)
            if remaining is None:
                await _register_failure(session, settings, user, now)
                raise TOTPInvalid("The recovery code is invalid", message_key="error.totp_invalid")
            user.totp_recovery_hashes = remaining
        else:
            raise TOTPRequired(
                "A verification code is required",
                message_key="error.totp_required",
            )

    license_state = await get_license(session)
    if license_state is not None and license_state.status == "suspended":
        permissions, _ = await effective_permissions(session, user.id)
        if "*" not in permissions:
            raise Unauthorized(
                "This school is suspended. Contact the platform owner.",
                message_key="error.instance_suspended",
                status_code=403,
            )

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    tokens, family = await issue_tokens(session, settings, user, request=request)
    must_enroll = await role_requires_totp(session, user.id) and not user.totp_enabled
    user_out = await build_user_out(session, user, must_enroll=must_enroll)
    await session.commit()
    return IssuedSession(tokens=tokens, user=user_out, family_id=family)


async def rotate_refresh(
    session: AsyncSession, settings: Settings, raw_token: str, request: Request
) -> IssuedSession:
    row = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        )
    ).scalar_one_or_none()
    if row is None:
        raise Unauthorized("Invalid refresh token", message_key="error.invalid_refresh")
    now = datetime.now(UTC)
    expires_at = _aware(row.expires_at)
    if row.revoked_at is not None or (expires_at is not None and expires_at < now):
        raise Unauthorized("Refresh token has expired", message_key="error.refresh_expired")
    if row.used_at is not None:
        await revoke_family(session, row.user_id, row.family_id)
        await session.commit()
        raise Unauthorized("Refresh token reuse detected", message_key="error.refresh_reuse")
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise Unauthorized("User is inactive", message_key="error.user_inactive")
    row.used_at = now
    tokens, family = await issue_tokens(session, settings, user, family_id=row.family_id, request=request)
    row.replaced_by = hash_refresh_token(tokens.refresh_token)
    must_enroll = await role_requires_totp(session, user.id) and not user.totp_enabled
    user_out = await build_user_out(session, user, must_enroll=must_enroll)
    await session.commit()
    return IssuedSession(tokens=tokens, user=user_out, family_id=family)


async def revoke_family(session: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID) -> bool:
    rows = (
        (
            await session.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.family_id == family_id,
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
    return bool(rows)


async def revoke_all(
    session: AsyncSession, user_id: uuid.UUID, *, except_family: uuid.UUID | None = None
) -> int:
    rows = (
        (
            await session.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    count = 0
    for row in rows:
        if except_family is not None and row.family_id == except_family:
            continue
        row.revoked_at = now
        count += 1
    return count


async def list_sessions(
    session: AsyncSession, user_id: uuid.UUID, current_family: str | None
) -> list[dict[str, Any]]:
    rows = (
        (await session.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))).scalars().all()
    )
    now = datetime.now(UTC)
    families: dict[uuid.UUID, list[RefreshToken]] = {}
    for row in rows:
        families.setdefault(row.family_id, []).append(row)

    items: list[dict[str, Any]] = []
    for family_id, group in families.items():
        active = [
            row
            for row in group
            if row.revoked_at is None and (_aware(row.expires_at) or now) >= now and row.used_at is None
        ]
        if not active:
            continue
        newest = max(active, key=lambda row: _aware(row.created_at) or now)
        started = min(
            (_aware(row.created_at) for row in group if row.created_at is not None),
            default=now,
        )
        items.append(
            {
                "id": str(family_id),
                "created_at": started.isoformat() if started else None,
                "expires_at": (_aware(newest.expires_at) or now).isoformat(),
                "ip": newest.ip,
                "user_agent": newest.user_agent,
                "current": str(family_id) == current_family,
            }
        )
    items.sort(key=lambda item: item["created_at"] or "", reverse=True)
    return items


__all__ = [
    "IssuedSession",
    "build_user_out",
    "authenticate",
    "issue_tokens",
    "list_sessions",
    "revoke_all",
    "revoke_family",
    "role_requires_totp",
    "rotate_refresh",
]
