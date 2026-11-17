"""First-run instance setup: school profile, branding and the first admin (P1-24).

The wizard is only available while the instance has no users at all. That keeps
the public endpoint from becoming an open admin-creation window: once the first
Super Admin exists, ``POST /setup`` refuses even if the caller knows the URL.
"""

from __future__ import annotations

import base64
import binascii
import re
import uuid
from typing import Any, Literal

from app.errors import Conflict, NotFound, ValidationFailed
from app.settings import Settings
from fastapi import Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.service import chain_lock_statement, record
from core.auth.models import User
from core.auth.passwords import validate_password
from core.auth.principal import Principal
from core.auth.security import hash_password
from core.auth.service import build_user_out, issue_tokens
from core.files.models import StoredFile
from core.files.service import upload_file
from core.files.storage import Storage
from core.files.validation import ValidatedUpload, validate_upload
from core.rbac.models import Role, UserRole
from core.rbac.service import effective_permissions
from core.settings.core_schema import CoreSettings
from core.settings.service import effective_map, set_setting
from core.themes.service import available_themes, set_default_theme, theme_detail

CORE = "core"
SETUP_LOCK_KEY = 0x53455455  # "SETU"
LANGUAGES = ("en", "am")
CALENDARS = ("ethiopian", "gregorian", "both")
LOGO_MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
DATA_URL_RE = re.compile(r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\s]+)$")


class SchoolSetup(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    timezone: str = Field(default="Africa/Addis_Ababa", min_length=1, max_length=80)
    calendar: Literal["ethiopian", "gregorian", "both"] = "both"
    default_language: Literal["en", "am"] = "en"
    enabled_languages: list[Literal["en", "am"]] = Field(default_factory=lambda: ["en", "am"], min_length=1)
    first_level: int = Field(default=0, ge=0, le=12)
    last_level: int = Field(default=12, ge=0, le=12)
    theme: str = Field(default="default", min_length=1, max_length=60)
    # Optional data URL: the setup endpoint is public, so uploads are inline
    # rather than through the permission-guarded files route.
    logo: str | None = None


class AdminSetup(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    locale: Literal["en", "am"] | None = None


class SetupRequest(BaseModel):
    school: SchoolSetup
    admin: AdminSetup


async def user_count(session: AsyncSession) -> int:
    return int((await session.execute(select(func.count()).select_from(User))).scalar_one())


async def _assert_open(session: AsyncSession) -> None:
    if await user_count(session) > 0:
        raise Conflict(
            "This instance has already been set up",
            code="SETUP_COMPLETE",
            message_key="error.setup_complete",
        )


async def _lock_setup(session: AsyncSession) -> None:
    """Serialise concurrent setup attempts on PostgreSQL.

    SQLite serialises writers at commit time already, and in practice the
    wizard submits once; the lock simply closes the theoretical race where two
    requests both observe zero users and create two first admins.
    """
    statement = chain_lock_statement(session.get_bind().dialect.name)
    if statement is not None:
        await session.execute(text(statement), {"key": SETUP_LOCK_KEY})


async def _logo_url(
    session: AsyncSession, storage: Storage, settings: Settings, file_id: str | None
) -> str | None:
    if not file_id:
        return None
    try:
        row = await session.get(StoredFile, uuid.UUID(file_id))
    except ValueError:
        return None
    if row is None:
        return None
    return storage.signed_url(row.object_key, expires_in=settings.storage_signed_url_seconds).url


async def setup_status(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
) -> dict[str, Any]:
    count = await user_count(session)
    profile = await effective_map(session, CORE, CoreSettings)
    themes = await available_themes(session)
    return {
        "required": count == 0,
        "completed": count > 0,
        "school": {
            "name": profile["school_profile.name"].value,
            "timezone": profile["school_profile.timezone"].value,
            "calendar": profile["school_profile.calendar"].value,
            "default_language": profile["school_profile.default_language"].value,
            "enabled_languages": profile["school_profile.enabled_languages"].value,
            "first_level": profile["academic_scope.first_level"].value,
            "last_level": profile["academic_scope.last_level"].value,
            "theme": profile["branding.theme"].value,
            "logo_url": await _logo_url(
                session,
                storage,
                settings,
                profile["school_profile.logo_file_id"].value,
            ),
        },
        "languages": list(LANGUAGES),
        "calendars": list(CALENDARS),
        "themes": [
            {"key": item["key"], "name": item["name"], "is_default": item["is_default"]} for item in themes
        ],
        "limits": {"logo_max_bytes": settings.storage_max_upload_bytes},
    }


def _decode_logo(logo: str | None, settings: Settings) -> ValidatedUpload | None:
    if logo is None or not logo.strip():
        return None
    match = DATA_URL_RE.match(logo.strip())
    if match is None:
        raise ValidationFailed(
            "The logo must be a PNG, JPEG or WebP image",
            message_key="error.setup_logo",
            details={"expected": sorted(LOGO_MIME_EXTENSIONS)},
        )
    mime, encoded = match.group(1), match.group(2)
    try:
        data = base64.b64decode(re.sub(r"\s+", "", encoded), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationFailed(
            "The logo data is not valid base64",
            message_key="error.setup_logo",
        ) from exc
    filename = f"school-logo{LOGO_MIME_EXTENSIONS[mime]}"
    return validate_upload(
        filename,
        mime,
        data,
        max_bytes=settings.storage_max_upload_bytes,
    )


def _validate_options(payload: SetupRequest) -> None:
    school = payload.school
    if school.default_language not in school.enabled_languages:
        raise ValidationFailed(
            "The default language must also be enabled",
            message_key="error.setup_language",
            details={
                "default_language": school.default_language,
                "enabled_languages": school.enabled_languages,
            },
        )
    if school.first_level > school.last_level:
        raise ValidationFailed(
            "The first grade level cannot be above the last",
            message_key="error.setup_grade_scope",
            details={
                "first_level": school.first_level,
                "last_level": school.last_level,
            },
        )


async def complete_setup(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    payload: SetupRequest,
    *,
    request: Request | None = None,
) -> dict[str, Any]:
    await _lock_setup(session)
    await _assert_open(session)
    _validate_options(payload)
    validate_password(payload.admin.password)

    # Validate the theme before creating anything so a bad choice cannot leave
    # a half-configured instance behind.
    detail = await theme_detail(session, payload.school.theme)
    if detail["issues"]:
        raise ValidationFailed(
            "That theme cannot be used as the school default",
            message_key="error.theme.invalid",
            details={"issues": detail["issues"]},
        )

    logo = _decode_logo(payload.school.logo, settings)

    role = (
        await session.execute(select(Role).where(Role.key == "super_admin", Role.is_active.is_(True)))
    ).scalar_one_or_none()
    if role is None:
        raise NotFound(
            "The Super Admin role is missing; restart the instance to bootstrap it",
            message_key="error.role_not_found",
        )

    email = str(payload.admin.email).lower()
    if (await session.execute(select(User).where(User.email == email))).scalar_one_or_none():
        raise Conflict("That email is already in use", message_key="error.email_exists")
    if payload.admin.phone:
        phone_taken = (
            await session.execute(select(User).where(User.phone == payload.admin.phone))
        ).scalar_one_or_none()
        if phone_taken is not None:
            raise Conflict("That phone number is already in use", message_key="error.phone_exists")

    user = User(
        email=email,
        phone=payload.admin.phone,
        display_name=payload.admin.display_name,
        password_hash=hash_password(payload.admin.password),
        locale=payload.admin.locale or payload.school.default_language,
        is_active=True,
        must_change_password=False,
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.flush()

    permissions, scopes = await effective_permissions(session, user.id)
    principal = Principal(
        actor_id=str(user.id),
        actor_type="user",
        via="web",
        display_name=user.display_name,
        email=user.email,
        locale=user.locale,
        roles=["super_admin"],
        permissions=permissions,
        scopes=scopes,
    )

    logo_id: str | None = None
    logo_url: str | None = None
    if logo is not None:
        stored = await upload_file(
            session,
            principal,
            storage,
            settings,
            filename=logo.filename,
            content_type=logo.mime,
            data=logo.data,
            owner_entity_type="school",
            owner_entity_id="profile",
            is_private=False,
            commit=False,
            thumbnail=False,
        )
        logo_id = stored["id"]
        logo_url = stored["url"]

    values: dict[str, Any] = {
        "school_profile.name": payload.school.name,
        "school_profile.default_language": payload.school.default_language,
        "school_profile.enabled_languages": list(payload.school.enabled_languages),
        "school_profile.timezone": payload.school.timezone,
        "school_profile.calendar": payload.school.calendar,
        "school_profile.logo_file_id": logo_id,
        "academic_scope.first_level": payload.school.first_level,
        "academic_scope.last_level": payload.school.last_level,
        "branding.theme": payload.school.theme,
    }
    applied: dict[str, Any] = {}
    for key, value in values.items():
        effective = await set_setting(session, CORE, CoreSettings, key, value, actor=principal)
        applied[key] = effective.value

    await set_default_theme(session, principal, payload.school.theme, commit=False)
    await record(
        session,
        action="auth.user.created",
        module="core",
        entity_type="user",
        entity_id=str(user.id),
        after={
            "email": user.email,
            "display_name": user.display_name,
            "roles": ["super_admin"],
            "via": "setup",
        },
        actor=principal,
        via=principal.via,
        ip=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    await record(
        session,
        action="setup.complete",
        module="core",
        entity_type="instance",
        entity_id="setup",
        after={
            "school": applied,
            "logo_file_id": logo_id,
            "theme": payload.school.theme,
            "admin_id": str(user.id),
        },
        actor=principal,
        via=principal.via,
        ip=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )

    tokens, _ = await issue_tokens(session, settings, user, request=request)
    await session.commit()

    return {
        "tokens": tokens.model_dump(),
        "user": (await build_user_out(session, user)).model_dump(),
        "school": applied,
        "logo_url": logo_url,
        "theme": payload.school.theme,
    }


__all__ = [
    "AdminSetup",
    "CALENDARS",
    "LANGUAGES",
    "SchoolSetup",
    "SetupRequest",
    "complete_setup",
    "setup_status",
    "user_count",
]
