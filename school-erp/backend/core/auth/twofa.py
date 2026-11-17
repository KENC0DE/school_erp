"""TOTP enrollment, confirmation and disablement (P1-04)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.errors import Conflict, Forbidden, NotFound, TOTPInvalid, TOTPRequiredByRole
from app.settings import Settings
from core.audit.service import record
from core.auth.crypto import decrypt_secret, encrypt_secret
from core.auth.deps import authenticated
from core.auth.models import User
from core.auth.principal import Principal
from core.auth.schemas import (
    TOTPConfirmRequest,
    TOTPConfirmResponse,
    TOTPDisableRequest,
    TOTPEnrollResponse,
)
from core.auth.security import verify_password
from core.auth.service import revoke_all, role_requires_totp
from core.auth.totp import (
    generate_secret,
    hash_recovery_code,
    new_recovery_codes,
    provisioning_uri,
    verify_code,
)
from core.db.deps import get_session
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth/2fa", tags=["auth"])


async def _current_user(session: AsyncSession, principal: Principal) -> User:
    if principal.actor_type != "user":
        raise Forbidden(
            "Two-factor authentication belongs to school users",
            message_key="error.permission_denied",
        )
    user = await session.get(User, uuid.UUID(principal.actor_id))
    if user is None:
        raise NotFound("The user does not exist")
    return user


@router.post("/enroll", response_model=TOTPEnrollResponse, dependencies=[Depends(authenticated)])
async def enroll(
    request: Request,
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> TOTPEnrollResponse:
    settings: Settings = request.app.state.settings
    user = await _current_user(session, principal)
    if user.totp_enabled:
        raise Conflict(
            "Two-factor authentication is already enabled",
            message_key="error.totp_already_enabled",
        )
    secret = generate_secret()
    user.totp_secret = encrypt_secret(settings, secret)
    await session.commit()
    return TOTPEnrollResponse(
        secret=secret,
        otpauth_uri=provisioning_uri(secret, user.email, settings.totp_issuer),
        issuer=settings.totp_issuer,
    )


@router.post("/confirm", response_model=TOTPConfirmResponse, dependencies=[Depends(authenticated)])
async def confirm(
    payload: TOTPConfirmRequest,
    request: Request,
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> TOTPConfirmResponse:
    settings: Settings = request.app.state.settings
    user = await _current_user(session, principal)
    secret = decrypt_secret(settings, user.totp_secret)
    if user.totp_enabled or not secret:
        raise Conflict(
            "Start enrollment before confirming",
            message_key="error.totp_not_started",
        )
    if not verify_code(secret, payload.code, window=settings.totp_window):
        raise TOTPInvalid("The verification code is invalid", message_key="error.totp_invalid")
    codes = new_recovery_codes()
    user.totp_enabled = True
    user.totp_confirmed_at = datetime.now(UTC)
    user.totp_recovery_hashes = [hash_recovery_code(code) for code in codes]
    await record(
        session,
        action="auth.totp_enabled",
        module="core",
        entity_type="user",
        entity_id=str(user.id),
        actor=principal,
        via=principal.via,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return TOTPConfirmResponse(recovery_codes=codes)


@router.post("/disable", dependencies=[Depends(authenticated)])
async def disable(
    payload: TOTPDisableRequest,
    request: Request,
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await _current_user(session, principal)
    if not verify_password(payload.password, user.password_hash):
        raise Forbidden("The password is incorrect", message_key="error.invalid_password")
    if await role_requires_totp(session, user.id):
        raise TOTPRequiredByRole(
            "Your role requires two-factor authentication",
            message_key="error.totp_required_by_role",
        )
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_confirmed_at = None
    user.totp_recovery_hashes = None
    await revoke_all(session, user.id)
    await record(
        session,
        action="auth.totp_disabled",
        module="core",
        entity_type="user",
        entity_id=str(user.id),
        actor=principal,
        via=principal.via,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return {"ok": True, "enabled": False}


__all__ = ["router"]
