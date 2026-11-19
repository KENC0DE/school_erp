"""Password reset by email and SMS stub (P1-04)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from app.errors import Unauthorized
from app.settings import Settings
from core.audit.service import record
from core.auth.deps import public_access
from core.auth.models import PasswordResetToken, User
from core.auth.passwords import validate_password
from core.auth.rate_limit import reset_limiter
from core.auth.schemas import ForgotPasswordRequest, ResetPasswordRequest
from core.auth.security import hash_password
from core.auth.service import revoke_all
from core.db.deps import get_session
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def send_reset_link(
    session: AsyncSession,
    settings: Settings,
    user: User,
    request: Request,
    *,
    subject: str,
    intro: str,
) -> str:
    """Create a single-use email link and send it. Returns the link (tests)."""
    raw = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.password_reset_minutes)
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash(raw),
            expires_at=expires_at,
            requested_ip=request.client.host if request.client else None,
            channel="email",
        )
    )
    link = f"{settings.web_base_url}/reset-password?token={raw}"
    body = (
        f"Hello {user.display_name},\n\n"
        f"{intro}\n\n{link}\n\n"
        f"This link expires in {settings.password_reset_minutes} minutes. "
        "If you were not expecting it, you can ignore this message."
    )
    await request.app.state.mailer.send(to=user.email, subject=subject, body=body)
    return link


@router.post("/forgot-password", dependencies=[Depends(public_access)])
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    settings: Settings = request.app.state.settings
    ip = request.client.host if request.client else "unknown"
    reset_limiter.hit(
        f"reset:{ip}",
        limit=settings.password_reset_rate_limit,
        window_seconds=settings.password_reset_window_seconds,
    )
    user = (
        await session.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    # Never reveal whether the address exists.
    if user is None or not user.is_active:
        return {"ok": True}

    raw = secrets.token_urlsafe(32)
    sms_code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.password_reset_minutes)
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash(raw),
            expires_at=expires_at,
            requested_ip=ip,
            channel="email",
        )
    )
    if user.phone:
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=_hash(sms_code),
                expires_at=expires_at,
                requested_ip=ip,
                channel="sms",
            )
        )
    link = f"{settings.web_base_url}/reset-password?token={raw}"
    body = (
        f"Hello {user.display_name},\n\n"
        f"Use this link to choose a new password. It expires in "
        f"{settings.password_reset_minutes} minutes:\n\n{link}\n\n"
        "If you did not request this, you can ignore this message."
    )
    await request.app.state.mailer.send(to=user.email, subject="Reset your School ERP password", body=body)
    if user.phone:
        await request.app.state.sms.send(
            to=user.phone,
            body=(
                f"Your School ERP reset code is {sms_code}. "
                f"It expires in {settings.password_reset_minutes} minutes. "
                "Never share this code."
            ),
        )
    await record(
        session,
        action="auth.password_reset_requested",
        module="core",
        entity_type="user",
        entity_id=str(user.id),
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return {"ok": True}


@router.post("/reset-password", dependencies=[Depends(public_access)])
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    settings: Settings = request.app.state.settings
    ip = request.client.host if request.client else "unknown"
    reset_limiter.hit(
        f"reset-try:{ip}",
        limit=settings.password_reset_rate_limit * 2,
        window_seconds=settings.password_reset_window_seconds,
    )
    validate_password(payload.new_password)
    row = (
        await session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash(payload.token))
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    expires_at = None
    if row is not None:
        expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if row is None or row.used_at is not None or expires_at is None or expires_at < now:
        raise Unauthorized(
            "This reset link is invalid or has expired",
            message_key="error.invalid_reset_token",
        )
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise Unauthorized(
            "This reset link is invalid or has expired",
            message_key="error.invalid_reset_token",
        )
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.failed_login_count = 0
    user.locked_until = None
    # A successful reset invalidates every other outstanding link or code.
    outstanding = (
        (
            await session.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for token in outstanding:
        token.used_at = now
    await revoke_all(session, user.id)
    await record(
        session,
        action="auth.password_reset",
        module="core",
        entity_type="user",
        entity_id=str(user.id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return {"ok": True}


__all__ = ["router"]
