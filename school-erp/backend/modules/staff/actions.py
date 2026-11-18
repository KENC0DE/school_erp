"""Action-registry entry points for staff records.

Routers and the future AI layer share these functions so permissions,
validation and audit entries stay identical.
"""

from __future__ import annotations

import uuid

from core.actions.registry import ActionContext, action

from modules.staff import contracts, profiles, qualifications, structure
from modules.staff.schemas import (
    AccountLink,
    ContractInput,
    ContractList,
    ContractOut,
    ContractUpdate,
    DepartmentInput,
    DepartmentList,
    DepartmentOut,
    DepartmentUpdate,
    PositionInput,
    PositionList,
    PositionOut,
    PositionUpdate,
    QualificationInput,
    QualificationList,
    QualificationOut,
    QualificationUpdate,
    StaffCreate,
    StaffList,
    StaffOut,
    StaffQuery,
    StaffUpdate,
)


def _id(payload: dict, key: str) -> uuid.UUID:
    return uuid.UUID(str(payload[key]))


def _body(payload: dict, *path_keys: str) -> dict:
    return {key: value for key, value in payload.items() if key not in path_keys}


def _include_contracts(ctx: ActionContext) -> bool:
    return ctx.principal.can("staff.contracts.view")


# ------------------------------------------------------------------ departments


@action(
    key="staff.departments.search",
    module="staff",
    permission="staff.view",
    risk="read",
    describe="List departments",
    output=DepartmentList,
)
async def search_departments(ctx: ActionContext, payload: dict | None = None) -> DepartmentList:
    return await structure.list_departments(
        ctx.session, include_inactive=bool((payload or {}).get("include_inactive"))
    )


@action(
    key="staff.departments.get",
    module="staff",
    permission="staff.view",
    risk="read",
    describe="Read one department",
    output=DepartmentOut,
)
async def get_department(ctx: ActionContext, payload: dict) -> DepartmentOut:
    return await structure.get_department(ctx.session, _id(payload, "department_id"))


@action(
    key="staff.departments.create",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Create a department",
    input=DepartmentInput,
    output=DepartmentOut,
)
async def create_department(ctx: ActionContext, payload: dict) -> DepartmentOut:
    data = DepartmentInput.model_validate(_body(payload, "department_id"))
    return await structure.create_department(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="staff.departments.update",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Update a department",
    input=DepartmentUpdate,
    output=DepartmentOut,
)
async def update_department(ctx: ActionContext, payload: dict) -> DepartmentOut:
    data = DepartmentUpdate.model_validate(payload)
    return await structure.update_department(
        ctx.session, ctx.principal, _id(payload, "department_id"), data, via=ctx.via
    )


# -------------------------------------------------------------------- positions


@action(
    key="staff.positions.search",
    module="staff",
    permission="staff.view",
    risk="read",
    describe="List positions",
    output=PositionList,
)
async def search_positions(ctx: ActionContext, payload: dict | None = None) -> PositionList:
    values = payload or {}
    department_id = values.get("department_id")
    return await structure.list_positions(
        ctx.session,
        department_id=uuid.UUID(str(department_id)) if department_id else None,
        include_inactive=bool(values.get("include_inactive")),
    )


@action(
    key="staff.positions.get",
    module="staff",
    permission="staff.view",
    risk="read",
    describe="Read one position",
    output=PositionOut,
)
async def get_position(ctx: ActionContext, payload: dict) -> PositionOut:
    return await structure.get_position(ctx.session, _id(payload, "position_id"))


@action(
    key="staff.positions.create",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Create a position",
    input=PositionInput,
    output=PositionOut,
)
async def create_position(ctx: ActionContext, payload: dict) -> PositionOut:
    data = PositionInput.model_validate(_body(payload, "position_id"))
    return await structure.create_position(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="staff.positions.update",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Update a position",
    input=PositionUpdate,
    output=PositionOut,
)
async def update_position(ctx: ActionContext, payload: dict) -> PositionOut:
    data = PositionUpdate.model_validate(payload)
    return await structure.update_position(
        ctx.session, ctx.principal, _id(payload, "position_id"), data, via=ctx.via
    )


# ----------------------------------------------------------------------- staff


@action(
    key="staff.search",
    module="staff",
    permission="staff.view",
    risk="read",
    describe="Search and filter staff records",
    input=StaffQuery,
    output=StaffList,
)
async def search_staff(ctx: ActionContext, payload: dict | None = None) -> StaffList:
    query = StaffQuery.model_validate(payload or {})
    return await profiles.list_staff(ctx.session, ctx.principal, query)


@action(
    key="staff.get",
    module="staff",
    permission="staff.view",
    risk="read",
    describe="Read one staff record with contracts and qualifications",
    output=StaffOut,
)
async def get_staff(ctx: ActionContext, payload: dict) -> StaffOut:
    return await profiles.get_staff(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        include_contracts=_include_contracts(ctx),
    )


@action(
    key="staff.create",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Create a staff record on a person",
    input=StaffCreate,
    output=StaffOut,
)
async def create_staff(ctx: ActionContext, payload: dict) -> StaffOut:
    data = StaffCreate.model_validate(_body(payload, "staff_id"))
    return await profiles.create_staff(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="staff.update",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Update a staff record",
    input=StaffUpdate,
    output=StaffOut,
)
async def update_staff(ctx: ActionContext, payload: dict) -> StaffOut:
    data = StaffUpdate.model_validate(payload)
    return await profiles.update_staff(
        ctx.session, ctx.principal, _id(payload, "staff_id"), data, via=ctx.via
    )


@action(
    key="staff.delete",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Soft-delete a staff record",
)
async def delete_staff(ctx: ActionContext, payload: dict) -> dict:
    return await profiles.delete_staff(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        row_version=payload.get("row_version"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="staff.restore",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Restore a soft-deleted staff record",
    output=StaffOut,
)
async def restore_staff(ctx: ActionContext, payload: dict) -> StaffOut:
    return await profiles.restore_staff(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="staff.account.link",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Link a user account to a staff record",
    input=AccountLink,
    output=StaffOut,
)
async def link_account(ctx: ActionContext, payload: dict) -> StaffOut:
    data = AccountLink.model_validate(_body(payload, "staff_id"))
    return await profiles.link_account(
        ctx.session, ctx.principal, _id(payload, "staff_id"), data, via=ctx.via
    )


@action(
    key="staff.account.unlink",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Unlink a user account from a staff record",
    output=StaffOut,
)
async def unlink_account(ctx: ActionContext, payload: dict) -> StaffOut:
    return await profiles.unlink_account(ctx.session, ctx.principal, _id(payload, "staff_id"), via=ctx.via)


# ------------------------------------------------------------------- contracts


@action(
    key="staff.contracts.search",
    module="staff",
    permission="staff.contracts.view",
    risk="read",
    describe="List a staff member's contracts, including salary",
    output=ContractList,
)
async def search_contracts(ctx: ActionContext, payload: dict) -> ContractList:
    return await contracts.list_contracts(ctx.session, _id(payload, "staff_id"))


@action(
    key="staff.contracts.create",
    module="staff",
    permission="staff.contracts.manage",
    risk="write",
    describe="Create an employment contract",
    input=ContractInput,
    output=ContractOut,
)
async def create_contract(ctx: ActionContext, payload: dict) -> ContractOut:
    data = ContractInput.model_validate(_body(payload, "staff_id", "contract_id"))
    return await contracts.create_contract(
        ctx.session, ctx.principal, _id(payload, "staff_id"), data, via=ctx.via
    )


@action(
    key="staff.contracts.update",
    module="staff",
    permission="staff.contracts.manage",
    risk="write",
    describe="Update an employment contract",
    input=ContractUpdate,
    output=ContractOut,
)
async def update_contract(ctx: ActionContext, payload: dict) -> ContractOut:
    data = ContractUpdate.model_validate(payload)
    return await contracts.update_contract(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        _id(payload, "contract_id"),
        data,
        via=ctx.via,
    )


@action(
    key="staff.contracts.delete",
    module="staff",
    permission="staff.contracts.manage",
    risk="write",
    describe="Soft-delete an employment contract",
)
async def delete_contract(ctx: ActionContext, payload: dict) -> dict:
    return await contracts.delete_contract(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        _id(payload, "contract_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="staff.contracts.restore",
    module="staff",
    permission="staff.contracts.manage",
    risk="write",
    describe="Restore a soft-deleted employment contract",
    output=ContractOut,
)
async def restore_contract(ctx: ActionContext, payload: dict) -> ContractOut:
    return await contracts.restore_contract(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        _id(payload, "contract_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


# -------------------------------------------------------------- qualifications


@action(
    key="staff.qualifications.search",
    module="staff",
    permission="staff.view",
    risk="read",
    describe="List a staff member's qualifications",
    output=QualificationList,
)
async def search_qualifications(ctx: ActionContext, payload: dict) -> QualificationList:
    return await qualifications.list_qualifications(ctx.session, _id(payload, "staff_id"))


@action(
    key="staff.qualifications.create",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Add a qualification to a staff record",
    input=QualificationInput,
    output=QualificationOut,
)
async def create_qualification(ctx: ActionContext, payload: dict) -> QualificationOut:
    data = QualificationInput.model_validate(_body(payload, "staff_id", "qualification_id"))
    return await qualifications.create_qualification(
        ctx.session, ctx.principal, _id(payload, "staff_id"), data, via=ctx.via
    )


@action(
    key="staff.qualifications.update",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Update a staff qualification",
    input=QualificationUpdate,
    output=QualificationOut,
)
async def update_qualification(ctx: ActionContext, payload: dict) -> QualificationOut:
    data = QualificationUpdate.model_validate(payload)
    return await qualifications.update_qualification(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        _id(payload, "qualification_id"),
        data,
        via=ctx.via,
    )


@action(
    key="staff.qualifications.delete",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Soft-delete a staff qualification",
)
async def delete_qualification(ctx: ActionContext, payload: dict) -> dict:
    return await qualifications.delete_qualification(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        _id(payload, "qualification_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="staff.qualifications.restore",
    module="staff",
    permission="staff.manage",
    risk="write",
    describe="Restore a soft-deleted staff qualification",
    output=QualificationOut,
)
async def restore_qualification(ctx: ActionContext, payload: dict) -> QualificationOut:
    return await qualifications.restore_qualification(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        _id(payload, "qualification_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


__all__ = [
    "create_contract",
    "create_department",
    "create_position",
    "create_qualification",
    "create_staff",
    "delete_contract",
    "delete_qualification",
    "delete_staff",
    "get_department",
    "get_position",
    "get_staff",
    "link_account",
    "restore_contract",
    "restore_qualification",
    "restore_staff",
    "search_contracts",
    "search_departments",
    "search_positions",
    "search_qualifications",
    "search_staff",
    "unlink_account",
    "update_contract",
    "update_department",
    "update_position",
    "update_qualification",
    "update_staff",
]
