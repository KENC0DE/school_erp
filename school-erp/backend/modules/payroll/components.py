"""Salary components and their per-staff assignments."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import get_including_deleted, restore, soft_delete
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payroll.common import (
    MODULE,
    component_state,
    live_component,
    live_staff_component,
    staff_component_state,
)
from modules.payroll.models import PayrollComponent, PayrollStaffComponent
from modules.payroll.schemas import (
    ComponentInput,
    ComponentList,
    ComponentOut,
    ComponentUpdate,
    StaffComponentInput,
    StaffComponentList,
    StaffComponentOut,
    StaffComponentUpdate,
)
from modules.payroll.views import component_out, staff_component_out
from modules.staff.models import StaffProfile


async def _live_staff(session: AsyncSession, staff_id: uuid.UUID) -> StaffProfile:
    row = (
        await session.execute(
            select(StaffProfile).where(
                StaffProfile.id == staff_id,
                StaffProfile.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("The staff member does not exist", message_key="payroll.error.staff_not_found")
    return row


async def _assert_code_free(
    session: AsyncSession,
    code: str,
    *,
    current_id: uuid.UUID | None = None,
) -> None:
    stmt = select(PayrollComponent.id).where(
        PayrollComponent.code == code,
        PayrollComponent.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(PayrollComponent.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "A salary component with that code already exists",
            message_key="payroll.error.component_code_taken",
            details={"code": code},
        )


async def list_components(
    session: AsyncSession,
    *,
    include_inactive: bool = False,
) -> ComponentList:
    stmt = select(PayrollComponent).where(PayrollComponent.deleted_at.is_(None))
    if not include_inactive:
        stmt = stmt.where(PayrollComponent.is_active.is_(True))
    rows = (
        (await session.execute(stmt.order_by(PayrollComponent.sort_order, PayrollComponent.code)))
        .scalars()
        .all()
    )
    return ComponentList(items=[component_out(row) for row in rows], total=len(rows))


async def get_component(session: AsyncSession, component_id: uuid.UUID) -> ComponentOut:
    return component_out(await live_component(session, component_id))


async def create_component(
    session: AsyncSession,
    principal: Principal,
    data: ComponentInput,
    *,
    via: str = "api",
) -> ComponentOut:
    await _assert_code_free(session, data.code)
    row = PayrollComponent(**data.model_dump())
    session.add(row)
    await session.flush()
    await record(
        session,
        action="payroll.components.create",
        module=MODULE,
        entity_type="payroll_component",
        entity_id=str(row.id),
        after=component_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return component_out(row)


async def update_component(
    session: AsyncSession,
    principal: Principal,
    component_id: uuid.UUID,
    data: ComponentUpdate,
    *,
    via: str = "api",
) -> ComponentOut:
    row = await live_component(session, component_id)
    before = component_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    if "code" in payload and payload["code"] != row.code:
        assert payload["code"] is not None
        await _assert_code_free(session, payload["code"], current_id=row.id)

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
            action="payroll.components.update",
            module=MODULE,
            entity_type="payroll_component",
            entity_id=str(row.id),
            before=before,
            after=component_state(row),
            actor=principal,
            via=via,
        )
    await session.commit()
    return component_out(row)


async def delete_component(
    session: AsyncSession,
    principal: Principal,
    component_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await live_component(session, component_id)
    assignments = (
        (
            await session.execute(
                select(PayrollStaffComponent.id)
                .where(
                    PayrollStaffComponent.component_id == row.id,
                    PayrollStaffComponent.deleted_at.is_(None),
                )
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if assignments is not None:
        raise Conflict(
            "Deactivate the component instead; it is still assigned to staff",
            message_key="payroll.error.component_in_use",
        )
    changed = await soft_delete(
        session,
        row,
        action="payroll.components.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="payroll_component",
    )
    await session.flush()
    await session.commit()
    return {"id": str(row.id), "deleted": bool(changed), "row_version": row.row_version}


async def restore_component(
    session: AsyncSession,
    principal: Principal,
    component_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> ComponentOut:
    row = await get_including_deleted(session, PayrollComponent, component_id)
    if row is None:
        raise NotFound(
            "The salary component does not exist",
            message_key="payroll.error.component_not_found",
        )
    await _assert_code_free(session, row.code, current_id=row.id)
    await restore(
        session,
        row,
        action="payroll.components.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="payroll_component",
    )
    await session.flush()
    await session.commit()
    return component_out(row)


# ---------------------------------------------------------- staff assignments


def _assert_exactly_one_form(
    amount_santim: int | None,
    rate_basis_points: int | None,
) -> None:
    if (amount_santim is None) == (rate_basis_points is None):
        raise ValidationFailed(
            "Set exactly one of a fixed amount or a rate",
            message_key="payroll.error.component_amount_form",
        )
    if amount_santim is not None and amount_santim < 0:
        raise ValidationFailed(
            "A salary component amount cannot be negative",
            message_key="payroll.error.component_amount_negative",
        )
    if rate_basis_points is not None and not 0 <= rate_basis_points <= 10_000:
        raise ValidationFailed(
            "A component rate must be between 0 and 100%",
            message_key="payroll.error.component_rate_range",
        )


async def _assert_no_overlap(
    session: AsyncSession,
    staff_id: uuid.UUID,
    component_id: uuid.UUID,
    starts_on: date,
    ends_on: date | None,
    *,
    current_id: uuid.UUID | None = None,
) -> None:
    # Two live assignments of the same component may not share a day, or the
    # staff member would be paid twice for the same allowance.
    conditions = [
        PayrollStaffComponent.staff_id == staff_id,
        PayrollStaffComponent.component_id == component_id,
        PayrollStaffComponent.deleted_at.is_(None),
        or_(
            PayrollStaffComponent.ends_on.is_(None),
            PayrollStaffComponent.ends_on >= starts_on,
        ),
    ]
    if ends_on is not None:
        conditions.append(PayrollStaffComponent.starts_on <= ends_on)
    stmt = select(PayrollStaffComponent.id).where(and_(*conditions))
    if current_id is not None:
        stmt = stmt.where(PayrollStaffComponent.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "This component already applies to the staff member in that period",
            message_key="payroll.error.component_overlap",
        )


async def list_staff_components(
    session: AsyncSession,
    staff_id: uuid.UUID,
) -> StaffComponentList:
    await _live_staff(session, staff_id)
    rows = (
        await session.execute(
            select(PayrollStaffComponent, PayrollComponent)
            .join(PayrollComponent, PayrollComponent.id == PayrollStaffComponent.component_id)
            .where(
                PayrollStaffComponent.staff_id == staff_id,
                PayrollStaffComponent.deleted_at.is_(None),
            )
            .order_by(PayrollStaffComponent.starts_on.desc(), PayrollComponent.sort_order)
        )
    ).all()
    return StaffComponentList(
        items=[staff_component_out(assignment, component) for assignment, component in rows],
        total=len(rows),
    )


async def create_staff_component(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    data: StaffComponentInput,
    *,
    via: str = "api",
) -> StaffComponentOut:
    await _live_staff(session, staff_id)
    component = await live_component(session, data.component_id)
    _assert_exactly_one_form(data.amount_santim, data.rate_basis_points)
    if data.ends_on is not None and data.ends_on < data.starts_on:
        raise ValidationFailed(
            "The end date cannot be before the start date",
            message_key="payroll.error.component_dates",
        )
    await _assert_no_overlap(
        session,
        staff_id,
        component.id,
        data.starts_on,
        data.ends_on,
    )
    row = PayrollStaffComponent(staff_id=staff_id, **data.model_dump())
    session.add(row)
    await session.flush()
    await record(
        session,
        action="payroll.staff_components.create",
        module=MODULE,
        entity_type="payroll_staff_component",
        entity_id=str(row.id),
        after=staff_component_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return staff_component_out(row, component)


async def update_staff_component(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
    data: StaffComponentUpdate,
    *,
    via: str = "api",
) -> StaffComponentOut:
    row = await live_staff_component(session, staff_id, assignment_id)
    component = await live_component(session, row.component_id)
    before = staff_component_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    amount = payload.get("amount_santim", row.amount_santim)
    rate = payload.get("rate_basis_points", row.rate_basis_points)
    _assert_exactly_one_form(amount, rate)
    starts_on = payload.get("starts_on", row.starts_on)
    ends_on = payload.get("ends_on", row.ends_on)
    if ends_on is not None and starts_on is not None and ends_on < starts_on:
        raise ValidationFailed(
            "The end date cannot be before the start date",
            message_key="payroll.error.component_dates",
        )
    await _assert_no_overlap(
        session,
        staff_id,
        component.id,
        starts_on,
        ends_on,
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
            action="payroll.staff_components.update",
            module=MODULE,
            entity_type="payroll_staff_component",
            entity_id=str(row.id),
            before=before,
            after=staff_component_state(row),
            actor=principal,
            via=via,
        )
    await session.commit()
    return staff_component_out(row, component)


async def delete_staff_component(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await live_staff_component(session, staff_id, assignment_id)
    changed = await soft_delete(
        session,
        row,
        action="payroll.staff_components.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="payroll_staff_component",
    )
    await session.flush()
    await session.commit()
    return {"id": str(row.id), "deleted": bool(changed), "row_version": row.row_version}


async def restore_staff_component(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> StaffComponentOut:
    row = await get_including_deleted(session, PayrollStaffComponent, assignment_id)
    if row is None or row.staff_id != staff_id:
        raise NotFound(
            "The staff salary component does not exist",
            message_key="payroll.error.staff_component_not_found",
        )
    component = await live_component(session, row.component_id)
    await _assert_no_overlap(
        session,
        staff_id,
        component.id,
        row.starts_on,
        row.ends_on,
        current_id=row.id,
    )
    await restore(
        session,
        row,
        action="payroll.staff_components.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="payroll_staff_component",
    )
    await session.flush()
    await session.commit()
    return staff_component_out(row, component)


__all__ = [
    "create_component",
    "create_staff_component",
    "delete_component",
    "delete_staff_component",
    "get_component",
    "list_components",
    "list_staff_components",
    "restore_component",
    "restore_staff_component",
    "update_component",
    "update_staff_component",
]
