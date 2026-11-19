from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from controller_api.deps import get_session
from controller_api.directory import build_directory_record, client_key
from controller_api.errors import not_found, rate_limited
from controller_api.keys import directory_key_set, ensure_signing_keys
from controller_api.models import School

router = APIRouter(prefix="/controller/v1/directory", tags=["controller-directory"])


@router.get("/resolve")
async def resolve(
    request: Request,
    code: str = Query(min_length=2, max_length=20),
    session: AsyncSession = Depends(get_session),
) -> dict:
    limiter = request.app.state.directory_limiter
    if not limiter.allow(client_key(request, code)):
        raise rate_limited("Too many school lookups. Try again shortly.")
    school = (
        await session.execute(select(School).where(School.school_code == code.upper()))
    ).scalar_one_or_none()
    if school is None:
        raise not_found("School not found")
    settings = request.app.state.settings
    _, directory_key = await ensure_signing_keys(session, settings)
    await session.commit()
    return await build_directory_record(school, directory_key)


@router.get("/keys")
async def keys(request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    await ensure_signing_keys(session, request.app.state.settings)
    await session.commit()
    rows = await directory_key_set(session)
    return {"items": [{"kid": row.kid, "public_key": row.public_pem, "active": row.active} for row in rows]}
