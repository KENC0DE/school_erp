"""First-run setup API (P1-24).

Both routes are public on purpose: the wizard has to run before any account
exists. The service refuses ``POST`` as soon as one user is present, so the
public surface closes itself after setup.
"""

from __future__ import annotations

from app.settings import Settings
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.deps import public_access
from core.db.deps import get_session
from core.files.deps import get_app_settings, get_storage
from core.files.storage import Storage
from core.setup.service import SetupRequest, complete_setup, setup_status

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/status", dependencies=[Depends(public_access)])
async def status(
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    return await setup_status(session, storage, settings)


@router.post("", dependencies=[Depends(public_access)])
async def complete(
    payload: SetupRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    return await complete_setup(
        session,
        storage,
        settings,
        payload,
        request=request,
    )


__all__ = ["router"]
