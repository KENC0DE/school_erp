"""Teaching assignments: teacher, subject, section and academic year.

Assignments are the source of the ``assigned_subjects`` and ``own_class`` data
scopes. Every write is audited and soft-deleted assignments can be restored.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import get_including_deleted, restore, soft_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear, GradeLevel, Section, Subject
from modules.staff.common import MODULE, live_staff
from modules.staff.models import StaffProfile, StaffTeachingAssignment
from modules.staff.schemas import (
    TeachingAssignmentInput,
    TeachingAssignmentList,
    TeachingAssignmentOut,
    TeachingAssignmentUpdate,
)

State = dict[str, Any]


def _state(row: StaffTeachingAssignment) -> State:
    return {
        "staff_id": str(row.staff_id),
        "year_id": str(row.year_id),
        "section_id": str(row.section_id),
        "subject_id": str(row.subject_id),
        "notes": row.notes,
        "row_version": row.row_version,
        "deleted": row.deleted_at is not None,
    }


async def _live_year(session: AsyncSession, year_id: uuid.UUID) -> AcademicYear:
    row = (
        await session.execute(
            select(AcademicYear).where(
                AcademicYear.id == year_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The academic year does not exist",
            message_key="error.academics.year_not_found",
        )
    return row


async def _live_section(session: AsyncSession, section_id: uuid.UUID) -> Section:
    row = (
        await session.execute(
            select(Section).where(
                Section.id == section_id,
                Section.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The section does not exist",
            message_key="error.academics.section_not_found",
        )
    return row


async def _live_subject(session: AsyncSession, subject_id: uuid.UUID) -> Subject:
    row = (
        await session.execute(
            select(Subject).where(
                Subject.id == subject_id,
                Subject.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The subject does not exist",
            message_key="error.academics.subject_not_found",
        )
    return row


async def _validate_target(
    session: AsyncSession,
    *,
    year_id: uuid.UUID,
    section_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> tuple[AcademicYear, Section, Subject]:
    year = await _live_year(session, year_id)
    section = await _live_section(session, section_id)
    if section.year_id != year.id:
        raise ValidationFailed(
            "The section does not belong to that academic year",
            message_key="staff.error.assignment_section_year",
            details={"section_id": str(section.id), "year_id": str(year.id)},
        )
    subject = await _live_subject(session, subject_id)
    if not subject.is_active:
        raise ValidationFailed(
            "An inactive subject cannot be assigned",
            message_key="staff.error.assignment_subject_inactive",
            details={"subject_id": str(subject.id)},
        )
    return year, section, subject


async def _assert_unique(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID,
    year_id: uuid.UUID,
    section_id: uuid.UUID,
    subject_id: uuid.UUID,
    current_id: uuid.UUID | None = None,
) -> None:
    stmt = select(StaffTeachingAssignment.id).where(
        StaffTeachingAssignment.staff_id == staff_id,
        StaffTeachingAssignment.year_id == year_id,
        StaffTeachingAssignment.section_id == section_id,
        StaffTeachingAssignment.subject_id == subject_id,
        StaffTeachingAssignment.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(StaffTeachingAssignment.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "That teacher is already assigned to this subject and section",
            message_key="staff.error.assignment_exists",
            details={
                "staff_id": str(staff_id),
                "section_id": str(section_id),
                "subject_id": str(subject_id),
                "year_id": str(year_id),
            },
        )


async def _live_assignment(
    session: AsyncSession, staff_id: uuid.UUID, assignment_id: uuid.UUID
) -> StaffTeachingAssignment:
    row = (
        await session.execute(
            select(StaffTeachingAssignment).where(
                StaffTeachingAssignment.id == assignment_id,
                StaffTeachingAssignment.staff_id == staff_id,
                StaffTeachingAssignment.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The teaching assignment does not exist",
            message_key="staff.error.assignment_not_found",
        )
    return row


async def _maps(
    session: AsyncSession,
    rows: list[StaffTeachingAssignment],
) -> tuple[
    dict[uuid.UUID, StaffProfile],
    dict[uuid.UUID, AcademicYear],
    dict[uuid.UUID, Section],
    dict[uuid.UUID, Subject],
    dict[uuid.UUID, GradeLevel],
]:
    staff_ids = {row.staff_id for row in rows}
    year_ids = {row.year_id for row in rows}
    section_ids = {row.section_id for row in rows}
    subject_ids = {row.subject_id for row in rows}
    staff = {
        row.id: row
        for row in (await session.execute(select(StaffProfile).where(StaffProfile.id.in_(staff_ids))))
        .scalars()
        .all()
    }
    years = {
        row.id: row
        for row in (await session.execute(select(AcademicYear).where(AcademicYear.id.in_(year_ids))))
        .scalars()
        .all()
    }
    sections = {
        row.id: row
        for row in (await session.execute(select(Section).where(Section.id.in_(section_ids)))).scalars().all()
    }
    level_ids = {row.level_id for row in sections.values()}
    levels = {
        row.id: row
        for row in (await session.execute(select(GradeLevel).where(GradeLevel.id.in_(level_ids))))
        .scalars()
        .all()
    }
    subjects = {
        row.id: row
        for row in (await session.execute(select(Subject).where(Subject.id.in_(subject_ids)))).scalars().all()
    }
    return staff, years, sections, subjects, levels


def _out(
    row: StaffTeachingAssignment,
    *,
    staff: StaffProfile,
    year: AcademicYear,
    section: Section,
    subject: Subject,
    level: GradeLevel,
) -> TeachingAssignmentOut:
    return TeachingAssignmentOut(
        id=str(row.id),
        staff_id=str(staff.id),
        staff_number=staff.staff_number,
        year_id=str(year.id),
        year_code=year.code,
        section_id=str(section.id),
        section_code=section.code,
        section_name=section.name,
        level_id=str(level.id),
        level_code=level.code,
        level_name=level.name,
        subject_id=str(subject.id),
        subject_code=subject.code,
        subject_name=subject.name,
        notes=row.notes,
        row_version=row.row_version,
    )


async def _out_one(session: AsyncSession, row: StaffTeachingAssignment) -> TeachingAssignmentOut:
    staff, years, sections, subjects, levels = await _maps(session, [row])
    return _out(
        row,
        staff=staff[row.staff_id],
        year=years[row.year_id],
        section=sections[row.section_id],
        subject=subjects[row.subject_id],
        level=levels[sections[row.section_id].level_id],
    )


async def list_assignments(
    session: AsyncSession,
    *,
    staff_id: uuid.UUID | None = None,
    year_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
) -> TeachingAssignmentList:
    stmt = select(StaffTeachingAssignment).where(StaffTeachingAssignment.deleted_at.is_(None))
    if staff_id is not None:
        await live_staff(session, staff_id)
        stmt = stmt.where(StaffTeachingAssignment.staff_id == staff_id)
    if year_id is not None:
        stmt = stmt.where(StaffTeachingAssignment.year_id == year_id)
    if section_id is not None:
        stmt = stmt.where(StaffTeachingAssignment.section_id == section_id)
    if subject_id is not None:
        stmt = stmt.where(StaffTeachingAssignment.subject_id == subject_id)
    rows = (
        (
            await session.execute(
                stmt.order_by(
                    StaffTeachingAssignment.year_id,
                    StaffTeachingAssignment.section_id,
                    StaffTeachingAssignment.subject_id,
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return TeachingAssignmentList(items=[], total=0)
    staff, years, sections, subjects, levels = await _maps(session, list(rows))
    items = [
        _out(
            row,
            staff=staff[row.staff_id],
            year=years[row.year_id],
            section=sections[row.section_id],
            subject=subjects[row.subject_id],
            level=levels[sections[row.section_id].level_id],
        )
        for row in rows
    ]
    return TeachingAssignmentList(items=items, total=len(items))


async def create_assignment(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    data: TeachingAssignmentInput,
    *,
    via: str = "api",
) -> TeachingAssignmentOut:
    staff = await live_staff(session, staff_id)
    if staff.status == "terminated":
        raise ValidationFailed(
            "A terminated staff member cannot receive teaching assignments",
            message_key="staff.error.assignment_staff_terminated",
        )
    await _validate_target(
        session,
        year_id=data.year_id,
        section_id=data.section_id,
        subject_id=data.subject_id,
    )
    await _assert_unique(
        session,
        staff_id=staff.id,
        year_id=data.year_id,
        section_id=data.section_id,
        subject_id=data.subject_id,
    )
    row = StaffTeachingAssignment(staff_id=staff.id, **data.model_dump())
    session.add(row)
    await session.flush()
    await record(
        session,
        action="staff.teaching.create",
        module=MODULE,
        entity_type="staff_teaching_assignment",
        entity_id=str(row.id),
        after=_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await _out_one(session, row)


async def update_assignment(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
    data: TeachingAssignmentUpdate,
    *,
    via: str = "api",
) -> TeachingAssignmentOut:
    row = await _live_assignment(session, staff_id, assignment_id)
    before = _state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    year_id = payload.get("year_id", row.year_id)
    section_id = payload.get("section_id", row.section_id)
    subject_id = payload.get("subject_id", row.subject_id)
    await _validate_target(
        session,
        year_id=year_id,
        section_id=section_id,
        subject_id=subject_id,
    )
    await _assert_unique(
        session,
        staff_id=row.staff_id,
        year_id=year_id,
        section_id=section_id,
        subject_id=subject_id,
        current_id=row.id,
    )

    changes: dict[str, Any] = {}
    for key, value in payload.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changes[key] = value
    if changes:
        row.row_version = (row.row_version or 0) + 1
    await session.flush()
    if changes:
        await record(
            session,
            action="staff.teaching.update",
            module=MODULE,
            entity_type="staff_teaching_assignment",
            entity_id=str(row.id),
            before=before,
            after=_state(row),
            actor=principal,
            via=via,
        )
    await session.commit()
    return await _out_one(session, row)


async def delete_assignment(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await _live_assignment(session, staff_id, assignment_id)
    changed = await soft_delete(
        session,
        row,
        action="staff.teaching.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="staff_teaching_assignment",
    )
    await session.flush()
    await session.commit()
    return {"id": str(row.id), "deleted": bool(changed), "row_version": row.row_version}


async def restore_assignment(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> TeachingAssignmentOut:
    await live_staff(session, staff_id)
    row = await get_including_deleted(session, StaffTeachingAssignment, assignment_id)
    if row is None or row.staff_id != staff_id:
        raise NotFound(
            "The teaching assignment does not exist",
            message_key="staff.error.assignment_not_found",
        )
    await _validate_target(
        session,
        year_id=row.year_id,
        section_id=row.section_id,
        subject_id=row.subject_id,
    )
    await _assert_unique(
        session,
        staff_id=row.staff_id,
        year_id=row.year_id,
        section_id=row.section_id,
        subject_id=row.subject_id,
        current_id=row.id,
    )
    await restore(
        session,
        row,
        action="staff.teaching.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="staff_teaching_assignment",
    )
    await session.flush()
    await session.commit()
    return await _out_one(session, row)


__all__ = [
    "create_assignment",
    "delete_assignment",
    "list_assignments",
    "restore_assignment",
    "update_assignment",
]
