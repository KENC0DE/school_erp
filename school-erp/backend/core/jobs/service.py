"""Background job listing, user-safe errors and retry (P1-25)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from app.settings import Settings
from core.audit.service import record
from core.auth.principal import Principal
from core.events.models import Job
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("erp.jobs")

# Kinds the UI may retry, with the payload field each task needs.
RETRY_TASKS: dict[str, str | None] = {
    "ping": None,
    "files.thumbnail": "file_id",
    "notifications.delivery": "notification_id",
    "assessment.recalculate": "structure_id",
}

# Failed tasks store the real exception for operators. The API only ever
# returns one of these translation keys so internal paths, SQL or provider
# responses cannot leak to a user.
ERROR_KEYS: dict[str, str] = {
    "files.thumbnail": "jobs.error.thumbnail",
    "notifications.delivery": "jobs.error.notification",
    "ping": "jobs.error.generic",
    "assessment.recalculate": "jobs.error.assessment",
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _error_key(job: Job) -> str | None:
    if job.status != "failed":
        return None
    return ERROR_KEYS.get(job.kind, "jobs.error.generic")


def _view(job: Job) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress,
        "error_key": _error_key(job),
        "retryable": job.status == "failed" and job.kind in RETRY_TASKS,
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at),
        "finished_at": _iso(job.finished_at),
    }


async def get_job(session: AsyncSession, job_id: str) -> Job:
    try:
        identifier = uuid.UUID(job_id)
    except ValueError as exc:
        raise NotFound("No background job with that id", message_key="error.job_not_found") from exc
    row = await session.get(Job, identifier)
    if row is None:
        raise NotFound("No background job with that id", message_key="error.job_not_found")
    return row


async def list_jobs(
    session: AsyncSession,
    *,
    status: str | None = None,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    stmt = select(Job).order_by(Job.created_at.desc(), Job.id.desc())
    if status:
        stmt = stmt.where(Job.status == status)
    if kind:
        stmt = stmt.where(Job.kind == kind)
    rows = (await session.execute(stmt.offset(max(0, offset)).limit(max(1, min(limit, 100))))).scalars().all()
    return {"items": [_view(row) for row in rows], "next_cursor": None}


async def reset_failed_deliveries(session: AsyncSession, notification_id: str) -> int:
    """Put a notification's failed channels back in the delivery queue."""
    from core.notifications.service import reset_failed_deliveries as reset

    return await reset(session, notification_id)


def _retry_args(job: Job) -> list[str]:
    field = RETRY_TASKS[job.kind]
    if field is None:
        return [str(job.id)]
    payload = job.payload or {}
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationFailed(
            "This job is missing the information needed to retry it",
            message_key="error.job_invalid_payload",
            details={"kind": job.kind, "field": field},
        )
    return [str(job.id), value]


async def _enqueue(job: Job) -> None:
    args = _retry_args(job)
    if job.kind == "ping":
        from core.events.celery_app import ping

        await asyncio.to_thread(ping.delay, *args)
    elif job.kind == "files.thumbnail":
        from core.events.celery_app import files_thumbnail_task

        await asyncio.to_thread(files_thumbnail_task.delay, *args)
    elif job.kind == "notifications.delivery":
        from core.events.celery_app import notifications_delivery_task

        await asyncio.to_thread(notifications_delivery_task.delay, *args)
    elif job.kind == "assessment.recalculate":
        from core.events.celery_app import assessment_recalculate_task

        await asyncio.to_thread(assessment_recalculate_task.delay, *args)


async def retry_job(
    session: AsyncSession,
    principal: Principal,
    job_id: str,
    *,
    settings: Settings,
) -> dict[str, Any]:
    job = await get_job(session, job_id)
    before = _view(job)
    if job.status != "failed":
        raise Conflict(
            "Only a failed job can be retried",
            code="JOB_NOT_FAILED",
            message_key="error.job_not_failed",
            details={"status": job.status},
        )
    if job.kind not in RETRY_TASKS:
        raise ValidationFailed(
            "This kind of job cannot be retried from the interface",
            message_key="error.job_not_retryable",
            details={"kind": job.kind},
        )
    # Validate the payload before touching the row so a missing id cannot make
    # the job look queued and then never run.
    _retry_args(job)

    if job.kind == "notifications.delivery":
        payload = job.payload or {}
        await reset_failed_deliveries(session, str(payload.get("notification_id")))

    job.status = "queued"
    job.progress = 0
    job.error = None
    job.result = None
    job.started_at = None
    job.finished_at = None
    await session.flush()
    after = _view(job)

    await record(
        session,
        action="job.retry",
        module="core",
        entity_type="job",
        entity_id=str(job.id),
        before=before,
        after=after,
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    await session.refresh(job)

    # Tests and brokers are deliberately decoupled: no test run talks to Redis.
    if settings.app_env != "test":
        try:
            await _enqueue(job)
        except Exception as exc:  # pragma: no cover - broker outages are operational
            logger.warning("job retry enqueue failed for %s: %s", job.id, exc)

    return _view(job)


__all__ = [
    "ERROR_KEYS",
    "RETRY_TASKS",
    "get_job",
    "list_jobs",
    "reset_failed_deliveries",
    "retry_job",
]
