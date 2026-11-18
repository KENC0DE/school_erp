"""Departments and positions: the shape of the staff establishment."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.staff.common import (
    MODULE,
    department_state,
    live_department,
    position_state,
)
from modules.staff.models import StaffDepartment, StaffPosition
from modules.staff.schemas import (
    DepartmentInput,
    DepartmentList,
    DepartmentOut,
    DepartmentUpdate,
    PositionInput,
    PositionList,
    PositionOut,
    PositionUpdate,
)
from modules.staff.views import department_out, position_out


async def _department_code_taken(
    session: AsyncSession, code: str, *, current_id: uuid.UUID | None = None
) -> bool:
    stmt = select(StaffDepartment.id).where(
        StaffDepartment.code == code,
        StaffDepartment.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(StaffDepartment.id != current_id)
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _assert_department_code_free(
    session: AsyncSession, code: str, *, current_id: uuid.UUID | None = None
) -> None:
    if await _department_code_taken(session, code, current_id=current_id):
        raise Conflict(
            "A department with that code already exists",
            message_key="staff.error.department_code_taken",
            details={"code": code},
        )


async def _assert_parent(
    session: AsyncSession, parent_id: uuid.UUID | None, *, current_id: uuid.UUID | None = None
) -> None:
    if parent_id is None:
        return
    if current_id is not None and parent_id == current_id:
        raise ValidationFailed(
            "A department cannot be its own parent",
            message_key="staff.error.department_parent_self",
        )
    parent = await live_department(session, parent_id)
    seen: set[uuid.UUID] = set()
    while parent is not None:
        if parent.id in seen:
            break
        seen.add(parent.id)
        if current_id is not None and parent.id == current_id:
            raise ValidationFailed(
                "That parent would create a department cycle",
                message_key="staff.error.department_cycle",
            )
        parent = await live_department(session, parent.parent_id) if parent.parent_id else None


async def list_departments(session: AsyncSession, *, include_inactive: bool = False) -> DepartmentList:
    stmt = select(StaffDepartment).where(StaffDepartment.deleted_at.is_(None))
    if not include_inactive:
        stmt = stmt.where(StaffDepartment.is_active.is_(True))
    rows = (
        (await session.execute(stmt.order_by(StaffDepartment.sort_order, StaffDepartment.name)))
        .scalars()
        .all()
    )
    return DepartmentList(items=[department_out(row) for row in rows], total=len(rows))


async def get_department(session: AsyncSession, department_id: uuid.UUID) -> DepartmentOut:
    return department_out(await live_department(session, department_id))


async def create_department(
    session: AsyncSession,
    principal: Principal,
    data: DepartmentInput,
    *,
    via: str = "api",
) -> DepartmentOut:
    await _assert_department_code_free(session, data.code)
    await _assert_parent(session, data.parent_id)
    row = StaffDepartment(**data.model_dump())
    session.add(row)
    await session.flush()
    await record(
        session,
        action="staff.departments.create",
        module=MODULE,
        entity_type="staff_department",
        entity_id=str(row.id),
        after=department_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return department_out(row)


async def update_department(
    session: AsyncSession,
    principal: Principal,
    department_id: uuid.UUID,
    data: DepartmentUpdate,
    *,
    via: str = "api",
) -> DepartmentOut:
    row = await live_department(session, department_id)
    before = department_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    if "code" in payload:
        await _assert_department_code_free(session, payload["code"], current_id=row.id)
    if "parent_id" in payload:
        await _assert_parent(session, payload["parent_id"], current_id=row.id)

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
            action="staff.departments.update",
            module=MODULE,
            entity_type="staff_department",
            entity_id=str(row.id),
            before=before,
            after=department_state(row),
            actor=principal,
            via=via,
        )
    await session.commit()
    return department_out(row)


async def _position_code_taken(
    session: AsyncSession, code: str, *, current_id: uuid.UUID | None = None
) -> bool:
    stmt = select(StaffPosition.id).where(
        StaffPosition.code == code,
        StaffPosition.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(StaffPosition.id != current_id)
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _assert_position_code_free(
    session: AsyncSession, code: str, *, current_id: uuid.UUID | None = None
) -> None:
    if await _position_code_taken(session, code, current_id=current_id):
        raise Conflict(
            "A position with that code already exists",
            message_key="staff.error.position_code_taken",
            details={"code": code},
        )


async def _assert_department_active(session: AsyncSession, department_id: uuid.UUID | None) -> None:
    if department_id is None:
        return
    department = await live_department(session, department_id)
    if not department.is_active:
        raise ValidationFailed(
            "An inactive department cannot receive positions",
            message_key="staff.error.department_inactive",
        )


async def _department_map(
    session: AsyncSession, rows: list[StaffPosition]
) -> dict[uuid.UUID, StaffDepartment]:
    ids = {row.department_id for row in rows if row.department_id is not None}
    if not ids:
        return {}
    return {
        row.id: row
        for row in (await session.execute(select(StaffDepartment).where(StaffDepartment.id.in_(ids))))
        .scalars()
        .all()
    }


async def list_positions(
    session: AsyncSession,
    *,
    department_id: uuid.UUID | None = None,
    include_inactive: bool = False,
) -> PositionList:
    stmt = select(StaffPosition).where(StaffPosition.deleted_at.is_(None))
    if department_id is not None:
        stmt = stmt.where(StaffPosition.department_id == department_id)
    if not include_inactive:
        stmt = stmt.where(StaffPosition.is_active.is_(True))
    rows = (
        (await session.execute(stmt.order_by(StaffPosition.sort_order, StaffPosition.name))).scalars().all()
    )
    departments = await _department_map(session, rows)
    return PositionList(
        items=[
            position_out(row, departments.get(row.department_id) if row.department_id else None)
            for row in rows
        ],
        total=len(rows),
    )


async def get_position(session: AsyncSession, position_id: uuid.UUID) -> PositionOut:
    row = await _live_position_or_raise(session, position_id)
    department = await live_department(session, row.department_id) if row.department_id else None
    return position_out(row, department)


async def _live_position_or_raise(session: AsyncSession, position_id: uuid.UUID) -> StaffPosition:
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


async def create_position(
    session: AsyncSession,
    principal: Principal,
    data: PositionInput,
    *,
    via: str = "api",
) -> PositionOut:
    await _assert_position_code_free(session, data.code)
    await _assert_department_active(session, data.department_id)
    row = StaffPosition(**data.model_dump())
    session.add(row)
    await session.flush()
    await record(
        session,
        action="staff.positions.create",
        module=MODULE,
        entity_type="staff_position",
        entity_id=str(row.id),
        after=position_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    department = await live_department(session, row.department_id) if row.department_id else None
    return position_out(row, department)


async def update_position(
    session: AsyncSession,
    principal: Principal,
    position_id: uuid.UUID,
    data: PositionUpdate,
    *,
    via: str = "api",
) -> PositionOut:
    row = await _live_position_or_raise(session, position_id)
    before = position_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    if "code" in payload:
        await _assert_position_code_free(session, payload["code"], current_id=row.id)
    if "department_id" in payload:
        await _assert_department_active(session, payload["department_id"])

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
            action="staff.positions.update",
            module=MODULE,
            entity_type="staff_position",
            entity_id=str(row.id),
            before=before,
            after=position_state(row),
            actor=principal,
            via=via,
        )
    await session.commit()
    department = await live_department(session, row.department_id) if row.department_id else None
    return position_out(row, department)


__all__ = [
    "create_department",
    "create_position",
    "get_department",
    "get_position",
    "list_departments",
    "list_positions",
    "update_department",
    "update_position",
]
