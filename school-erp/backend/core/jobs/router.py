from __future__ import annotations

from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from core.events.models import Job
from core.events.service import create_job
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", dependencies=[Depends(require("jobs.view"))])
async def list_jobs(session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.execute(select(Job).order_by(Job.created_at.desc()).limit(50))).scalars().all()
    return {
        "items": [
            {
                "id": str(row.id),
                "kind": row.kind,
                "status": row.status,
                "progress": row.progress,
                "error": row.error,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "next_cursor": None,
    }


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
