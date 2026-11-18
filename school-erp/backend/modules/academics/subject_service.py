"""Subjects and their per-level assignment (ARCH §9.1)."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import get_including_deleted, restore, soft_delete
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics import service as catalog
from modules.academics.models import GradeLevel, LevelSubject, Subject
from modules.academics.subject_schemas import (
    LevelSubjectOut,
    LevelSubjectReplace,
    LevelSubjectsOut,
    SubjectCreate,
    SubjectList,
    SubjectOut,
    SubjectUpdate,
)

MODULE = "academics"


def _subject_state(subject: Subject) -> dict[str, Any]:
    return {
        "code": subject.code,
        "name": subject.name,
        "name_am": subject.name_am,
        "sort_order": subject.sort_order,
        "is_active": subject.is_active,
        "row_version": subject.row_version,
        "deleted": subject.deleted_at is not None,
    }


def _subject_out(subject: Subject) -> SubjectOut:
    return SubjectOut(
        id=str(subject.id),
        code=subject.code,
        name=subject.name,
        name_am=subject.name_am,
        sort_order=subject.sort_order,
        is_active=subject.is_active,
        row_version=subject.row_version,
    )


async def _live_subject(session: AsyncSession, subject_id: uuid.UUID) -> Subject:
    subject = (await session.execute(select(Subject).where(Subject.id == subject_id))).scalar_one_or_none()
    if subject is None:
        raise NotFound(
            "The subject does not exist",
            message_key="error.academics.subject_not_found",
        )
    return subject


async def _assert_code_free(session: AsyncSession, code: str, *, current_id: uuid.UUID | None = None) -> None:
    stmt = select(Subject.id).where(Subject.code == code)
    if current_id is not None:
        stmt = stmt.where(Subject.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "A subject with that code already exists",
            message_key="error.academics.subject_code_taken",
            details={"code": code},
        )


async def _next_order(session: AsyncSession) -> int:
    current = (await session.execute(select(func.max(Subject.sort_order)))).scalar_one_or_none()
    return int(current) + 1 if current is not None else 0


async def list_subjects(
    session: AsyncSession,
    *,
    include_inactive: bool = False,
) -> SubjectList:
    stmt = select(Subject)
    if not include_inactive:
        stmt = stmt.where(Subject.is_active.is_(True))
    subjects = (await session.execute(stmt.order_by(Subject.sort_order, Subject.name))).scalars().all()
    items = [_subject_out(subject) for subject in subjects]
    return SubjectList(items=items, total=len(items))


async def get_subject(session: AsyncSession, subject_id: uuid.UUID) -> SubjectOut:
    return _subject_out(await _live_subject(session, subject_id))


async def create_subject(
    session: AsyncSession,
    principal: Principal,
    data: SubjectCreate,
    *,
    via: str = "api",
) -> SubjectOut:
    await _assert_code_free(session, data.code)
    subject = Subject(
        code=data.code,
        name=data.name,
        name_am=data.name_am,
        sort_order=data.sort_order if data.sort_order is not None else await _next_order(session),
        is_active=data.is_active,
    )
    session.add(subject)
    await session.flush()
    await record(
        session,
        action="academics.subjects.create",
        module=MODULE,
        entity_type="academic_subject",
        entity_id=str(subject.id),
        after=_subject_state(subject),
        actor=principal,
        via=via,
    )
    return _subject_out(subject)


async def update_subject(
    session: AsyncSession,
    principal: Principal,
    subject_id: uuid.UUID,
    data: SubjectUpdate,
    *,
    via: str = "api",
    reason: str | None = None,
) -> SubjectOut:
    subject = await _live_subject(session, subject_id)
    before = _subject_state(subject)
    ensure_row_version(subject, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    changes: dict[str, Any] = {}
    for key in ("name", "name_am", "sort_order", "is_active"):
        if key not in payload:
            continue
        value = payload[key]
        if value is None and key != "name_am":
            continue
        if getattr(subject, key) != value:
            setattr(subject, key, value)
            changes[key] = value
    if changes:
        subject.row_version = (subject.row_version or 0) + 1
    await session.flush()
    if changes:
        await record(
            session,
            action="academics.subjects.update",
            module=MODULE,
            entity_type="academic_subject",
            entity_id=str(subject.id),
            before=before,
            after=_subject_state(subject),
            actor=principal,
            reason=reason,
            via=via,
        )
    return _subject_out(subject)


async def delete_subject(
    session: AsyncSession,
    principal: Principal,
    subject_id: uuid.UUID,
    *,
    row_version: int | None = None,
    reason: str | None = None,
    via: str = "api",
) -> SubjectOut:
    subject = await _live_subject(session, subject_id)
    if row_version is not None:
        ensure_row_version(subject, row_version, current_state=_subject_state(subject))
    await soft_delete(
        session,
        subject,
        action="academics.subjects.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="academic_subject",
    )
    await session.flush()
    return _subject_out(subject)


async def restore_subject(
    session: AsyncSession,
    principal: Principal,
    subject_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> SubjectOut:
    subject = await get_including_deleted(session, Subject, subject_id)
    if subject is None:
        raise NotFound(
            "The subject does not exist",
            message_key="error.academics.subject_not_found",
        )
    await _assert_code_free(session, subject.code, current_id=subject.id)
    await restore(
        session,
        subject,
        action="academics.subjects.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="academic_subject",
    )
    await session.flush()
    return _subject_out(subject)


async def _assignment_rows(session: AsyncSession, level_id: uuid.UUID) -> list[tuple[LevelSubject, Subject]]:
    rows = (
        await session.execute(
            select(LevelSubject, Subject)
            .join(Subject, Subject.id == LevelSubject.subject_id)
            .where(LevelSubject.level_id == level_id)
            .order_by(Subject.sort_order, Subject.name)
        )
    ).all()
    return [(row[0], row[1]) for row in rows]


async def level_subjects(session: AsyncSession, level_id: uuid.UUID) -> LevelSubjectsOut:
    level: GradeLevel = await catalog.scoped_level(session, level_id)
    rows = await _assignment_rows(session, level.id)
    items = [
        LevelSubjectOut(
            subject_id=str(subject.id),
            code=subject.code,
            name=subject.name,
            name_am=subject.name_am,
            credit=assignment.credit,
            is_active=subject.is_active,
        )
        for assignment, subject in rows
    ]
    return LevelSubjectsOut(
        level_id=str(level.id),
        level_code=level.code,
        items=items,
        total=len(items),
    )


async def replace_level_subjects(
    session: AsyncSession,
    principal: Principal,
    level_id: uuid.UUID,
    data: LevelSubjectReplace,
    *,
    via: str = "api",
) -> LevelSubjectsOut:
    level = await catalog.scoped_level(session, level_id)
    if not level.is_active:
        raise ValidationFailed(
            "An inactive grade level cannot receive subjects",
            message_key="error.academics.level_inactive",
        )
    before = [
        {"subject": subject.code, "credit": assignment.credit}
        for assignment, subject in await _assignment_rows(session, level.id)
    ]
    unique_ids = list(dict.fromkeys(entry.subject_id for entry in data.subjects))
    subjects = {
        subject.id: subject
        for subject in (
            (await session.execute(select(Subject).where(Subject.id.in_(unique_ids)))).scalars().all()
        )
    }
    missing = [str(subject_id) for subject_id in unique_ids if subject_id not in subjects]
    if missing:
        raise ValidationFailed(
            "One or more selected subjects do not exist",
            message_key="error.academics.subject_missing",
            details={"subject_ids": missing},
        )
    inactive = [
        subjects[entry.subject_id].code for entry in data.subjects if not subjects[entry.subject_id].is_active
    ]
    if inactive:
        raise ValidationFailed(
            "Inactive subjects cannot be assigned to a level",
            message_key="error.academics.subject_inactive",
            details={"codes": sorted(set(inactive))},
        )
    credits = {entry.subject_id: entry.credit for entry in data.subjects}
    await session.execute(delete(LevelSubject).where(LevelSubject.level_id == level.id))
    for subject_id in unique_ids:
        session.add(LevelSubject(level_id=level.id, subject_id=subject_id, credit=credits[subject_id]))
    await session.flush()
    after = [
        {"subject": subject.code, "credit": assignment.credit}
        for assignment, subject in await _assignment_rows(session, level.id)
    ]
    if before != after:
        await record(
            session,
            action="academics.subjects.assignments.replace",
            module=MODULE,
            entity_type="academic_level",
            entity_id=str(level.id),
            before={"level": level.code, "subjects": before},
            after={"level": level.code, "subjects": after},
            actor=principal,
            reason=data.reason,
            via=via,
        )
    return await level_subjects(session, level.id)


__all__ = [
    "create_subject",
    "delete_subject",
    "get_subject",
    "level_subjects",
    "list_subjects",
    "replace_level_subjects",
    "restore_subject",
    "update_subject",
]
