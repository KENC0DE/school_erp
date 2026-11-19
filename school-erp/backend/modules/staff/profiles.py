"""Staff profiles: registration, search, detail, account linking and restore."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import Conflict, Forbidden, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.api.pagination import PageParams, contains, paginate
from core.audit.service import record
from core.auth.models import User
from core.auth.principal import Principal
from core.custom_fields.service import merge_custom, validate_entity_values
from core.db.soft_delete import get_including_deleted, restore, soft_delete
from core.people.models import Person, normalize_name
from core.people.service import create_person, prepare_person, update_person
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.staff import numbering, scopes
from modules.staff.common import (
    MODULE,
    live_department,
    live_person,
    live_position,
    live_staff,
    staff_state,
)
from modules.staff.models import (
    StaffContract,
    StaffDepartment,
    StaffPosition,
    StaffProfile,
    StaffQualification,
)
from modules.staff.schemas import (
    STAFF_STATUSES,
    AccountLink,
    StaffCreate,
    StaffList,
    StaffOut,
    StaffQuery,
    StaffSummary,
    StaffUpdate,
)
from modules.staff.views import staff_out, staff_summary

SORT_COLUMNS = {
    "created_at": StaffProfile.created_at,
    "staff_number": StaffProfile.staff_number,
    "status": StaffProfile.status,
    "hire_date": StaffProfile.hire_date,
}
STATUS_VALUES = set(STAFF_STATUSES)


def _assert_status(value: str) -> None:
    if value not in STATUS_VALUES:
        raise ValidationFailed(
            "Unknown staff status",
            message_key="staff.error.status_invalid",
            details={"status": value},
        )


async def _assert_number_free(
    session: AsyncSession, staff_number: str, *, current_id: uuid.UUID | None = None
) -> None:
    stmt = select(StaffProfile.id).where(
        StaffProfile.staff_number == staff_number,
        StaffProfile.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(StaffProfile.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "A staff member with that number already exists",
            message_key="staff.error.number_taken",
            details={"staff_number": staff_number},
        )


async def _assert_person_free(
    session: AsyncSession, person_id: uuid.UUID, *, current_id: uuid.UUID | None = None
) -> None:
    stmt = select(StaffProfile.id).where(
        StaffProfile.person_id == person_id,
        StaffProfile.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(StaffProfile.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "That person already has a staff record",
            message_key="staff.error.person_exists",
            details={"person_id": str(person_id)},
        )


async def _assert_user_free(
    session: AsyncSession, user_id: uuid.UUID, *, current_id: uuid.UUID | None = None
) -> None:
    stmt = select(StaffProfile.id).where(
        StaffProfile.user_id == user_id,
        StaffProfile.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(StaffProfile.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "That user account is already linked to another staff member",
            message_key="staff.error.user_taken",
            details={"user_id": str(user_id)},
        )


async def _resolve_placement(
    session: AsyncSession,
    department_id: uuid.UUID | None,
    position_id: uuid.UUID | None,
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Validate the department/position pair and default the department from the position."""
    position = await live_position(session, position_id) if position_id is not None else None
    if position is not None and not position.is_active:
        raise ValidationFailed(
            "An inactive position cannot be assigned",
            message_key="staff.error.position_inactive",
        )
    department = await live_department(session, department_id) if department_id is not None else None
    if department is not None and not department.is_active:
        raise ValidationFailed(
            "An inactive department cannot be assigned",
            message_key="staff.error.department_inactive",
        )
    if position is not None and position.department_id is not None:
        if department is None:
            department = await live_department(session, position.department_id)
        elif department.id != position.department_id:
            raise ValidationFailed(
                "The position belongs to a different department",
                message_key="staff.error.position_department_mismatch",
                details={
                    "position_id": str(position.id),
                    "department_id": str(department.id),
                },
            )
    return (
        department.id if department is not None else None,
        position.id if position is not None else None,
    )


def _department_and_position(
    row: StaffProfile,
    departments: dict[uuid.UUID, StaffDepartment],
    positions: dict[uuid.UUID, StaffPosition],
) -> tuple[StaffDepartment | None, StaffPosition | None]:
    return (
        departments.get(row.department_id) if row.department_id else None,
        positions.get(row.position_id) if row.position_id else None,
    )


async def _related_maps(
    session: AsyncSession, rows: list[StaffProfile]
) -> tuple[
    dict[uuid.UUID, Person],
    dict[uuid.UUID, StaffDepartment],
    dict[uuid.UUID, StaffPosition],
]:
    people = {
        row.id: row
        for row in (
            await session.execute(select(Person).where(Person.id.in_([item.person_id for item in rows])))
        )
        .scalars()
        .all()
    }
    department_ids = {row.department_id for row in rows if row.department_id is not None}
    departments = {
        row.id: row
        for row in (
            await session.execute(select(StaffDepartment).where(StaffDepartment.id.in_(department_ids)))
        )
        .scalars()
        .all()
    }
    position_ids = {row.position_id for row in rows if row.position_id is not None}
    positions = {
        row.id: row
        for row in (await session.execute(select(StaffPosition).where(StaffPosition.id.in_(position_ids))))
        .scalars()
        .all()
    }
    return people, departments, positions


async def list_staff(
    session: AsyncSession,
    principal: Principal | None,
    query: StaffQuery,
) -> StaffList:
    stmt = (
        select(StaffProfile)
        .join(Person, Person.id == StaffProfile.person_id)
        .where(StaffProfile.deleted_at.is_(None), Person.deleted_at.is_(None))
    )
    if query.status is not None:
        _assert_status(query.status)
        stmt = stmt.where(StaffProfile.status == query.status)
    if query.department_id is not None:
        stmt = stmt.where(StaffProfile.department_id == query.department_id)
    if query.position_id is not None:
        stmt = stmt.where(StaffProfile.position_id == query.position_id)
    if query.linked is not None:
        stmt = stmt.where(
            StaffProfile.user_id.is_not(None) if query.linked else StaffProfile.user_id.is_(None)
        )
    if query.q:
        terms = normalize_name(query.q).split()
        matches: list[Any] = [contains(StaffProfile.staff_number, query.q)]
        if terms:
            matches.append(and_(*[Person.search_name.like(f"%{term}%") for term in terms]))
        stmt = stmt.where(or_(*matches))
    if principal is not None:
        visible = await scopes.visible_staff_ids(session, principal)
        if visible is not None:
            stmt = stmt.where(StaffProfile.id.in_(visible))

    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows, next_cursor = await paginate(
        session,
        stmt,
        PageParams(
            limit=query.limit,
            cursor=query.cursor,
            sort=query.sort,
            order=query.order,
        ),
        sort_columns=SORT_COLUMNS,
        default_sort="created_at",
        id_column=StaffProfile.id,
    )
    people, departments, positions = await _related_maps(session, rows)
    items: list[StaffSummary] = []
    for row in rows:
        person = people.get(row.person_id)
        if person is None:
            continue
        department, position = _department_and_position(row, departments, positions)
        items.append(
            staff_summary(
                row,
                person,
                locale=principal.locale if principal else "en",
                department=department,
                position=position,
            )
        )
    return StaffList(items=items, next_cursor=next_cursor, total=total)


async def staff_detail(
    session: AsyncSession,
    principal: Principal | None,
    profile: StaffProfile,
    *,
    include_contracts: bool = False,
) -> StaffOut:
    person = await live_person(session, profile.person_id)
    department = await live_department(session, profile.department_id) if profile.department_id else None
    position = await live_position(session, profile.position_id) if profile.position_id else None
    contracts = (
        (
            await session.execute(
                select(StaffContract)
                .where(
                    StaffContract.staff_id == profile.id,
                    StaffContract.deleted_at.is_(None),
                )
                .order_by(StaffContract.start_date.desc(), StaffContract.id)
            )
        )
        .scalars()
        .all()
        if include_contracts
        else []
    )
    qualifications = (
        (
            await session.execute(
                select(StaffQualification)
                .where(
                    StaffQualification.staff_id == profile.id,
                    StaffQualification.deleted_at.is_(None),
                )
                .order_by(StaffQualification.start_date.desc().nullslast(), StaffQualification.id)
            )
        )
        .scalars()
        .all()
    )
    return staff_out(
        profile,
        person,
        locale=principal.locale if principal else "en",
        department=department,
        position=position,
        contracts=list(contracts),
        qualifications=list(qualifications),
        contracts_restricted=not include_contracts,
    )


async def get_staff(
    session: AsyncSession,
    principal: Principal | None,
    staff_id: uuid.UUID,
    *,
    include_contracts: bool = False,
) -> StaffOut:
    profile = await live_staff(session, staff_id)
    if principal is not None:
        visible = await scopes.visible_staff_ids(session, principal)
        if visible is not None and profile.id not in visible:
            raise Forbidden(
                "This staff record is outside your department",
                message_key="error.scope_denied",
                details={"staff_id": str(profile.id)},
            )
    return await staff_detail(
        session,
        principal,
        profile,
        include_contracts=include_contracts,
    )


async def _assert_person_not_staff(session: AsyncSession, person_input: dict[str, Any]) -> None:
    """Reject a new staff record when the person is already on staff.

    ``create_person`` always inserts a new person row, so a second submission of
    the same person would otherwise pass ``_assert_person_free``. Prepare the
    candidate first and look for a live person with the same identity (exact
    name triplet and date of birth, or the same email or phone) that already
    owns a staff profile.
    """
    candidate, warnings = await prepare_person(session, person_input)
    person_ids = {
        uuid.UUID(warning["person"]["id"])
        for warning in warnings
        if warning.get("reason") == "same_names_and_dob"
    }
    matches: list[Any] = []
    if candidate.email:
        matches.append(Person.email == candidate.email)
    if candidate.phone:
        matches.append(Person.phone == candidate.phone)
    if person_ids:
        matches.append(Person.id.in_(person_ids))
    if not matches:
        return
    existing = (
        await session.execute(
            select(StaffProfile.person_id)
            .join(Person, Person.id == StaffProfile.person_id)
            .where(
                StaffProfile.deleted_at.is_(None),
                Person.deleted_at.is_(None),
                or_(*matches),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise Conflict(
            "That person already has a staff record",
            message_key="staff.error.person_exists",
            details={"person_id": str(existing)},
        )


async def create_staff(
    session: AsyncSession,
    principal: Principal,
    data: StaffCreate,
    *,
    via: str = "api",
) -> StaffOut:
    if data.person_id is not None:
        person = await live_person(session, data.person_id)
        await _assert_person_free(session, person.id)
    else:
        assert data.person is not None  # guaranteed by the schema validator
        await _assert_person_not_staff(session, data.person.model_dump())
        person, _warnings = await create_person(
            session,
            principal,
            data.person.model_dump(),
            via=via,
            commit=False,
        )
        await _assert_person_free(session, person.id)
    staff_number = data.staff_number
    if staff_number is None:
        staff_number = (await numbering.allocate_number(session)).staff_number
    await _assert_number_free(session, staff_number)
    department_id, position_id = await _resolve_placement(session, data.department_id, data.position_id)
    _assert_status(data.status)
    custom = None
    if data.custom is not None:
        cleaned = await validate_entity_values(session, "staff", data.custom)
        custom = merge_custom(None, cleaned)

    row = StaffProfile(
        person_id=person.id,
        staff_number=staff_number,
        status=data.status,
        department_id=department_id,
        position_id=position_id,
        hire_date=data.hire_date,
        end_date=data.end_date,
        notes=data.notes,
        custom=custom,
    )
    session.add(row)
    await session.flush()
    await record(
        session,
        action="staff.create",
        module=MODULE,
        entity_type="staff",
        entity_id=str(row.id),
        after=staff_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await staff_detail(
        session, principal, row, include_contracts=principal.can("staff.contracts.view")
    )


async def update_staff(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    data: StaffUpdate,
    *,
    via: str = "api",
) -> StaffOut:
    row = await live_staff(session, staff_id)
    before = staff_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)

    if payload.get("person"):
        await update_person(
            session,
            principal,
            row.person_id,
            payload.pop("person"),
            via=via,
            commit=False,
        )
    if "staff_number" in payload:
        await _assert_number_free(session, payload["staff_number"], current_id=row.id)
    if "status" in payload:
        _assert_status(payload["status"])
    if "department_id" in payload or "position_id" in payload:
        department_id = payload.get("department_id", row.department_id)
        position_id = payload.get("position_id", row.position_id)
        department_id, position_id = await _resolve_placement(session, department_id, position_id)
        payload["department_id"] = department_id
        payload["position_id"] = position_id
    if "custom" in payload:
        cleaned = await validate_entity_values(session, "staff", payload["custom"], partial=True)
        payload["custom"] = merge_custom(row.custom, cleaned)

    if payload.get("hire_date") and payload.get("end_date"):
        if payload["end_date"] < payload["hire_date"]:
            raise ValidationFailed(
                "The end date cannot be before the hire date",
                message_key="staff.error.dates_invalid",
            )
    elif row.hire_date and payload.get("end_date") and payload["end_date"] < row.hire_date:
        raise ValidationFailed(
            "The end date cannot be before the hire date",
            message_key="staff.error.dates_invalid",
        )
    elif payload.get("hire_date") and row.end_date and row.end_date < payload["hire_date"]:
        raise ValidationFailed(
            "The end date cannot be before the hire date",
            message_key="staff.error.dates_invalid",
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
            action="staff.update",
            module=MODULE,
            entity_type="staff",
            entity_id=str(row.id),
            before=before,
            after=staff_state(row),
            actor=principal,
            via=via,
        )
    await session.commit()
    return await staff_detail(
        session, principal, row, include_contracts=principal.can("staff.contracts.view")
    )


async def link_account(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    data: AccountLink,
    *,
    via: str = "api",
) -> StaffOut:
    row = await live_staff(session, staff_id)
    user = (await session.execute(select(User).where(User.id == data.user_id))).scalar_one_or_none()
    if user is None:
        raise NotFound("The user account does not exist", message_key="staff.error.user_not_found")
    if not user.is_active:
        raise ValidationFailed(
            "An inactive user account cannot be linked",
            message_key="staff.error.user_inactive",
        )
    await _assert_user_free(session, user.id, current_id=row.id)
    before = staff_state(row)
    row.user_id = user.id
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="staff.account.link",
        module=MODULE,
        entity_type="staff",
        entity_id=str(row.id),
        before=before,
        after=staff_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await staff_detail(
        session, principal, row, include_contracts=principal.can("staff.contracts.view")
    )


async def unlink_account(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    *,
    via: str = "api",
) -> StaffOut:
    row = await live_staff(session, staff_id)
    if row.user_id is None:
        return await staff_detail(
            session, principal, row, include_contracts=principal.can("staff.contracts.view")
        )
    before = staff_state(row)
    row.user_id = None
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="staff.account.unlink",
        module=MODULE,
        entity_type="staff",
        entity_id=str(row.id),
        before=before,
        after=staff_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await staff_detail(
        session, principal, row, include_contracts=principal.can("staff.contracts.view")
    )


async def delete_staff(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    *,
    row_version: int | None = None,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await live_staff(session, staff_id)
    if row_version is not None:
        ensure_row_version(row, row_version, current_state=staff_state(row))
    changed = await soft_delete(
        session,
        row,
        action="staff.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="staff",
    )
    await session.flush()
    await session.commit()
    return {"id": str(row.id), "deleted": bool(changed), "row_version": row.row_version}


async def restore_staff(
    session: AsyncSession,
    principal: Principal,
    staff_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> StaffOut:
    row = await get_including_deleted(session, StaffProfile, staff_id)
    if row is None:
        raise NotFound("The staff member does not exist", message_key="staff.error.not_found")
    await _assert_number_free(session, row.staff_number, current_id=row.id)
    await _assert_person_free(session, row.person_id, current_id=row.id)
    if row.user_id is not None:
        await _assert_user_free(session, row.user_id, current_id=row.id)
    await restore(
        session,
        row,
        action="staff.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="staff",
    )
    await session.flush()
    await session.commit()
    return await staff_detail(
        session, principal, row, include_contracts=principal.can("staff.contracts.view")
    )


__all__ = [
    "create_staff",
    "delete_staff",
    "get_staff",
    "link_account",
    "list_staff",
    "restore_staff",
    "staff_detail",
    "unlink_account",
    "update_staff",
]
