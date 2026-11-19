"""Action-registry entry points for leave types, balances and requests."""

from __future__ import annotations

import uuid
from datetime import date

from app.errors import ValidationFailed
from core.actions.registry import ActionContext, action

from modules.staff import leave_balances, leave_requests, leave_types
from modules.staff.leave_schemas import (
    LeaveBalanceInput,
    LeaveBalanceList,
    LeaveBalanceOut,
    LeaveCalendarOut,
    LeaveDecisionInput,
    LeaveRequestInput,
    LeaveRequestList,
    LeaveRequestOut,
    LeaveRequestUpdate,
    LeaveTypeInput,
    LeaveTypeList,
    LeaveTypeOut,
    LeaveTypeUpdate,
)


def _id(payload: dict, key: str) -> uuid.UUID:
    return uuid.UUID(str(payload[key]))


def _optional_id(payload: dict, key: str) -> uuid.UUID | None:
    value = payload.get(key)
    return uuid.UUID(str(value)) if value else None


def _optional_date(payload: dict, key: str) -> date | None:
    value = payload.get(key)
    return date.fromisoformat(str(value)) if value else None


def _body(payload: dict, *path_keys: str) -> dict:
    return {key: value for key, value in payload.items() if key not in path_keys}


# ----------------------------------------------------------------- leave types


@action(
    key="staff.leave_types.search",
    module="staff",
    permission="staff.leave.view",
    risk="read",
    describe="List leave types",
    output=LeaveTypeList,
)
async def search_leave_types(ctx: ActionContext, payload: dict | None = None) -> LeaveTypeList:
    return await leave_types.list_leave_types(
        ctx.session, include_inactive=bool((payload or {}).get("include_inactive"))
    )


@action(
    key="staff.leave_types.get",
    module="staff",
    permission="staff.leave.view",
    risk="read",
    describe="Read one leave type",
    output=LeaveTypeOut,
)
async def get_leave_type(ctx: ActionContext, payload: dict) -> LeaveTypeOut:
    return await leave_types.get_leave_type(ctx.session, _id(payload, "leave_type_id"))


@action(
    key="staff.leave_types.create",
    module="staff",
    permission="staff.leave.manage",
    risk="write",
    describe="Create a leave type",
    input=LeaveTypeInput,
    output=LeaveTypeOut,
)
async def create_leave_type(ctx: ActionContext, payload: dict) -> LeaveTypeOut:
    data = LeaveTypeInput.model_validate(_body(payload, "leave_type_id"))
    return await leave_types.create_leave_type(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="staff.leave_types.update",
    module="staff",
    permission="staff.leave.manage",
    risk="write",
    describe="Update a leave type",
    input=LeaveTypeUpdate,
    output=LeaveTypeOut,
)
async def update_leave_type(ctx: ActionContext, payload: dict) -> LeaveTypeOut:
    data = LeaveTypeUpdate.model_validate(payload)
    return await leave_types.update_leave_type(
        ctx.session, ctx.principal, _id(payload, "leave_type_id"), data, via=ctx.via
    )


# -------------------------------------------------------------- leave balances


@action(
    key="staff.leave_balances.search",
    module="staff",
    permission="staff.leave.view",
    risk="read",
    describe="List leave balances",
    output=LeaveBalanceList,
)
async def search_leave_balances(ctx: ActionContext, payload: dict | None = None) -> LeaveBalanceList:
    values = payload or {}
    return await leave_balances.list_leave_balances(
        ctx.session,
        ctx.principal,
        staff_id=_optional_id(values, "staff_id"),
        year_id=_optional_id(values, "year_id"),
        leave_type_id=_optional_id(values, "leave_type_id"),
    )


@action(
    key="staff.leave_balances.set",
    module="staff",
    permission="staff.leave.manage",
    risk="write",
    describe="Create or update a staff leave balance",
    input=LeaveBalanceInput,
    output=LeaveBalanceOut,
)
async def set_leave_balance(ctx: ActionContext, payload: dict) -> LeaveBalanceOut:
    data = LeaveBalanceInput.model_validate(payload)
    return await leave_balances.set_leave_balance(ctx.session, ctx.principal, data, via=ctx.via)


# -------------------------------------------------------------- leave requests


@action(
    key="staff.leave_requests.search",
    module="staff",
    permission="staff.leave.view",
    risk="read",
    describe="List leave requests",
    output=LeaveRequestList,
)
async def search_leave_requests(ctx: ActionContext, payload: dict | None = None) -> LeaveRequestList:
    values = payload or {}
    status = values.get("status")
    return await leave_requests.list_leave_requests(
        ctx.session,
        ctx.principal,
        staff_id=_optional_id(values, "staff_id"),
        year_id=_optional_id(values, "year_id"),
        leave_type_id=_optional_id(values, "leave_type_id"),
        status=status if status else None,
        from_date=_optional_date(values, "from_date"),
        to_date=_optional_date(values, "to_date"),
    )


@action(
    key="staff.leave_requests.get",
    module="staff",
    permission="staff.leave.view",
    risk="read",
    describe="Read one leave request",
    output=LeaveRequestOut,
)
async def get_leave_request(ctx: ActionContext, payload: dict) -> LeaveRequestOut:
    return await leave_requests.get_leave_request(ctx.session, ctx.principal, _id(payload, "request_id"))


@action(
    key="staff.leave_requests.create",
    module="staff",
    permission="staff.leave.request",
    risk="write",
    describe="Create a draft leave request",
    input=LeaveRequestInput,
    output=LeaveRequestOut,
)
async def create_leave_request(ctx: ActionContext, payload: dict) -> LeaveRequestOut:
    data = LeaveRequestInput.model_validate(_body(payload, "request_id"))
    return await leave_requests.create_leave_request(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="staff.leave_requests.update",
    module="staff",
    permission="staff.leave.request",
    risk="write",
    describe="Edit a draft leave request",
    input=LeaveRequestUpdate,
    output=LeaveRequestOut,
)
async def update_leave_request(ctx: ActionContext, payload: dict) -> LeaveRequestOut:
    data = LeaveRequestUpdate.model_validate(payload)
    return await leave_requests.update_leave_request(
        ctx.session, ctx.principal, _id(payload, "request_id"), data, via=ctx.via
    )


@action(
    key="staff.leave_requests.submit",
    module="staff",
    permission="staff.leave.request",
    risk="write",
    describe="Submit a draft leave request",
    output=LeaveRequestOut,
)
async def submit_leave_request(ctx: ActionContext, payload: dict) -> LeaveRequestOut:
    return await leave_requests.submit_leave_request(
        ctx.session, ctx.principal, _id(payload, "request_id"), via=ctx.via
    )


@action(
    key="staff.leave_requests.approve",
    module="staff",
    permission="staff.leave.approve",
    risk="write",
    describe="Approve a submitted leave request",
    input=LeaveDecisionInput,
    output=LeaveRequestOut,
)
async def approve_leave_request(ctx: ActionContext, payload: dict) -> LeaveRequestOut:
    note = payload.get("note")
    data = LeaveDecisionInput.model_validate({"note": note}) if note is not None else None
    return await leave_requests.approve_leave_request(
        ctx.session, ctx.principal, _id(payload, "request_id"), data, via=ctx.via
    )


@action(
    key="staff.leave_requests.reject",
    module="staff",
    permission="staff.leave.approve",
    risk="write",
    describe="Reject a submitted leave request",
    input=LeaveDecisionInput,
    output=LeaveRequestOut,
)
async def reject_leave_request(ctx: ActionContext, payload: dict) -> LeaveRequestOut:
    note = payload.get("note")
    data = LeaveDecisionInput.model_validate({"note": note}) if note is not None else None
    return await leave_requests.reject_leave_request(
        ctx.session, ctx.principal, _id(payload, "request_id"), data, via=ctx.via
    )


@action(
    key="staff.leave_requests.cancel",
    module="staff",
    permission="staff.leave.request",
    risk="write",
    describe="Cancel a leave request",
    output=LeaveRequestOut,
)
async def cancel_leave_request(ctx: ActionContext, payload: dict) -> LeaveRequestOut:
    return await leave_requests.cancel_leave_request(
        ctx.session,
        ctx.principal,
        _id(payload, "request_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="staff.leave_calendar.get",
    module="staff",
    permission="staff.leave.view",
    risk="read",
    describe="Read leave requests overlapping a date range",
    output=LeaveCalendarOut,
)
async def get_leave_calendar(ctx: ActionContext, payload: dict) -> LeaveCalendarOut:
    from_date = _optional_date(payload, "from_date")
    to_date = _optional_date(payload, "to_date")
    if from_date is None or to_date is None:
        raise ValidationFailed(
            "A calendar range needs both a start and an end date",
            message_key="staff.error.leave_dates",
        )
    status = payload.get("status")
    return await leave_requests.leave_calendar(
        ctx.session,
        ctx.principal,
        from_date=from_date,
        to_date=to_date,
        year_id=_optional_id(payload, "year_id"),
        leave_type_id=_optional_id(payload, "leave_type_id"),
        status=status if status else None,
    )


__all__ = [
    "approve_leave_request",
    "cancel_leave_request",
    "create_leave_request",
    "create_leave_type",
    "get_leave_calendar",
    "get_leave_request",
    "get_leave_type",
    "reject_leave_request",
    "search_leave_balances",
    "search_leave_requests",
    "search_leave_types",
    "set_leave_balance",
    "submit_leave_request",
    "update_leave_request",
    "update_leave_type",
]
