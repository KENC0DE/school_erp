"""Staff attendance: the daily staff roster, bulk entry and yearly summary.

Staff attendance is separate from student registers. The natural key is
(staff, date), so replaying an offline edit or correcting a status never
creates a second row. Every mutation is audited through this module.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from app.errors import Forbidden, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.people.models import Person, full_name
from core.rbac.scopes import ALL, DEPARTMENT, SELF, effective_scopes
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.staff import scopes as staff_scopes
from modules.staff.attendance_schemas import (
    StaffAttendanceBulkInput,
    StaffAttendanceCounts,
    StaffAttendanceDay,
    StaffAttendanceEntryOut,
    StaffAttendanceQuery,
    StaffAttendanceSummary,
)
from modules.staff.common import MODULE, live_staff
from modules.staff.models import StaffAttendance, StaffDepartment, StaffProfile

EMPLOYED_STATUSES = ("active", "on_leave")


def utcnow() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    return datetime.now(UTC).date()


async def visible_staff_ids(
    session: AsyncSession,
    principal: Principal,
    permission: str = "staff.attendance.view",
) -> set[uuid.UUID] | None:
    """Staff whose attendance a caller may see, or ``None`` for everyone."""
    scopes = effective_scopes(principal, permission)
    if scopes is None or ALL in scopes:
        return None
    allowed: set[uuid.UUID] = set()
    user_id = uuid.UUID(principal.user_id)
    if SELF in scopes:
        profile = await staff_scopes.staff_for_user(session, user_id)
        if profile is not None:
            allowed.add(profile.id)
    if DEPARTMENT in scopes:
        allowed |= await staff_scopes.department_staff_ids(session, user_id)
    return allowed


async def assert_staff_visible(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    *,
    permission: str = "staff.attendance.view",
) -> None:
    allowed = await visible_staff_ids(session, principal, permission)
    if allowed is not None and staff_id not in allowed:
        raise Forbidden(
            "This staff attendance record is outside your scope",
            message_key="error.scope_denied",
            details={"staff_id": str(staff_id)},
        )


def attendance_state(row: StaffAttendance) -> dict[str, Any]:
    return {
        "staff_id": str(row.staff_id),
        "date": row.date.isoformat(),
        "status": row.status,
        "reason": row.reason,
        "note": row.note,
        "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
        "row_version": row.row_version,
    }


def _empty_day(on_date: date) -> StaffAttendanceDay:
    return StaffAttendanceDay(
        date=on_date,
        counts=StaffAttendanceCounts(),
        items=[],
    )


async def day_view(
    session: AsyncSession,
    principal: Principal,
    query: StaffAttendanceQuery,
) -> StaffAttendanceDay:
    """Every employed staff member for one day, with the status recorded so far."""
    on_date = query.date or today()
    allowed = await visible_staff_ids(session, principal, "staff.attendance.view")
    if allowed is not None and not allowed:
        return _empty_day(on_date)

    stmt = (
        select(StaffProfile, Person, StaffDepartment)
        .join(Person, Person.id == StaffProfile.person_id)
        .outerjoin(StaffDepartment, StaffDepartment.id == StaffProfile.department_id)
        .where(
            StaffProfile.deleted_at.is_(None),
            Person.deleted_at.is_(None),
            StaffProfile.status.in_(EMPLOYED_STATUSES),
        )
    )
    if allowed is not None:
        stmt = stmt.where(StaffProfile.id.in_(allowed))
    if query.department_id is not None:
        stmt = stmt.where(StaffProfile.department_id == query.department_id)
    if query.q:
        pattern = f"%{query.q.strip()}%"
        stmt = stmt.where(
            or_(
                StaffProfile.staff_number.ilike(pattern),
                Person.given_name_en.ilike(pattern),
                Person.father_name_en.ilike(pattern),
                Person.grandfather_name_en.ilike(pattern),
                Person.given_name_am.ilike(pattern),
            )
        )

    rows = (await session.execute(stmt.order_by(StaffProfile.staff_number))).all()
    staff_ids = [row[0].id for row in rows]
    records: dict[uuid.UUID, StaffAttendance] = {}
    if staff_ids:
        records = {
            row.staff_id: row
            for row in (
                await session.execute(
                    select(StaffAttendance).where(
                        StaffAttendance.staff_id.in_(staff_ids),
                        StaffAttendance.date == on_date,
                        StaffAttendance.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        }

    items: list[StaffAttendanceEntryOut] = []
    counts = StaffAttendanceCounts()
    for profile, person, department in rows:
        row = records.get(profile.id)
        status = row.status if row is not None else None
        if query.status is not None and status != query.status:
            continue
        items.append(
            StaffAttendanceEntryOut(
                staff_id=str(profile.id),
                staff_number=profile.staff_number,
                staff_name=full_name(person, "en"),
                staff_name_am=full_name(person, "am") or None,
                department_id=str(department.id) if department else None,
                department_name=department.name if department else None,
                status=status,  # type: ignore[arg-type]
                reason=row.reason if row is not None else None,
                note=row.note if row is not None else None,
                record_id=str(row.id) if row is not None else None,
                row_version=row.row_version if row is not None else None,
            )
        )
        counts.total += 1
        if status is None:
            counts.unrecorded += 1
        else:
            counts.recorded += 1
            setattr(counts, status, getattr(counts, status) + 1)
    return StaffAttendanceDay(date=on_date, counts=counts, items=items)


async def upsert_day(
    session: AsyncSession,
    principal: Principal,
    data: StaffAttendanceBulkInput,
    *,
    via: str = "api",
) -> StaffAttendanceDay:
    """Record one status per staff member for a date, idempotently."""
    actor_id = uuid.UUID(principal.user_id)
    staff_ids = {item.staff_id for item in data.items}
    allowed = await visible_staff_ids(session, principal, "staff.attendance.record")
    if allowed is not None:
        outside = staff_ids - allowed
        if outside:
            raise Forbidden(
                "This staff attendance record is outside your scope",
                message_key="error.scope_denied",
                details={"staff_id": str(sorted(outside, key=str)[0])},
            )

    profiles = {
        row.id: row
        for row in (
            await session.execute(
                select(StaffProfile).where(
                    StaffProfile.id.in_(staff_ids),
                    StaffProfile.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }
    existing = {
        row.staff_id: row
        for row in (
            await session.execute(
                select(StaffAttendance).where(
                    StaffAttendance.staff_id.in_(staff_ids),
                    StaffAttendance.date == data.date,
                    StaffAttendance.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }

    for item in data.items:
        profile = profiles.get(item.staff_id)
        if profile is None:
            raise ValidationFailed(
                "The staff member does not exist",
                message_key="staff.error.attendance_staff_not_found",
                details={"staff_id": str(item.staff_id)},
            )
        if profile.status not in EMPLOYED_STATUSES:
            raise ValidationFailed(
                "Attendance can only be recorded for employed staff",
                message_key="staff.error.attendance_not_employed",
                details={"staff_id": str(item.staff_id), "status": profile.status},
            )

        current = existing.get(item.staff_id)
        if current is None:
            created = StaffAttendance(
                staff_id=item.staff_id,
                date=data.date,
                status=item.status,
                reason=item.reason,
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
                action="staff.attendance.create",
                module=MODULE,
                entity_type="staff_attendance",
                entity_id=str(created.id),
                after=attendance_state(created),
                actor=principal,
                via=via,
            )
            continue

        if item.row_version is not None:
            ensure_row_version(current, item.row_version, current_state=attendance_state(current))
        changes: dict[str, Any] = {}
        for key in ("status", "reason", "note"):
            value = getattr(item, key)
            if getattr(current, key) != value:
                changes[key] = value
        if not changes:
            continue
        before = attendance_state(current)
        for key, value in changes.items():
            setattr(current, key, value)
        current.recorded_at = utcnow()
        current.recorded_by = actor_id
        current.updated_by = actor_id
        current.row_version = (current.row_version or 0) + 1
        await record(
            session,
            action="staff.attendance.update",
            module=MODULE,
            entity_type="staff_attendance",
            entity_id=str(current.id),
            before=before,
            after=attendance_state(current),
            actor=principal,
            via=via,
        )

    await session.commit()
    return await day_view(session, principal, StaffAttendanceQuery(date=data.date))


def _rate(attended: int, total: int) -> int:
    if total <= 0:
        return 0
    return (attended * 100 + total // 2) // total


async def summary(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    *,
    from_date: date,
    to_date: date,
) -> StaffAttendanceSummary:
    """One staff member's attendance totals over a closed date range."""
    if to_date < from_date:
        raise ValidationFailed(
            "The end date must not be before the start date",
            message_key="staff.error.attendance_range",
            details={"from_date": from_date.isoformat(), "to_date": to_date.isoformat()},
        )
    await assert_staff_visible(session, principal, staff_id)
    profile = await live_staff(session, staff_id)
    person = (await session.execute(select(Person).where(Person.id == profile.person_id))).scalar_one()

    rows = (
        await session.execute(
            select(StaffAttendance.status, func.count())
            .where(
                StaffAttendance.staff_id == staff_id,
                StaffAttendance.date >= from_date,
                StaffAttendance.date <= to_date,
                StaffAttendance.deleted_at.is_(None),
            )
            .group_by(StaffAttendance.status)
        )
    ).all()
    counts = {status: int(amount) for status, amount in rows}
    total = sum(counts.values())
    attended = counts.get("present", 0) + counts.get("late", 0)
    return StaffAttendanceSummary(
        staff_id=str(profile.id),
        staff_number=profile.staff_number,
        staff_name=full_name(person, "en"),
        from_date=from_date,
        to_date=to_date,
        total=total,
        present=counts.get("present", 0),
        absent=counts.get("absent", 0),
        late=counts.get("late", 0),
        leave=counts.get("leave", 0),
        attended=attended,
        rate_percent=_rate(attended, total),
    )


__all__ = [
    "assert_staff_visible",
    "attendance_state",
    "day_view",
    "summary",
    "upsert_day",
    "visible_staff_ids",
]
