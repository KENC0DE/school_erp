"""Background jobs API: listing, user-safe errors and retry (P1-25)."""

from __future__ import annotations

from app.errors import InvalidFilter
from app.settings import Settings
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from core.events.service import create_job
from core.files.deps import get_app_settings
from core.jobs.service import list_jobs as list_jobs_service
from core.jobs.service import retry_job
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/jobs", tags=["jobs"])

STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")


@router.get("", dependencies=[Depends(require("jobs.view"))])
async def list_jobs(
    status: str | None = Query(default=None),
    kind: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if status is not None and status not in STATUSES:
        raise InvalidFilter(
            "That job status does not exist",
            details={"filter": "status", "allowed": list(STATUSES)},
        )
    return await list_jobs_service(
        session,
        status=status,
        kind=kind,
        limit=limit,
        offset=offset,
    )


@router.post("/{job_id}/retry", dependencies=[Depends(require("jobs.manage"))])
async def retry(
    job_id: str,
    principal: Principal = Depends(require("jobs.manage")),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    return await retry_job(
        session,
        principal,
        job_id,
        settings=settings,
    )


@router.post("/ping", dependencies=[Depends(require("jobs.view"))])
async def ping(
    principal: Principal = Depends(require("jobs.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = await create_job(session, "ping", created_by=principal.actor_id)
    await session.commit()
    import asyncio

    from core.events.celery_app import ping as ping_task

    await asyncio.to_thread(ping_task.delay, str(job.id))
    return {"job_id": str(job.id), "status": "queued"}


__all__ = ["STATUSES", "router"]
