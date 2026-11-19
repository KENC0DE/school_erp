"""Assessment domain events emitted through the transactional outbox (P4-09).

The event names and payload shapes live here so submissions, results and the
automation engine cannot drift. Every helper joins the caller's transaction, so
an event is committed with the change that caused it or not at all.
"""

from __future__ import annotations

from core.events.service import emit
from sqlalchemy.ext.asyncio import AsyncSession

from modules.assessment.models import ResultSnapshot, Submission


def _timestamp(value) -> str | None:
    return value.isoformat() if value is not None else None


async def marks_submitted(
    session: AsyncSession,
    *,
    submission: Submission,
    counts: tuple[int, int, int],
    actor_id: str | None,
) -> None:
    assessments, scores, entered = counts
    await emit(
        session,
        "marks.submitted",
        {
            "submission_id": str(submission.id),
            "year_id": str(submission.year_id),
            "term_id": str(submission.term_id),
            "section_id": str(submission.section_id),
            "subject_id": str(submission.subject_id),
            "status": submission.status,
            "assessments": assessments,
            "scores": scores,
            "entered": entered,
            "submitted_at": _timestamp(submission.submitted_at),
            "note": submission.note,
        },
        actor_id=actor_id,
    )


async def marks_published(
    session: AsyncSession,
    *,
    submission: Submission,
    counts: tuple[int, int, int],
    actor_id: str | None,
) -> None:
    assessments, scores, entered = counts
    await emit(
        session,
        "marks.published",
        {
            "submission_id": str(submission.id),
            "year_id": str(submission.year_id),
            "term_id": str(submission.term_id),
            "section_id": str(submission.section_id),
            "subject_id": str(submission.subject_id),
            "status": submission.status,
            "assessments": assessments,
            "scores": scores,
            "entered": entered,
            "published_at": _timestamp(submission.published_at),
        },
        actor_id=actor_id,
    )


async def results_published(
    session: AsyncSession,
    *,
    snapshot: ResultSnapshot,
    actor_id: str | None,
) -> None:
    """A term or year result sheet was published or re-published."""
    students = snapshot.payload.get("students") if isinstance(snapshot.payload, dict) else None
    await emit(
        session,
        "marks.published",
        {
            "snapshot_id": str(snapshot.id),
            "kind": snapshot.kind,
            "year_id": str(snapshot.year_id),
            "term_id": str(snapshot.term_id) if snapshot.term_id else None,
            "section_id": str(snapshot.section_id) if snapshot.section_id else None,
            "students": len(students) if isinstance(students, list) else None,
            "checksum": snapshot.checksum,
            "published_at": _timestamp(snapshot.published_at),
        },
        actor_id=actor_id,
    )


__all__ = ["marks_published", "marks_submitted", "results_published"]
