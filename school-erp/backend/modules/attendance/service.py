"""Attendance sessions and records: creation, fast entry, closing and audit.

Every mutation goes through these functions. The natural key (session, student)
keeps one row per student no matter how often an offline client replays its
outbox, and an optional ``row_version`` lets a client refuse to overwrite a row
it has not seen.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from app.errors import Conflict, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.models import User
from core.auth.principal import Principal
from core.events import service as events
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear, LevelSubject, Section
from modules.attendance import scoping, views
from modules.attendance.common import (
    MODULE,
    attendance_settings,
    enrolled_students,
    is_future,
    live_record,
    live_section,
    live_session,
    live_subject,
    live_year,
    record_state,
    session_state,
    utcnow,
)
from modules.attendance.models import AttendanceRecord, AttendanceSession
from modules.attendance.schemas import (
    MODES,
    BulkRecordsInput,
    RecordInput,
    RecordUpdate,
    SessionCreate,
    SessionDetail,
    SessionList,
    SessionQuery,
    SessionUpdate,
)

SORT_COLUMNS = {
    "date": AttendanceSession.date,
    "created_at": AttendanceSession.created_at,
    "status": AttendanceSession.status,
}
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"submitted", "locked"},
    "submitted": {"open", "locked"},
    "locked": {"open"},
}
STATUS_ACTIONS = {
    "submitted": "submit",
    "locked": "lock",
    "open": "reopen",
}


async def _detail(session: AsyncSession, row: AttendanceSession) -> SessionDetail:
    records = list(
        (
            await session.execute(
                select(AttendanceRecord)
                .where(
                    AttendanceRecord.session_id == row.id,
                    AttendanceRecord.deleted_at.is_(None),
                )
                .order_by(AttendanceRecord.created_at, AttendanceRecord.id)
            )
        )
        .scalars()
        .all()
    )
    roster = await enrolled_students(session, row.year_id, row.section_id)
    labels = await views.load_labels(session, [row])
    users = dict(labels.users)
    recorded_by = {record.recorded_by for record in records if record.recorded_by is not None}
    if recorded_by:
        users |= {
            user.id: user.display_name
            for user in (await session.execute(select(User).where(User.id.in_(recorded_by)))).scalars().all()
        }
    return views.detail_out(row, labels, records, roster, users)


async def _counts_by_session(
    session: AsyncSession,
    session_ids: list[uuid.UUID],
) -> dict[uuid.UUID, views.SessionCounts]:
    if not session_ids:
        return {}
    rows = (
        await session.execute(
            select(AttendanceRecord.session_id, AttendanceRecord.status, func.count())
            .where(
                AttendanceRecord.session_id.in_(session_ids),
                AttendanceRecord.deleted_at.is_(None),
            )
            .group_by(AttendanceRecord.session_id, AttendanceRecord.status)
        )
    ).all()
    counts: dict[uuid.UUID, views.SessionCounts] = {
        session_id: views.SessionCounts() for session_id in session_ids
    }
    for session_id, status, amount in rows:
        item = counts[session_id]
        item.total += int(amount)
        if status in ("present", "absent", "late", "excused"):
            setattr(item, status, int(amount))
    return counts


async def _scoped_session(
    session: AsyncSession,
    principal: Principal,
    permission: str,
    session_id: uuid.UUID,
) -> AttendanceSession:
    row = await live_session(session, session_id)
    await scoping.assert_section_visible(session, principal, permission, row.section_id)
    return row


async def _validate_session_target(
    session: AsyncSession,
    year: AcademicYear,
    section: Section,
    *,
    mode: str,
    period: int | None,
    subject_id: uuid.UUID | None,
    on_date: date,
) -> None:
    if section.year_id != year.id:
        raise ValidationFailed(
            "The section does not belong to that academic year",
            message_key="attendance.error.section_year",
            details={"section_id": str(section.id), "year_id": str(year.id)},
        )
    if on_date < year.start_date or on_date > year.end_date:
        raise ValidationFailed(
            "The register date must fall inside the academic year",
            message_key="attendance.error.date_outside_year",
            details={
                "date": on_date.isoformat(),
                "year_start": year.start_date.isoformat(),
                "year_end": year.end_date.isoformat(),
            },
        )
    if mode == "per_period" and period is None:
        raise ValidationFailed(
            "A per-period register needs a lesson number",
            message_key="attendance.error.period_required",
            details={"mode": mode},
        )
    if subject_id is not None:
        subject = await live_subject(session, subject_id)
        offered = (
            await session.execute(
                select(LevelSubject).where(
                    LevelSubject.level_id == section.level_id,
                    LevelSubject.subject_id == subject.id,
                )
            )
        ).scalar_one_or_none()
        if offered is None:
            raise ValidationFailed(
                "The subject is not offered at this level",
                message_key="attendance.error.subject_not_offered",
                details={"subject_id": str(subject.id), "section_id": str(section.id)},
            )


async def _duplicate_session(
    session: AsyncSession,
    year_id: uuid.UUID,
    section_id: uuid.UUID,
    on_date: date,
    mode: str,
    period: int | None,
) -> AttendanceSession | None:
    stmt = select(AttendanceSession).where(
        AttendanceSession.deleted_at.is_(None),
        AttendanceSession.year_id == year_id,
        AttendanceSession.section_id == section_id,
        AttendanceSession.date == on_date,
        AttendanceSession.mode == mode,
    )
    stmt = stmt.where(
        AttendanceSession.period.is_(None) if period is None else AttendanceSession.period == period
    )
    return (await session.execute(stmt)).scalars().first()


async def create_session(
    session: AsyncSession,
    principal: Principal,
    data: SessionCreate,
    *,
    via: str = "api",
) -> SessionDetail:
    settings = await attendance_settings(session)
    mode = data.mode or settings.mode
    if mode not in MODES:
        raise ValidationFailed(
            "Unknown attendance mode",
            message_key="attendance.error.mode_invalid",
            details={"mode": mode},
        )
    if mode != settings.mode:
        raise ValidationFailed(
            "This school records attendance per day"
            if settings.mode == "daily"
            else "This school records attendance per lesson",
            message_key="attendance.error.mode_mismatch",
            details={"school_mode": settings.mode, "requested_mode": mode},
        )
    if mode == "per_period" and data.period is None:
        raise ValidationFailed(
            "A per-period register needs a lesson number",
            message_key="attendance.error.period_required",
        )
    if mode == "daily" and data.period is not None:
        raise ValidationFailed(
            "A daily register cannot carry a lesson number",
            message_key="attendance.error.period_not_allowed",
        )
    if is_future(data.date) and not settings.allow_future_dates:
        raise ValidationFailed(
            "A register cannot be dated in the future",
            message_key="attendance.error.future_date",
            details={"date": data.date.isoformat()},
        )

    year = await live_year(session, data.year_id)
    section = await live_section(session, data.section_id)
    await scoping.assert_section_visible(session, principal, "attendance.record", section.id)
    await _validate_session_target(
        session,
        year,
        section,
        mode=mode,
        period=data.period,
        subject_id=data.subject_id,
        on_date=data.date,
    )
    if await _duplicate_session(session, year.id, section.id, data.date, mode, data.period) is not None:
        raise Conflict(
            "An attendance register already exists for that section and date",
            message_key="attendance.error.session_exists",
            details={"section_id": str(section.id), "date": data.date.isoformat()},
        )

    row = AttendanceSession(
        year_id=year.id,
        section_id=section.id,
        date=data.date,
        mode=mode,
        period=data.period,
        subject_id=data.subject_id,
        notes=data.notes,
        status="open",
        created_by=uuid.UUID(principal.user_id),
        updated_by=uuid.UUID(principal.user_id),
    )
    session.add(row)
    await session.flush()

    seeded = 0
    if data.seed_records:
        roster = await enrolled_students(session, year.id, section.id)
        for profile, _person, _enrollment in roster:
            session.add(
                AttendanceRecord(
                    session_id=row.id,
                    student_id=profile.id,
                    status="present",
                    recorded_at=utcnow(),
                    recorded_by=uuid.UUID(principal.user_id),
                    created_by=uuid.UUID(principal.user_id),
                    updated_by=uuid.UUID(principal.user_id),
                )
            )
            seeded += 1
        await session.flush()

    await record(
        session,
        action="attendance.session.create",
        module=MODULE,
        entity_type="attendance_session",
        entity_id=str(row.id),
        after={**session_state(row), "records_seeded": seeded},
        actor=principal,
        via=via,
    )
    await session.commit()
    return await _detail(session, row)


async def list_sessions(
    session: AsyncSession,
    principal: Principal,
    query: SessionQuery,
) -> SessionList:
    stmt = select(AttendanceSession).where(AttendanceSession.deleted_at.is_(None))
    allowed = await scoping.visible_section_ids(session, principal, "attendance.view")
    if allowed is not None:
        if not allowed:
            return SessionList(items=[], total=0, next_cursor=None)
        stmt = stmt.where(AttendanceSession.section_id.in_(allowed))
    if query.year_id is not None:
        stmt = stmt.where(AttendanceSession.year_id == query.year_id)
    if query.section_id is not None:
        stmt = stmt.where(AttendanceSession.section_id == query.section_id)
    if query.from_date is not None:
        stmt = stmt.where(AttendanceSession.date >= query.from_date)
    if query.to_date is not None:
        stmt = stmt.where(AttendanceSession.date <= query.to_date)
    if query.status is not None:
        stmt = stmt.where(AttendanceSession.status == query.status)

    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())

    from core.api.pagination import PageParams, paginate

    rows, next_cursor = await paginate(
        session,
        stmt,
        PageParams(limit=query.limit, cursor=query.cursor, sort=query.sort, order=query.order),
        sort_columns=SORT_COLUMNS,
        default_sort="date",
        id_column=AttendanceSession.id,
    )
    labels = await views.load_labels(session, rows)
    counts = await _counts_by_session(session, [row.id for row in rows])
    items = [views.session_out(row, labels, counts.get(row.id, views.SessionCounts())) for row in rows]
    return SessionList(items=items, next_cursor=next_cursor, total=total)


async def get_session(
    session: AsyncSession,
    principal: Principal,
    session_id: uuid.UUID,
) -> SessionDetail:
    row = await _scoped_session(session, principal, "attendance.view", session_id)
    return await _detail(session, row)


async def update_session(
    session: AsyncSession,
    principal: Principal,
    session_id: uuid.UUID,
    data: SessionUpdate,
    *,
    via: str = "api",
) -> SessionDetail:
    row = await _scoped_session(session, principal, "attendance.record", session_id)
    if row.status != "open" and data.notes is not None and data.notes != row.notes:
        raise Conflict(
            "A closed register can no longer be edited",
            message_key="attendance.error.session_closed",
            details={"status": row.status},
        )
    ensure_row_version(row, data.row_version, current_state=session_state(row))
    changes: dict[str, Any] = {}
    if data.notes != row.notes:
        changes["notes"] = data.notes
    if changes:
        before = session_state(row)
        row.notes = data.notes
        row.updated_by = uuid.UUID(principal.user_id)
        row.row_version = (row.row_version or 0) + 1
        await record(
            session,
            action="attendance.session.update",
            module=MODULE,
            entity_type="attendance_session",
            entity_id=str(row.id),
            before=before,
            after=session_state(row),
            actor=principal,
            via=via,
        )
    await session.commit()
    return await _detail(session, row)


def _assert_transition(current: str, target: str) -> None:
    if target == current:
        return
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise Conflict(
            "That attendance status change is not allowed",
            message_key="attendance.error.transition",
            details={"from": current, "to": target},
        )


async def _transition(
    session: AsyncSession,
    principal: Principal,
    session_id: uuid.UUID,
    target: str,
    *,
    read_permission: str,
    via: str,
) -> SessionDetail:
    row = await _scoped_session(session, principal, read_permission, session_id)
    _assert_transition(row.status, target)
    if row.status == target:
        await session.commit()
        return await _detail(session, row)
    if row.status == "locked" and not principal.can("attendance.manage"):
        raise Conflict(
            "Only an attendance manager can reopen a locked register",
            message_key="attendance.error.reopen_forbidden",
            details={"status": row.status},
        )
    before = session_state(row)
    row.status = target
    row.status_changed_at = utcnow()
    row.status_changed_by = uuid.UUID(principal.user_id)
    row.updated_by = uuid.UUID(principal.user_id)
    row.row_version = (row.row_version or 0) + 1
    await record(
        session,
        action=f"attendance.session.{STATUS_ACTIONS[target]}",
        module=MODULE,
        entity_type="attendance_session",
        entity_id=str(row.id),
        before=before,
        after=session_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await _detail(session, row)


async def submit_session(
    session: AsyncSession,
    principal: Principal,
    session_id: uuid.UUID,
    *,
    via: str = "api",
) -> SessionDetail:
    return await _transition(
        session, principal, session_id, "submitted", read_permission="attendance.record", via=via
    )


async def lock_session(
    session: AsyncSession,
    principal: Principal,
    session_id: uuid.UUID,
    *,
    via: str = "api",
) -> SessionDetail:
    return await _transition(
        session, principal, session_id, "locked", read_permission="attendance.manage", via=via
    )


async def reopen_session(
    session: AsyncSession,
    principal: Principal,
    session_id: uuid.UUID,
    *,
    via: str = "api",
) -> SessionDetail:
    return await _transition(
        session, principal, session_id, "open", read_permission="attendance.manage", via=via
    )


async def delete_session(
    session: AsyncSession,
    principal: Principal,
    session_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict:
    row = await _scoped_session(session, principal, "attendance.manage", session_id)
    before = session_state(row)
    now = utcnow()
    row.deleted_at = now
    row.deleted_by = uuid.UUID(principal.user_id)
    row.updated_by = uuid.UUID(principal.user_id)
    row.row_version = (row.row_version or 0) + 1
    await record(
        session,
        action="attendance.session.delete",
        module=MODULE,
        entity_type="attendance_session",
        entity_id=str(row.id),
        before=before,
        after={"deleted": True},
        actor=principal,
        reason=reason,
        via=via,
    )
    await session.commit()
    return {"deleted": True, "id": str(row.id)}


async def _assert_editable(session: AsyncSession, row: AttendanceSession) -> None:
    if row.status != "open":
        raise Conflict(
            "This register is closed; reopen it before changing entries",
            message_key="attendance.error.session_closed",
            details={"status": row.status},
        )


def _assert_reason(settings: Any, item: RecordInput | RecordUpdate, current_status: str) -> None:
    status = item.status or current_status
    reason = item.reason
    required = status == "excused" or (settings.require_reason and status in ("absent", "late"))
    if required and not (reason and reason.strip()):
        raise ValidationFailed(
            "A reason is required for this attendance status",
            message_key="attendance.error.reason_required",
            details={"status": status},
        )


def _record_values(
    item: RecordInput | RecordUpdate, current: AttendanceRecord | None, *, replace: bool = False
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if item.status is not None:
        values["status"] = item.status
    if replace or item.reason is not None:
        values["reason"] = item.reason
    if replace or item.note is not None:
        values["note"] = item.note
    if replace or item.late_minutes is not None:
        values["late_minutes"] = item.late_minutes
    status = values.get("status", current.status if current else "present")
    if status != "late" and "late_minutes" not in values:
        # Switching away from late clears the stale minute count.
        values["late_minutes"] = None
    return values


async def _emit_absent(
    session: AsyncSession,
    principal: Principal,
    session_row: AttendanceSession,
    record_row: AttendanceRecord,
) -> None:
    """Publish the automation event when a student becomes absent."""
    if record_row.status != "absent":
        return
    await events.emit(
        session,
        "attendance.absent_marked",
        {
            "session_id": str(session_row.id),
            "record_id": str(record_row.id),
            "student_id": str(record_row.student_id),
            "year_id": str(session_row.year_id),
            "section_id": str(session_row.section_id),
            "date": session_row.date.isoformat(),
            "mode": session_row.mode,
            "period": session_row.period,
            "reason": record_row.reason,
            "late_minutes": record_row.late_minutes,
            "recorded_at": record_row.recorded_at.isoformat(),
        },
        actor_id=principal.user_id,
    )


async def _live_records_for(
    session: AsyncSession,
    session_id: uuid.UUID,
    student_ids: set[uuid.UUID],
) -> dict[uuid.UUID, AttendanceRecord]:
    if not student_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.session_id == session_id,
                    AttendanceRecord.student_id.in_(student_ids),
                    AttendanceRecord.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    return {row.student_id: row for row in rows}


async def upsert_records(
    session: AsyncSession,
    principal: Principal,
    session_id: uuid.UUID,
    data: BulkRecordsInput,
    *,
    via: str = "api",
) -> SessionDetail:
    row = await _scoped_session(session, principal, "attendance.record", session_id)
    await _assert_editable(session, row)
    settings = await attendance_settings(session)
    roster = await enrolled_students(session, row.year_id, row.section_id)
    enrolled = {profile.id for profile, _person, _enrollment in roster}
    existing = await _live_records_for(session, row.id, {item.student_id for item in data.items})
    actor_id = uuid.UUID(principal.user_id)

    for item in data.items:
        if item.student_id not in enrolled:
            raise ValidationFailed(
                "The student is not actively enrolled in this section",
                message_key="attendance.error.student_not_enrolled",
                details={"student_id": str(item.student_id)},
            )
        current = existing.get(item.student_id)
        _assert_reason(settings, item, current.status if current else "present")
        if current is None:
            created = AttendanceRecord(
                session_id=row.id,
                student_id=item.student_id,
                status=item.status,
                reason=item.reason,
                late_minutes=item.late_minutes if item.status == "late" else None,
                note=item.note,
                recorded_at=utcnow(),
                recorded_by=actor_id,
                created_by=actor_id,
                updated_by=actor_id,
            )
            session.add(created)
            await session.flush()
            await record(
                session,
                action="attendance.record.create",
                module=MODULE,
                entity_type="attendance_record",
                entity_id=str(created.id),
                after=record_state(created),
                actor=principal,
                via=via,
            )
            await _emit_absent(session, principal, row, created)
            continue

        if item.row_version is not None:
            ensure_row_version(current, item.row_version, current_state=record_state(current))
        values = _record_values(item, current, replace=True)
        changes = {key: value for key, value in values.items() if getattr(current, key) != value}
        if not changes:
            continue
        before = record_state(current)
        was_absent = before["status"] == "absent"
        for key, value in changes.items():
            setattr(current, key, value)
        current.recorded_at = utcnow()
        current.recorded_by = actor_id
        current.updated_by = actor_id
        current.row_version = (current.row_version or 0) + 1
        await record(
            session,
            action="attendance.record.update",
            module=MODULE,
            entity_type="attendance_record",
            entity_id=str(current.id),
            before=before,
            after=record_state(current),
            actor=principal,
            via=via,
        )
        if not was_absent:
            await _emit_absent(session, principal, row, current)
    await session.commit()
    return await _detail(session, row)


async def update_record(
    session: AsyncSession,
    principal: Principal,
    session_id: uuid.UUID,
    record_id: uuid.UUID,
    data: RecordUpdate,
    *,
    via: str = "api",
) -> SessionDetail:
    row = await _scoped_session(session, principal, "attendance.record", session_id)
    await _assert_editable(session, row)
    settings = await attendance_settings(session)
    current = await live_record(session, row.id, record_id)
    _assert_reason(settings, data, current.status)
    ensure_row_version(current, data.row_version, current_state=record_state(current))
    values = _record_values(data, current)
    changes = {key: value for key, value in values.items() if getattr(current, key) != value}
    if changes:
        before = record_state(current)
        was_absent = before["status"] == "absent"
        for key, value in changes.items():
            setattr(current, key, value)
        current.recorded_at = utcnow()
        current.recorded_by = uuid.UUID(principal.user_id)
        current.updated_by = uuid.UUID(principal.user_id)
        current.row_version = (current.row_version or 0) + 1
        await record(
            session,
            action="attendance.record.update",
            module=MODULE,
            entity_type="attendance_record",
            entity_id=str(current.id),
            before=before,
            after=record_state(current),
            actor=principal,
            via=via,
        )
        if not was_absent:
            await _emit_absent(session, principal, row, current)
    await session.commit()
    return await _detail(session, row)


__all__ = [
    "create_session",
    "delete_session",
    "get_session",
    "list_sessions",
    "lock_session",
    "reopen_session",
    "submit_session",
    "update_record",
    "update_session",
    "upsert_records",
]
