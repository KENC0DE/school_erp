"""Academic structure domain events emitted through the transactional outbox.

Closing a term is published as ``term.closed`` so report cards, notifications
and the automation engine can react after the change commits. The event joins
the caller's transaction, so a rolled-back close never leaves a phantom event.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.events.service import emit
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear, Term


async def term_closed(
    session: AsyncSession,
    *,
    year: AcademicYear,
    term: Term,
    actor_id: str | None,
    reason: str | None = None,
) -> None:
    await emit(
        session,
        "term.closed",
        {
            "year_id": str(year.id),
            "year_code": year.code,
            "term_id": str(term.id),
            "term_number": term.number,
            "term_name": term.name,
            "status": term.status,
            "closed_at": datetime.now(UTC).isoformat(),
            "reason": reason,
        },
        actor_id=actor_id,
    )


__all__ = ["term_closed"]
