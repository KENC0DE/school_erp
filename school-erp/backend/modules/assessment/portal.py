"""The parent and student read model of published results (P4-16).

The only source is ``ResultSnapshot``: a snapshot exists because an authorised
caller published the sheet, and it is immutable. Reading it means a draft,
submitted or approved mark can never reach a portal, and a later scale edit
cannot rewrite history. The account resolves to its own student profiles (or,
for a parent, every linked child) and each payload is narrowed to that child
before it leaves the API.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from core.auth.principal import Principal
from core.people.models import full_name
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.assessment.common import as_utc
from modules.assessment.models import ResultSnapshot
from modules.assessment.schemas import (
    PortalChild,
    PortalResult,
    PortalResults,
    StudentResult,
)
from modules.students.models import StudentEnrollment
from modules.students.portal import portal_students


def _uuid_or_none(value: object) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:  # pragma: no cover - snapshots are written by us
        return None


def _published_at(snapshot: ResultSnapshot) -> datetime:
    value = snapshot.published_at
    return as_utc(value) if value is not None else datetime.min


async def _section_ids(session: AsyncSession, student_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    rows = (
        (
            await session.execute(
                select(StudentEnrollment.section_id).where(
                    StudentEnrollment.student_id.in_(student_ids),
                    StudentEnrollment.section_id.is_not(None),
                    StudentEnrollment.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    return {row for row in rows if row is not None}


def _newest(snapshots: list[ResultSnapshot]) -> list[ResultSnapshot]:
    """The current publish of each section/term/kind, oldest publish dropped."""
    seen: set[tuple[str, uuid.UUID | None, uuid.UUID | None]] = set()
    current: list[ResultSnapshot] = []
    for snapshot in snapshots:
        key = (snapshot.kind, snapshot.section_id, snapshot.term_id)
        if key in seen:
            continue
        seen.add(key)
        current.append(snapshot)
    return current


def _result(
    snapshot: ResultSnapshot,
    entry: dict,
) -> PortalResult:
    payload = snapshot.payload or {}
    student = StudentResult.model_validate(entry)
    # The portal only ever serves published sheets, whatever workflow state the
    # sheet carried when it was snapshotted.
    student = student.model_copy(update={"status": "published"})
    return PortalResult(
        snapshot_id=str(snapshot.id),
        kind="year" if snapshot.kind == "year" else "term",
        year_id=str(snapshot.year_id),
        year_code=str(payload.get("year_code") or ""),
        term_id=str(snapshot.term_id) if snapshot.term_id else None,
        term_name=payload.get("term_name"),
        section_id=str(snapshot.section_id) if snapshot.section_id else "",
        section_code=str(payload.get("section_code") or ""),
        level_name=str(payload.get("level_name") or ""),
        published_at=_published_at(snapshot),
        result=student,
    )


async def my_results(
    session: AsyncSession,
    principal: Principal,
    *,
    year_id: uuid.UUID | None = None,
) -> PortalResults:
    """Published results for the signed-in student or parent."""
    try:
        user_id = uuid.UUID(principal.user_id)
    except ValueError:  # pragma: no cover - API principals are user accounts
        return PortalResults()
    children = await portal_students(session, user_id)
    if not children:
        return PortalResults()

    student_ids = [profile.id for profile, _ in children]
    section_ids = await _section_ids(session, student_ids)
    outputs = {
        profile.id: PortalChild(
            student_id=str(profile.id),
            student_number=profile.student_number,
            student_name=full_name(person),
            student_name_am=full_name(person, "am") or None,
        )
        for profile, person in children
    }
    if not section_ids:
        return PortalResults(children=list(outputs.values()))

    stmt = select(ResultSnapshot).where(
        ResultSnapshot.section_id.in_(section_ids),
        ResultSnapshot.deleted_at.is_(None),
    )
    if year_id is not None:
        stmt = stmt.where(ResultSnapshot.year_id == year_id)
    stmt = stmt.order_by(
        ResultSnapshot.published_at.desc(),
        ResultSnapshot.id.desc(),
    )
    snapshots = (await session.execute(stmt)).scalars().all()

    for snapshot in _newest(list(snapshots)):
        payload = snapshot.payload or {}
        for entry in payload.get("students") or []:
            student_id = _uuid_or_none(entry.get("student_id"))
            child = outputs.get(student_id) if student_id else None
            if child is None:
                continue
            child.results.append(_result(snapshot, entry))

    for child in outputs.values():
        child.results.sort(key=lambda item: item.published_at, reverse=True)
    return PortalResults(children=[child for child in outputs.values() if child.results])


__all__ = ["my_results"]
