from __future__ import annotations

from datetime import UTC, datetime

from erp_shared.audit import compute_hash
from erp_shared.protocol import (
    AuditIngestRequest,
    AuditIngestResponse,
    EnrollRequest,
    EnrollResponse,
    HeartbeatRequest,
    HeartbeatResponse,
)
from erp_shared.signing import verify_detached
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from controller_api.deps import get_session
from controller_api.directory import token_hash
from controller_api.errors import unauthorized
from controller_api.keys import ensure_signing_keys
from controller_api.licenses import issue_license
from controller_api.models import (
    Alert,
    EnrollmentToken,
    Heartbeat,
    School,
    VaultChainHead,
    VaultEntry,
)

router = APIRouter(prefix="/controller/v1", tags=["controller-link"])


@router.post("/enroll", response_model=EnrollResponse)
async def enroll(
    payload: EnrollRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> EnrollResponse:
    settings = request.app.state.settings
    token = (
        await session.execute(
            select(EnrollmentToken).where(EnrollmentToken.token_hash == token_hash(payload.enrollment_token))
        )
    ).scalar_one_or_none()
    if token is None or token.used_at is not None:
        raise unauthorized("Enrollment token is invalid or already used")
    expires_at = token.expires_at if token.expires_at.tzinfo else token.expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        raise unauthorized("Enrollment token has expired")
    school = await session.get(School, token.school_id)
    if school is None:
        raise unauthorized("School not found for this token")
    school.instance_public_key = payload.instance_public_key
    school.app_version = payload.app_version
    if payload.api_base_url:
        school.api_base_url = payload.api_base_url
    token.used_at = datetime.now(UTC)
    license_key, _ = await ensure_signing_keys(session, settings)
    license_token = await issue_license(session, school, license_key, settings)
    await session.commit()
    return EnrollResponse(
        instance_id=school.id,
        license_token=license_token,
        controller_public_key=license_key.public_pem,
        heartbeat_seconds=60,
    )


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    payload: HeartbeatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HeartbeatResponse:
    settings = request.app.state.settings
    school = await session.get(School, payload.instance_id)
    if school is None:
        raise unauthorized("Unknown instance")
    if not school.instance_public_key:
        raise unauthorized("Instance is not enrolled")
    if not verify_detached(school.instance_public_key, payload.model_dump(), payload.signature):
        raise unauthorized("Heartbeat signature is invalid")
    school.app_version = payload.app_version
    school.updated_at = datetime.now(UTC)
    session.add(
        Heartbeat(
            school_id=school.id,
            payload=payload.model_dump(exclude={"signature"}),
        )
    )
    license_key, _ = await ensure_signing_keys(session, settings)
    token = await issue_license(session, school, license_key, settings)
    await session.commit()
    return HeartbeatResponse(
        license_token=token,
        heartbeat_seconds=settings.heartbeat_seconds if hasattr(settings, "heartbeat_seconds") else 60,
    )


@router.post("/audit/ingest", response_model=AuditIngestResponse)
async def audit_ingest(
    payload: AuditIngestRequest,
    session: AsyncSession = Depends(get_session),
) -> AuditIngestResponse:
    school = await session.get(School, payload.instance_id)
    if school is None or not school.instance_public_key:
        raise unauthorized("Unknown instance")
    if not verify_detached(school.instance_public_key, payload.model_dump(), payload.signature):
        raise unauthorized("Audit batch signature is invalid")

    head = await session.get(VaultChainHead, school.id)
    if head is None:
        head = VaultChainHead(school_id=school.id, last_seq=0, last_hash=None)
        session.add(head)
        await session.flush()

    alerts: list[str] = []
    expected_seq = head.last_seq + 1
    running_prev = head.last_hash
    accepted = 0
    for item in sorted(payload.entries, key=lambda e: e.seq):
        chain_ok = True
        if item.seq != expected_seq:
            alerts.append(f"AUDIT_GAP: expected seq {expected_seq}, got {item.seq}")
            chain_ok = False
        computed = compute_hash(item.prev_hash, item.entry)
        if computed != item.hash:
            alerts.append(f"AUDIT_HASH_MISMATCH: seq {item.seq}")
            chain_ok = False
        if item.prev_hash != running_prev:
            alerts.append(f"AUDIT_CHAIN_BREAK: seq {item.seq}")
            chain_ok = False
        exists = (
            await session.execute(
                select(VaultEntry).where(VaultEntry.school_id == school.id, VaultEntry.seq == item.seq)
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(
                VaultEntry(
                    school_id=school.id,
                    seq=item.seq,
                    prev_hash=item.prev_hash,
                    hash=item.hash,
                    entry=item.entry,
                    chain_ok=chain_ok,
                )
            )
            accepted += 1
        running_prev = item.hash
        expected_seq = item.seq + 1
    head.last_seq = max(head.last_seq, expected_seq - 1)
    head.last_hash = running_prev
    for code in alerts:
        session.add(Alert(school_id=school.id, kind=code.split(":")[0], message=code))
    await session.commit()
    return AuditIngestResponse(accepted=accepted, vault_seq=head.last_seq, alerts=alerts)
