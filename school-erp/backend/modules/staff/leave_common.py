"""Shared rules for leave types, balances and requests.

Leave durations are stored as integer half-day units. The API still speaks in
days; this module is the single place that converts between the two so no float
ever reaches the database.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import NotFound, ValidationFailed
from core.people.models import Person, full_name
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear
from modules.staff.models import StaffLeaveBalance, StaffLeaveRequest, StaffLeaveType, StaffProfile

MODULE = "staff"


def days_from_units(units: int) -> float:
    return units / 2


def units_from_days(days: float) -> int:
    doubled = days * 2
    units = round(doubled)
    if abs(doubled - units) > 1e-9:
        raise ValidationFailed(
            "Leave days must be a whole or half day",
            message_key="staff.error.leave_half_day_step",
            details={"days": days},
        )
    return units


def request_units(start_date, end_date, is_half_day: bool) -> int:  # noqa: ANN001
    days = (end_date - start_date).days + 1
    if days < 1:
        raise ValidationFailed(
            "The end date cannot be before the start date",
            message_key="staff.error.leave_dates",
        )
    if is_half_day and start_date != end_date:
        raise ValidationFailed(
            "A half-day request must start and end on the same date",
            message_key="staff.error.leave_half_day_dates",
        )
    return days * 2 - (1 if is_half_day else 0)


async def live_leave_type(session: AsyncSession, leave_type_id: uuid.UUID) -> StaffLeaveType:
    row = (
        await session.execute(
            select(StaffLeaveType).where(
                StaffLeaveType.id == leave_type_id,
                StaffLeaveType.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The leave type does not exist",
            message_key="staff.error.leave_type_not_found",
        )
    return row


async def live_leave_year(session: AsyncSession, year_id: uuid.UUID) -> AcademicYear:
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


def leave_type_state(row: StaffLeaveType) -> dict[str, Any]:
    return {
        "code": row.code,
        "name": row.name,
        "name_am": row.name_am,
        "is_paid": row.is_paid,
        "annual_entitlement_units": row.annual_entitlement_units,
        "counts_against_balance": row.counts_against_balance,
        "requires_approval": row.requires_approval,
        "is_active": row.is_active,
        "sort_order": row.sort_order,
        "notes": row.notes,
        "row_version": row.row_version,
    }


def leave_balance_state(row: StaffLeaveBalance) -> dict[str, Any]:
    return {
        "staff_id": str(row.staff_id),
        "year_id": str(row.year_id),
        "leave_type_id": str(row.leave_type_id),
        "entitled_units": row.entitled_units,
        "carried_units": row.carried_units,
        "adjustment_units": row.adjustment_units,
        "notes": row.notes,
        "row_version": row.row_version,
    }


def leave_request_state(row: StaffLeaveRequest) -> dict[str, Any]:
    return {
        "staff_id": str(row.staff_id),
        "year_id": str(row.year_id),
        "leave_type_id": str(row.leave_type_id),
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
        "is_half_day": row.is_half_day,
        "days_units": row.days_units,
        "reason": row.reason,
        "status": row.status,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "decided_by": str(row.decided_by) if row.decided_by else None,
        "decision_note": row.decision_note,
        "row_version": row.row_version,
    }


async def staff_identity(
    session: AsyncSession, staff_ids: set[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, str]]:
    """Map staff ids to ``(staff_number, person display name)``."""
    if not staff_ids:
        return {}
    rows = (
        await session.execute(
            select(StaffProfile, Person)
            .join(Person, Person.id == StaffProfile.person_id)
            .where(StaffProfile.id.in_(staff_ids))
        )
    ).all()
    return {profile.id: (profile.staff_number, full_name(person, locale="en")) for profile, person in rows}


__all__ = [
    "MODULE",
    "days_from_units",
    "leave_balance_state",
    "leave_request_state",
    "leave_type_state",
    "live_leave_type",
    "live_leave_year",
    "request_units",
    "staff_identity",
    "units_from_days",
]
