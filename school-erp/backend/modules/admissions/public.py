"""The optional public application page: tokens, spam checks and intake.

The public form is deliberately small. It exposes only the active fields a
guardian would fill in, issues a short-lived signed token with the form, and
accepts a submission only when the token is old enough, the honeypot is empty
and the client is under the per-IP limit. The actual application is created by
the same service the office uses, so numbering, audit and event behaviour are
identical.
"""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from app.errors import Forbidden, ValidationFailed
from app.settings import Settings
from core.auth.principal import Principal
from core.auth.rate_limit import SlidingWindowLimiter
from core.custom_fields.service import definition_view, definitions_for
from core.people.schemas import PersonInput
from core.settings.core_schema import CoreSettings
from core.settings.service import load_model
from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics import service as catalog
from modules.academics import years as year_service
from modules.admissions import service
from modules.admissions.schemas import AdmissionGuardianInput, ApplicationCreate, ApplicationOut

FORM_TOKEN_TYPE = "admissions_public_form"
FORM_TOKEN_MINUTES = 60
ENTITY = "admission_application"

# Only one public form exists per school process, so a module-level limiter is
# enough. Production can move it to the shared cache with the auth limiters.
public_limiter = SlidingWindowLimiter()


def _public_principal(locale: str = "en") -> Principal:
    return Principal(
        actor_id="public",
        actor_type="system",
        via="web",
        locale=locale,
        roles=[],
        permissions=set(),
    )


def issue_form_token(settings: Settings) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "type": FORM_TOKEN_TYPE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=FORM_TOKEN_MINUTES)).timestamp()),
            "jti": secrets.token_hex(12),
        },
        settings.secret_key,
        algorithm="HS256",
    )


def _read_form_token(settings: Settings, token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            options={"require": ["type", "iat", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise ValidationFailed(
            "The public form expired; reload the page and try again",
            message_key="admissions.error.form_expired",
        ) from exc
    if payload.get("type") != FORM_TOKEN_TYPE:
        raise ValidationFailed(
            "The public form expired; reload the page and try again",
            message_key="admissions.error.form_expired",
        )
    return payload


def _assert_not_too_fast(payload: dict[str, Any], min_seconds: int) -> None:
    issued = int(payload.get("iat", 0))
    if time.time() - issued < min_seconds:
        raise ValidationFailed(
            "The form was submitted too quickly; please try again",
            message_key="admissions.error.too_fast",
        )


class PublicGuardianInput(BaseModel):
    """Public applicants may only describe a new guardian, never link one."""

    model_config = ConfigDict(extra="forbid")

    person: PersonInput
    relationship: str = Field(default="guardian", min_length=1, max_length=40)
    is_primary: bool = False
    can_pickup: bool = True
    wants_account: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class PublicApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form_token: str = Field(min_length=1, max_length=4000)
    # A hidden field no person fills in. Bots that complete every input are
    # rejected without touching the database.
    website: str | None = Field(default=None, max_length=200)
    person: PersonInput
    year_id: uuid.UUID | None = None
    level_id: uuid.UUID
    custom: dict[str, Any] | None = None
    guardians: list[PublicGuardianInput] = Field(default_factory=list, max_length=10)


class PublicOption(BaseModel):
    id: str
    code: str
    name: str


class PublicApplicationOut(BaseModel):
    application_number: str
    full_name: str
    status: Literal["applied"]
    year_code: str | None = None
    level_code: str | None = None


class PublicFormOut(BaseModel):
    enabled: bool
    school_name: str
    form_token: str | None = None
    min_seconds: int = 0
    fields: list[dict[str, Any]] = Field(default_factory=list)
    years: list[PublicOption] = Field(default_factory=list)
    levels: list[PublicOption] = Field(default_factory=list)
    entrance_test_enabled: bool = True
    entrance_test_max_score: int = 100
    entrance_test_pass_score: int | None = None
    require_guardian: bool = True


async def _school_name(session: AsyncSession) -> str:
    try:
        core = await load_model(session, "core", CoreSettings)
    except Exception:  # pragma: no cover - settings exist after setup
        return ""
    return core.school_profile.name


async def form_view(session: AsyncSession, settings: Settings) -> PublicFormOut:
    admission = await service.load_settings(session)
    school_name = await _school_name(session)
    if not admission.form.public_enabled:
        return PublicFormOut(
            enabled=False,
            school_name=school_name,
            entrance_test_enabled=admission.entrance_test.enabled,
            entrance_test_max_score=admission.entrance_test.max_score,
            entrance_test_pass_score=admission.entrance_test.pass_score,
            require_guardian=admission.form.require_guardian,
        )
    principal = _public_principal()
    fields = [
        definition_view(definition)
        for definition in await definitions_for(session, ENTITY, principal=principal, include_hidden=False)
    ]
    years = await year_service.list_years(session)
    levels = await catalog.list_levels(session)
    return PublicFormOut(
        enabled=True,
        school_name=school_name,
        form_token=issue_form_token(settings),
        min_seconds=admission.form.public_min_seconds,
        fields=fields,
        years=[
            PublicOption(id=year.id, code=year.code, name=year.name)
            for year in years.items
            if year.status != "closed"
        ],
        levels=[PublicOption(id=level.id, code=level.code, name=level.name) for level in levels.items],
        entrance_test_enabled=admission.entrance_test.enabled,
        entrance_test_max_score=admission.entrance_test.max_score,
        entrance_test_pass_score=admission.entrance_test.pass_score,
        require_guardian=admission.form.require_guardian,
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client and request.client.host else "unknown"


async def submit_application(
    session: AsyncSession,
    settings: Settings,
    data: PublicApplicationCreate,
    request: Request,
) -> PublicApplicationOut:
    admission = await service.load_settings(session)
    if not admission.form.public_enabled:
        raise Forbidden(
            "The public application page is closed",
            message_key="admissions.error.public_disabled",
        )
    if (data.website or "").strip():
        raise ValidationFailed(
            "The form could not be submitted",
            message_key="admissions.error.spam",
        )

    public_limiter.hit(
        f"admissions-public:{_client_ip(request)}",
        limit=admission.form.public_rate_limit,
        window_seconds=60 * 60,
    )
    token = _read_form_token(settings, data.form_token)
    _assert_not_too_fast(token, admission.form.public_min_seconds)

    principal = _public_principal(await _default_locale(session))
    payload = ApplicationCreate(
        person=data.person,
        year_id=data.year_id,
        level_id=data.level_id,
        custom=data.custom,
        guardians=[
            AdmissionGuardianInput(
                person=guardian.person,
                relationship=guardian.relationship,
                is_primary=guardian.is_primary,
                can_pickup=guardian.can_pickup,
                wants_account=guardian.wants_account,
                notes=guardian.notes,
            )
            for guardian in data.guardians
        ],
        source="public",
    )
    row, _warnings = await service.create_application(session, principal, payload, via="web")
    view: ApplicationOut = await service.application_view(
        session, row, locale=principal.locale, include_guardians=False
    )
    return PublicApplicationOut(
        application_number=view.application_number,
        full_name=view.person.full_name,
        status="applied",
        year_code=view.year_code,
        level_code=view.level_code,
    )


async def _default_locale(session: AsyncSession) -> str:
    try:
        core = await load_model(session, "core", CoreSettings)
    except Exception:  # pragma: no cover - settings exist after setup
        return "en"
    return core.school_profile.default_language


__all__ = [
    "PublicApplicationCreate",
    "PublicApplicationOut",
    "PublicFormOut",
    "form_view",
    "issue_form_token",
    "public_limiter",
    "submit_application",
]
