"""Student domain events emitted through the transactional outbox.

The event names and payload shapes live here so registration, admission
conversion, enrollment and promotion cannot drift. Every helper joins the
caller's transaction: the event is committed with the student change or not at
all.
"""

from __future__ import annotations

from typing import Any

from core.events.service import emit
from sqlalchemy.ext.asyncio import AsyncSession


async def emit_admitted(
    session: AsyncSession,
    *,
    student_id: str,
    student_number: str,
    person_id: str,
    status: str,
    admission_date: str | None,
    actor_id: str | None,
) -> None:
    await emit(
        session,
        "student.admitted",
        {
            "student_id": student_id,
            "student_number": student_number,
            "person_id": person_id,
            "status": status,
            "admission_date": admission_date,
        },
        actor_id=actor_id,
    )


async def emit_enrolled(
    session: AsyncSession,
    *,
    student_id: str,
    enrollment_id: str,
    year_id: str,
    level_id: str,
    section_id: str | None,
    roll_number: str | None,
    status: str,
    actor_id: str | None,
) -> None:
    await emit(
        session,
        "student.enrolled",
        {
            "student_id": student_id,
            "enrollment_id": enrollment_id,
            "year_id": year_id,
            "level_id": level_id,
            "section_id": section_id,
            "roll_number": roll_number,
            "status": status,
        },
        actor_id=actor_id,
    )


async def emit_promoted(
    session: AsyncSession,
    *,
    student_id: str,
    student_number: str,
    action: str,
    status: str,
    source_year_id: str,
    target_year_id: str,
    from_level_id: str,
    to_level_id: str | None,
    target_section_id: str | None,
    effective_date: str,
    actor_id: str | None,
) -> None:
    payload: dict[str, Any] = {
        "student_id": student_id,
        "student_number": student_number,
        "action": action,
        "status": status,
        "source_year_id": source_year_id,
        "target_year_id": target_year_id,
        "from_level_id": from_level_id,
        "to_level_id": to_level_id,
        "target_section_id": target_section_id,
        "effective_date": effective_date,
    }
    await emit(session, "student.promoted", payload, actor_id=actor_id)
