from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from erp_shared.license import sign_payload
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from controller_api.deps import CPPrincipal, current_user, get_session
from controller_api.directory import new_school_code, token_hash
from controller_api.errors import conflict, forbidden, not_found
from controller_api.keys import ensure_signing_keys
from controller_api.licenses import LICENSABLE_MODULES, issue_license
from controller_api.models import CPAudit, EnrollmentToken, LicenseRecord, School, SupportSession

router = APIRouter(prefix="/controller/v1", tags=["controller-schools"])


class SchoolCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    school_code: str | None = Field(default=None, max_length=20)
    api_base_url: str = "http://localhost:8000"
    logo_url: str | None = None
    plan: str = "standard"
    modules: list[str] | None = None


class SchoolUpdate(BaseModel):
    name: str | None = None
    api_base_url: str | None = None
    logo_url: str | None = None
    status: str | None = None
    min_app_version: str | None = None
    plan: str | None = None


class ModuleToggle(BaseModel):
    key: str
    enabled: bool


class SupportSessionRequest(BaseModel):
    reason: str = Field(min_length=4, max_length=1000)
    read_only: bool = False


def serialize_school(school: School) -> dict:
    return {
        "id": school.id,
        "name": school.name,
        "school_code": school.school_code,
        "api_base_url": school.api_base_url,
        "logo_url": school.logo_url,
        "status": school.status,
        "min_app_version": school.min_app_version,
        "plan": school.plan,
        "size_profile": school.size_profile,
        "modules": list(school.modules or []),
        "app_version": school.app_version,
        "enrolled": bool(school.instance_public_key),
        "created_at": school.created_at.isoformat() if school.created_at else None,
    }


async def _audit(session: AsyncSession, principal: CPPrincipal | None, action: str, **kwargs) -> None:
    session.add(
        CPAudit(
            actor_id=principal.id if principal else None,
            action=action,
            entity_type=kwargs.get("entity_type"),
            entity_id=kwargs.get("entity_id"),
            details=kwargs.get("details"),
        )
    )


@router.get("/schools")
async def list_schools(
    principal: CPPrincipal = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict:
    rows = (await session.execute(select(School).order_by(School.name))).scalars().all()
    return {"items": [serialize_school(row) for row in rows], "next_cursor": None}


@router.post("/schools", status_code=201)
async def create_school(
    payload: SchoolCreate,
    request: Request,
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not principal.is_owner:
        raise forbidden("Only the platform owner can create schools")
    code = (payload.school_code or new_school_code()).upper()
    existing = (await session.execute(select(School).where(School.school_code == code))).scalar_one_or_none()
    if existing is not None:
        raise conflict("School code is already in use")
    school = School(
        name=payload.name,
        school_code=code,
        api_base_url=payload.api_base_url,
        logo_url=payload.logo_url,
        plan=payload.plan,
        modules=payload.modules if payload.modules is not None else list(LICENSABLE_MODULES),
    )
    session.add(school)
    await session.flush()
    raw_token = secrets.token_urlsafe(32)
    session.add(
        EnrollmentToken(
            school_id=school.id,
            token_hash=token_hash(raw_token),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
    )
    await _audit(
        session,
        principal,
        "schools.create",
        entity_type="school",
        entity_id=school.id,
        details={"name": school.name},
    )
    await session.commit()
    return {**serialize_school(school), "enrollment_token": raw_token, "enrollment_token_once": True}


@router.get("/schools/{school_id}")
async def get_school(
    school_id: str,
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    school = await session.get(School, school_id)
    if school is None:
        raise not_found("School not found")
    return serialize_school(school)


@router.patch("/schools/{school_id}")
async def update_school(
    school_id: str,
    payload: SchoolUpdate,
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not principal.can_write():
        raise forbidden("Your role cannot change schools")
    school = await session.get(School, school_id)
    if school is None:
        raise not_found("School not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        if field == "status" and value not in {"active", "grace", "suspended"}:
            raise conflict("Unknown status")
        setattr(school, field, value)
    await _audit(
        session,
        principal,
        "schools.update",
        entity_type="school",
        entity_id=school.id,
        details=payload.model_dump(exclude_none=True),
    )
    await session.commit()
    return serialize_school(school)


@router.patch("/schools/{school_id}/modules")
async def toggle_module(
    school_id: str,
    payload: ModuleToggle,
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not principal.can_write():
        raise forbidden("Your role cannot change modules")
    school = await session.get(School, school_id)
    if school is None:
        raise not_found("School not found")
    modules = set(school.modules or [])
    if payload.enabled:
        if payload.key not in LICENSABLE_MODULES:
            raise conflict(f"Unknown licensable module {payload.key}")
        modules.add(payload.key)
    else:
        modules.discard(payload.key)
    school.modules = sorted(modules)
    await _audit(
        session,
        principal,
        "schools.modules.toggle",
        entity_type="school",
        entity_id=school.id,
        details={"key": payload.key, "enabled": payload.enabled},
    )
    await session.commit()
    return serialize_school(school)


@router.post("/schools/{school_id}/support-session")
async def support_session(
    school_id: str,
    payload: SupportSessionRequest,
    request: Request,
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not principal.can_write():
        raise forbidden("Your role cannot open support sessions")
    school = await session.get(School, school_id)
    if school is None:
        raise not_found("School not found")
    settings = request.app.state.settings
    license_key, _ = await ensure_signing_keys(session, settings)
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.support_session_minutes)
    claims = {
        "instance_id": school.id,
        "cp_user_id": principal.id,
        "reason": payload.reason,
        "read_only": payload.read_only,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int(expires_at.timestamp()),
        "aud": "school-instance",
    }
    token = sign_payload(license_key.private_pem, claims, kid=license_key.kid)
    session.add(
        SupportSession(
            school_id=school.id,
            cp_user_id=principal.id,
            reason=payload.reason,
            read_only=payload.read_only,
            expires_at=expires_at,
        )
    )
    await _audit(
        session,
        principal,
        "support_session.open",
        entity_type="school",
        entity_id=school.id,
        details={"reason": payload.reason, "read_only": payload.read_only},
    )
    await session.commit()
    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "read_only": payload.read_only,
        "reason": payload.reason,
        "instance_id": school.id,
    }


@router.get("/schools/{school_id}/license")
async def school_license(
    school_id: str,
    principal: CPPrincipal = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    school = await session.get(School, school_id)
    if school is None:
        raise not_found("School not found")
    row = (
        (
            await session.execute(
                select(LicenseRecord)
                .where(LicenseRecord.school_id == school_id)
                .order_by(LicenseRecord.issued_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    return {
        "school_id": school_id,
        "issued_at": row.issued_at.isoformat() if row and row.issued_at else None,
        "valid_until": row.valid_until.isoformat() if row else None,
        "status": row.status if row else school.status,
        "modules": list(row.modules) if row else list(school.modules or []),
    }


async def issue_for_school(session: AsyncSession, school: School, settings) -> str:
    license_key, _ = await ensure_signing_keys(session, settings)
    return await issue_license(session, school, license_key, settings)
