from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from app.settings import get_settings
from celery import Celery

logger = logging.getLogger("erp.worker")


def build_celery() -> Celery:
    settings = get_settings()
    app = Celery("erp", broker=settings.redis_url, backend=settings.redis_url)
    app.conf.update(
        task_always_eager=settings.dev_mode and settings.app_env == "test",
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        beat_schedule={
            "heartbeat": {"task": "erp.heartbeat", "schedule": float(settings.heartbeat_seconds)},
            "verify-audit-chain": {
                "task": "erp.verify_audit_chain",
                "schedule": 60 * 60 * 24,
            },
        },
    )
    return app


celery_app = build_celery()


async def _run_in_session(coro_factory):  # type: ignore[no-untyped-def]
    import os

    from core.db.session import Database

    settings = get_settings()
    url = os.environ.get("ERP_DATABASE_URL") or settings.database_url
    database = Database(url)
    try:
        async with database.session() as session:
            return await coro_factory(session)
    finally:
        await database.dispose()


async def _mark_job(
    job_id: str, status: str, *, result: dict | None = None, error: str | None = None
) -> None:
    from core.events.models import Job

    async def work(session):
        job = await session.get(Job, uuid.UUID(job_id))
        if job is None:
            return
        job.status = status
        if status == "running":
            job.started_at = datetime.now(UTC)
            job.progress = 10
        if status in {"succeeded", "failed"}:
            job.finished_at = datetime.now(UTC)
            job.progress = 100 if status == "succeeded" else job.progress
            job.result = result
            job.error = error
        await session.commit()

    await _run_in_session(work)


@celery_app.task(name="erp.ping")
def ping(job_id: str) -> dict:
    asyncio.run(_mark_job(job_id, "running"))
    asyncio.run(_mark_job(job_id, "succeeded", result={"pong": True}))
    return {"job_id": job_id, "pong": True}


@celery_app.task(name="erp.heartbeat")
def heartbeat_task() -> dict:
    from core.controller_link.service import heartbeat

    async def work(session):
        return await heartbeat(session)

    try:
        return asyncio.run(_run_in_session(work)) or {"ok": True}
    except Exception as exc:  # pragma: no cover - offline controller is normal
        logger.warning("heartbeat failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@celery_app.task(name="erp.verify_audit_chain")
def verify_audit_chain() -> dict:
    from core.audit.service import verify_chain

    async def work(session):
        return await verify_chain(session)

    return asyncio.run(_run_in_session(work))
