from __future__ import annotations

import uuid

from app.errors import ValidationFailed
from core.auth.deps import authenticated, get_optional_principal, public_access, require
from core.auth.models import User
from core.auth.principal import Principal
from core.db.deps import get_session
from core.themes.importers import ImportedTheme, import_payload
from core.themes.service import (
    active_theme,
    available_themes,
    delete_theme,
    import_theme,
    list_themes,
    mobile_theme,
    preview_import,
    set_default_theme,
    set_user_preference,
    theme_detail,
    update_theme,
)
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/themes", tags=["themes"])


class ThemeImportRequest(BaseModel):
    format: str = Field(pattern="^(css|json|registry)$")
    content: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=120)
    key: str | None = Field(default=None, max_length=60)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class ThemePreviewRequest(BaseModel):
    format: str = Field(pattern="^(css|json|registry)$")
    content: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=120)
    key: str | None = Field(default=None, max_length=60)


class ThemeUpdateRequest(BaseModel):
    row_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    is_default: bool | None = None


class ThemePreferenceRequest(BaseModel):
    theme_key: str | None = Field(default=None, max_length=60)
    mode: str = Field(default="light", pattern="^(light|dark)$")


async def _current_user(principal: Principal | None, session: AsyncSession) -> User | None:
    if principal is None or principal.actor_type != "user":
        return None
    try:
        return await session.get(User, uuid.UUID(principal.actor_id))
    except ValueError:
        return None


async def _preview(payload: ThemePreviewRequest) -> dict:
    try:
        theme: ImportedTheme = await import_payload(
            payload.format, payload.content, name=payload.name, key=payload.key
        )
    except ValidationFailed as exc:
        return {
            "valid": False,
            "issues": [
                {
                    "code": exc.code.lower(),
                    "message": exc.message,
                    "details": exc.details,
                }
            ],
            "warnings": [],
            "fallback": (await _builtin_fallback()),
        }
    return preview_import(theme)


async def _builtin_fallback() -> dict:
    from core.themes.tokens import DEFAULT_THEME

    return {
        "key": DEFAULT_THEME["key"],
        "name": DEFAULT_THEME["name"],
        "tokens": DEFAULT_THEME["tokens"],
        "source": "builtin",
        "fallback": True,
    }


@router.get("/active", dependencies=[Depends(public_access)])
async def active(
    principal: Principal | None = Depends(get_optional_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await active_theme(session, await _current_user(principal, session))


@router.get("/active/mobile", dependencies=[Depends(public_access)])
async def active_mobile(
    mode: str = Query(default="light", pattern="^(light|dark)$"),
    principal: Principal | None = Depends(get_optional_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await mobile_theme(session, await _current_user(principal, session), mode)


@router.get("/available", dependencies=[Depends(authenticated)])
async def available(session: AsyncSession = Depends(get_session)) -> dict:
    return {"items": await available_themes(session)}


@router.get("", dependencies=[Depends(public_access)])
async def list_all(session: AsyncSession = Depends(get_session)) -> dict:
    return {"items": await list_themes(session)}


@router.post("/preview", dependencies=[Depends(require("themes.view"))])
async def preview(payload: ThemePreviewRequest) -> dict:
    return await _preview(payload)


@router.post("/import", status_code=201, dependencies=[Depends(require("themes.manage"))])
async def import_theme_endpoint(
    payload: ThemeImportRequest,
    principal: Principal = Depends(require("themes.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    theme = await import_payload(
        payload.format,
        payload.content,
        name=payload.name,
        key=payload.key,
    )
    return await import_theme(
        session,
        principal,
        theme,
        description=payload.description,
        is_active=payload.is_active,
    )


@router.put("/preference", dependencies=[Depends(authenticated)])
async def save_preference(
    payload: ThemePreferenceRequest,
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await set_user_preference(
        session,
        principal,
        theme_key=payload.theme_key or None,
        mode=payload.mode,
    )


@router.get("/{key}", dependencies=[Depends(require("themes.view"))])
async def detail(key: str, session: AsyncSession = Depends(get_session)) -> dict:
    return await theme_detail(session, key)


@router.patch("/{key}", dependencies=[Depends(require("themes.manage"))])
async def patch_theme(
    key: str,
    payload: ThemeUpdateRequest,
    principal: Principal = Depends(require("themes.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await update_theme(
        session,
        principal,
        key,
        payload.model_dump(exclude_unset=True),
    )


@router.post("/{key}/default", dependencies=[Depends(require("themes.manage"))])
async def make_default(
    key: str,
    principal: Principal = Depends(require("themes.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await set_default_theme(session, principal, key)


@router.delete("/{key}", dependencies=[Depends(require("themes.manage"))])
async def remove_theme(
    key: str,
    principal: Principal = Depends(require("themes.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await delete_theme(session, principal, key)
