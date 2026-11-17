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
            "ship-audit": {
                "task": "erp.ship_audit",
                "schedule": float(settings.audit_ship_interval_seconds),
            },
            "verify-audit-chain": {
                "task": "erp.verify_audit_chain",
                "schedule": float(settings.audit_verify_interval_seconds),
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


@celery_app.task(name="erp.files_thumbnail")
def files_thumbnail_task(job_id: str, file_id: str) -> dict:
    asyncio.run(_mark_job(job_id, "running"))

    async def work(session):
        from core.files.service import generate_thumbnail
        from core.files.storage import build_storage

        return await generate_thumbnail(session, build_storage(get_settings()), file_id)

    try:
        result = asyncio.run(_run_in_session(work))
    except Exception as exc:  # pragma: no cover - storage and image failures
        logger.warning("thumbnail failed: %s", exc)
        asyncio.run(_mark_job(job_id, "failed", error="The thumbnail could not be generated"))
        return {"job_id": job_id, "ok": False}
    asyncio.run(_mark_job(job_id, "succeeded", result=result))
    return {"job_id": job_id, "ok": True}


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


@celery_app.task(name="erp.ship_audit")
def ship_audit_task() -> dict:
    from core.controller_link.service import ship_audit

    async def work(session):
        return await ship_audit(session, get_settings())

    try:
        return asyncio.run(_run_in_session(work)) or {"ok": True, "shipped": 0}
    except Exception as exc:  # pragma: no cover - controller outages are normal
        logger.warning("audit shipping failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@celery_app.task(name="erp.verify_audit_chain")
def verify_audit_chain() -> dict:
    from core.audit.service import verify_chain

    async def work(session):
        return await verify_chain(session)

    result = asyncio.run(_run_in_session(work))
    if not result.get("ok"):
        logger.error("audit chain verification failed: %s", result)
    return result
