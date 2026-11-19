"""Shared lookups and audit snapshots for staff records."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import NotFound
from core.people.models import Person
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.staff.models import (
    StaffContract,
    StaffDepartment,
    StaffPosition,
    StaffProfile,
    StaffQualification,
)

MODULE = "staff"


async def live_staff(session: AsyncSession, staff_id: uuid.UUID) -> StaffProfile:
    row = (
        await session.execute(
            select(StaffProfile).where(
                StaffProfile.id == staff_id,
                StaffProfile.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("The staff member does not exist", message_key="staff.error.not_found")
    return row


async def live_person(session: AsyncSession, person_id: uuid.UUID) -> Person:
    row = (
        await session.execute(select(Person).where(Person.id == person_id, Person.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("The person does not exist", message_key="staff.error.person_not_found")
    return row


async def live_department(session: AsyncSession, department_id: uuid.UUID) -> StaffDepartment:
    row = (
        await session.execute(
            select(StaffDepartment).where(
                StaffDepartment.id == department_id,
                StaffDepartment.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The department does not exist",
            message_key="staff.error.department_not_found",
        )
    return row


async def live_position(session: AsyncSession, position_id: uuid.UUID) -> StaffPosition:
    row = (
        await session.execute(
            select(StaffPosition).where(
                StaffPosition.id == position_id,
                StaffPosition.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("The position does not exist", message_key="staff.error.position_not_found")
    return row


async def live_contract(session: AsyncSession, staff_id: uuid.UUID, contract_id: uuid.UUID) -> StaffContract:
    row = (
        await session.execute(
            select(StaffContract).where(
                StaffContract.id == contract_id,
                StaffContract.staff_id == staff_id,
                StaffContract.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("The contract does not exist", message_key="staff.error.contract_not_found")
    return row


async def live_qualification(
    session: AsyncSession, staff_id: uuid.UUID, qualification_id: uuid.UUID
) -> StaffQualification:
    row = (
        await session.execute(
            select(StaffQualification).where(
                StaffQualification.id == qualification_id,
                StaffQualification.staff_id == staff_id,
                StaffQualification.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The qualification does not exist",
            message_key="staff.error.qualification_not_found",
        )
    return row


def department_state(row: StaffDepartment) -> dict[str, Any]:
    return {
        "code": row.code,
        "name": row.name,
        "name_am": row.name_am,
        "parent_id": str(row.parent_id) if row.parent_id else None,
        "description": row.description,
        "is_active": row.is_active,
        "sort_order": row.sort_order,
        "row_version": row.row_version,
        "deleted": row.deleted_at is not None,
    }


def position_state(row: StaffPosition) -> dict[str, Any]:
    return {
        "code": row.code,
        "name": row.name,
        "name_am": row.name_am,
        "department_id": str(row.department_id) if row.department_id else None,
        "is_teaching": row.is_teaching,
        "description": row.description,
        "is_active": row.is_active,
        "sort_order": row.sort_order,
        "row_version": row.row_version,
        "deleted": row.deleted_at is not None,
    }


def staff_state(row: StaffProfile) -> dict[str, Any]:
    return {
        "person_id": str(row.person_id),
        "staff_number": row.staff_number,
        "user_id": str(row.user_id) if row.user_id else None,
        "status": row.status,
        "department_id": str(row.department_id) if row.department_id else None,
        "position_id": str(row.position_id) if row.position_id else None,
        "hire_date": row.hire_date.isoformat() if row.hire_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "notes": row.notes,
        "custom": row.custom or {},
        "row_version": row.row_version,
        "deleted": row.deleted_at is not None,
    }


def contract_state(row: StaffContract) -> dict[str, Any]:
    return {
        "staff_id": str(row.staff_id),
        "type": row.type,
        "status": row.status,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "salary_santim": row.salary_santim,
        "notes": row.notes,
        "row_version": row.row_version,
    }


def qualification_state(row: StaffQualification) -> dict[str, Any]:
    return {
        "staff_id": str(row.staff_id),
        "kind": row.kind,
        "title": row.title,
        "institution": row.institution,
        "field_of_study": row.field_of_study,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "result": row.result,
        "notes": row.notes,
        "row_version": row.row_version,
    }
