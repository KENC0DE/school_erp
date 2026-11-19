"""Staff qualifications: education, training, certification and experience."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import get_including_deleted, restore, soft_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.staff.common import (
    MODULE,
    live_qualification,
    live_staff,
    qualification_state,
)
from modules.staff.models import StaffQualification
from modules.staff.schemas import (
    QUALIFICATION_KINDS,
    QualificationInput,
    QualificationList,
    QualificationOut,
    QualificationUpdate,
)
from modules.staff.views import qualification_out

KIND_VALUES = set(QUALIFICATION_KINDS)


def _assert_values(kind: str) -> None:
    if kind not in KIND_VALUES:
        raise ValidationFailed(
            "Unknown qualification kind",
            message_key="staff.error.qualification_kind_invalid",
            details={"kind": kind},
        )


def _assert_dates(start_date, end_date) -> None:  # type: ignore[no-untyped-def]
    if start_date and end_date and end_date < start_date:
        raise ValidationFailed(
            "The qualification end date cannot be before its start date",
            message_key="staff.error.dates_invalid",
        )


async def list_qualifications(session: AsyncSession, staff_id: uuid.UUID) -> QualificationList:
    await live_staff(session, staff_id)
    rows = (
        (
            await session.execute(
                select(StaffQualification)
                .where(
                    StaffQualification.staff_id == staff_id,
                    StaffQualification.deleted_at.is_(None),
                )
                .order_by(
                    StaffQualification.start_date.desc().nullslast(),
                    StaffQualification.id,
                )
            )
        )
        .scalars()
        .all()
    )
    return QualificationList(items=[qualification_out(row) for row in rows], total=len(rows))


async def create_qualification(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    data: QualificationInput,
    *,
    via: str = "api",
) -> QualificationOut:
    await live_staff(session, staff_id)
    _assert_values(data.kind)
    _assert_dates(data.start_date, data.end_date)
    row = StaffQualification(staff_id=staff_id, **data.model_dump())
    session.add(row)
    await session.flush()
    await record(
        session,
        action="staff.qualifications.create",
        module=MODULE,
        entity_type="staff_qualification",
        entity_id=str(row.id),
        after=qualification_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return qualification_out(row)


async def update_qualification(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    qualification_id: uuid.UUID,
    data: QualificationUpdate,
    *,
    via: str = "api",
) -> QualificationOut:
    row = await live_qualification(session, staff_id, qualification_id)
    before = qualification_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    _assert_values(payload.get("kind", row.kind))
    _assert_dates(payload.get("start_date", row.start_date), payload.get("end_date", row.end_date))

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
            action="staff.qualifications.update",
            module=MODULE,
            entity_type="staff_qualification",
            entity_id=str(row.id),
            before=before,
            after=qualification_state(row),
            actor=principal,
            via=via,
        )
    await session.commit()
    return qualification_out(row)


async def delete_qualification(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    qualification_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await live_qualification(session, staff_id, qualification_id)
    changed = await soft_delete(
        session,
        row,
        action="staff.qualifications.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="staff_qualification",
    )
    await session.flush()
    await session.commit()
    return {"id": str(row.id), "deleted": bool(changed), "row_version": row.row_version}


async def restore_qualification(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    qualification_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> QualificationOut:
    await live_staff(session, staff_id)
    row = await get_including_deleted(session, StaffQualification, qualification_id)
    if row is None or row.staff_id != staff_id:
        raise NotFound(
            "The qualification does not exist",
            message_key="staff.error.qualification_not_found",
        )
    await restore(
        session,
        row,
        action="staff.qualifications.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="staff_qualification",
    )
    await session.flush()
    await session.commit()
    return qualification_out(row)


__all__ = [
    "create_qualification",
    "delete_qualification",
    "list_qualifications",
    "restore_qualification",
    "update_qualification",
]
