"""Employment contracts, including salary stored as integer santim."""

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

from modules.staff.common import (
    MODULE,
    contract_state,
    live_contract,
    live_staff,
)
from modules.staff.models import StaffContract
from modules.staff.schemas import (
    CONTRACT_STATUSES,
    CONTRACT_TYPES,
    ContractInput,
    ContractList,
    ContractOut,
    ContractUpdate,
)
from modules.staff.views import contract_out

TYPE_VALUES = set(CONTRACT_TYPES)
STATUS_VALUES = set(CONTRACT_STATUSES)


def _assert_values(contract_type: str, status: str) -> None:
    if contract_type not in TYPE_VALUES:
        raise ValidationFailed(
            "Unknown contract type",
            message_key="staff.error.contract_type_invalid",
            details={"type": contract_type},
        )
    if status not in STATUS_VALUES:
        raise ValidationFailed(
            "Unknown contract status",
            message_key="staff.error.contract_status_invalid",
            details={"status": status},
        )


async def _assert_single_active(
    session: AsyncSession,
    staff_id: uuid.UUID,
    *,
    current_id: uuid.UUID | None = None,
    status: str,
) -> None:
    if status != "active":
        return
    stmt = select(StaffContract.id).where(
        StaffContract.staff_id == staff_id,
        StaffContract.status == "active",
        StaffContract.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(StaffContract.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "This staff member already has an active contract",
            message_key="staff.error.contract_active",
            details={"staff_id": str(staff_id)},
        )


def _assert_dates(start_date, end_date) -> None:  # type: ignore[no-untyped-def]
    if end_date is not None and end_date < start_date:
        raise ValidationFailed(
            "The contract end date cannot be before its start date",
            message_key="staff.error.dates_invalid",
        )


async def list_contracts(session: AsyncSession, staff_id: uuid.UUID) -> ContractList:
    await live_staff(session, staff_id)
    rows = (
        (
            await session.execute(
                select(StaffContract)
                .where(
                    StaffContract.staff_id == staff_id,
                    StaffContract.deleted_at.is_(None),
                )
                .order_by(StaffContract.start_date.desc(), StaffContract.id)
            )
        )
        .scalars()
        .all()
    )
    return ContractList(items=[contract_out(row) for row in rows], total=len(rows))


async def create_contract(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    data: ContractInput,
    *,
    via: str = "api",
) -> ContractOut:
    await live_staff(session, staff_id)
    _assert_values(data.type, data.status)
    _assert_dates(data.start_date, data.end_date)
    await _assert_single_active(session, staff_id, status=data.status)
    row = StaffContract(staff_id=staff_id, **data.model_dump())
    session.add(row)
    await session.flush()
    await record(
        session,
        action="staff.contracts.create",
        module=MODULE,
        entity_type="staff_contract",
        entity_id=str(row.id),
        after=contract_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return contract_out(row)


async def update_contract(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    contract_id: uuid.UUID,
    data: ContractUpdate,
    *,
    via: str = "api",
) -> ContractOut:
    row = await live_contract(session, staff_id, contract_id)
    before = contract_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    contract_type = payload.get("type", row.type)
    status = payload.get("status", row.status)
    start_date = payload.get("start_date", row.start_date)
    end_date = payload.get("end_date", row.end_date)
    _assert_values(contract_type, status)
    _assert_dates(start_date, end_date)
    await _assert_single_active(session, staff_id, current_id=row.id, status=status)

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
            action="staff.contracts.update",
            module=MODULE,
            entity_type="staff_contract",
            entity_id=str(row.id),
            before=before,
            after=contract_state(row),
            actor=principal,
            via=via,
        )
    await session.commit()
    return contract_out(row)


async def delete_contract(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    contract_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await live_contract(session, staff_id, contract_id)
    changed = await soft_delete(
        session,
        row,
        action="staff.contracts.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="staff_contract",
    )
    await session.flush()
    await session.commit()
    return {"id": str(row.id), "deleted": bool(changed), "row_version": row.row_version}


async def restore_contract(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    contract_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> ContractOut:
    await live_staff(session, staff_id)
    row = await get_including_deleted(session, StaffContract, contract_id)
    if row is None or row.staff_id != staff_id:
        raise NotFound(
            "The contract does not exist",
            message_key="staff.error.contract_not_found",
        )
    await _assert_single_active(session, staff_id, current_id=row.id, status=row.status)
    await restore(
        session,
        row,
        action="staff.contracts.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="staff_contract",
    )
    await session.flush()
    await session.commit()
    return contract_out(row)


__all__ = [
    "create_contract",
    "delete_contract",
    "list_contracts",
    "restore_contract",
    "update_contract",
]
