from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.events.models import DomainEvent, Job
from sqlalchemy.ext.asyncio import AsyncSession


async def emit(
    session: AsyncSession,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    actor_id: str | None = None,
) -> DomainEvent:
    event = DomainEvent(
        event_type=event_type,
        payload=payload or {},
        actor_id=actor_id,
        occurred_at=datetime.now(UTC),
    )
    session.add(event)
    await session.flush()
    return event


async def create_job(
    session: AsyncSession,
    kind: str,
    payload: dict[str, Any] | None = None,
    *,
    created_by: str | None = None,
) -> Job:
    import uuid

    job = Job(
        kind=kind,
        payload=payload or {},
        status="queued",
        created_by=uuid.UUID(created_by) if created_by else None,
    )
    session.add(job)
    await session.flush()
    return job
