"""Cookie + double-submit CSRF session endpoints for the web app (P1-04).

The access token stays in memory/local storage (short-lived); the refresh token
lives in an HttpOnly cookie scoped to this router. Every refresh must echo the
readable CSRF cookie in ``X-CSRF-Token``.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from app.errors import CSRFFailed, Unauthorized
from app.settings import Settings
from core.auth.deps import get_current_principal, public_access
from core.auth.principal import Principal
from core.auth.schemas import (
    LoginRequest,
    WebSessionResponse,
)
from core.auth.service import authenticate, revoke_family, rotate_refresh
from core.db.deps import get_session
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth/web", tags=["auth"])

REFRESH_COOKIE = "erp_refresh"
CSRF_COOKIE = "erp_csrf"
COOKIE_PATH = "/api/v1/auth/web"
CSRF_HEADER = "x-csrf-token"


def _secure(settings: Settings) -> bool:
    return settings.web_cookie_secure or settings.is_production


def _set_session_cookies(response: Response, settings: Settings, refresh_token: str) -> None:
    csrf = secrets.token_urlsafe(24)
    max_age = settings.refresh_token_days * 86_400
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=max_age,
        path=COOKIE_PATH,
        httponly=True,
        secure=_secure(settings),
        samesite="lax",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=max_age,
        path=COOKIE_PATH,
        httponly=False,
        secure=_secure(settings),
        samesite="lax",
    )


def _clear_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH, secure=_secure(settings))
    response.delete_cookie(CSRF_COOKIE, path=COOKIE_PATH, secure=_secure(settings))


def _check_csrf(request: Request) -> None:
    cookie = request.cookies.get(CSRF_COOKIE) or ""
    header = request.headers.get(CSRF_HEADER) or ""
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise CSRFFailed("The CSRF token is missing or invalid", message_key="error.csrf_failed")


@router.post("/login", response_model=WebSessionResponse, dependencies=[Depends(public_access)])
async def web_login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> WebSessionResponse:
    settings: Settings = request.app.state.settings
    issued = await authenticate(session, settings, payload, request)
    _set_session_cookies(response, settings, issued.tokens.refresh_token)
    return WebSessionResponse(
        access_token=issued.tokens.access_token,
        expires_in=issued.tokens.expires_in,
        user=issued.user,
    )


@router.post("/refresh", response_model=WebSessionResponse, dependencies=[Depends(public_access)])
async def web_refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> WebSessionResponse:
    settings: Settings = request.app.state.settings
    _check_csrf(request)
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise Unauthorized("No web session cookie", message_key="error.invalid_refresh")
    issued = await rotate_refresh(session, settings, raw, request)
    _set_session_cookies(response, settings, issued.tokens.refresh_token)
    return WebSessionResponse(
        access_token=issued.tokens.access_token,
        expires_in=issued.tokens.expires_in,
        user=issued.user,
    )


@router.post("/logout")
async def web_logout(
    request: Request,
    response: Response,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    settings: Settings = request.app.state.settings
    if principal.session_id:
        await revoke_family(session, uuid.UUID(principal.actor_id), uuid.UUID(principal.session_id))
        await session.commit()
    _clear_cookies(response, settings)
    return {"ok": True, "at": datetime.now(UTC).isoformat()}


__all__ = ["CSRF_COOKIE", "CSRF_HEADER", "REFRESH_COOKIE", "router"]
