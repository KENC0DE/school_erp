"""Action-registry entry points for payroll.

Routers and the future AI layer share these functions so permissions,
validation and audit entries stay identical.
"""

from __future__ import annotations

import uuid

from core.actions.registry import ActionContext, action

from modules.payroll import components, rules, runs
from modules.payroll.schemas import (
    ComponentInput,
    ComponentList,
    ComponentOut,
    ComponentUpdate,
    PayslipList,
    PayslipOut,
    RuleInput,
    RuleOut,
    RuleSetInput,
    RuleSetList,
    RuleSetOut,
    RuleSetUpdate,
    RuleUpdate,
    RunInput,
    RunList,
    RunOut,
    RunQuery,
    StaffComponentInput,
    StaffComponentList,
    StaffComponentOut,
    StaffComponentUpdate,
)


def _id(payload: dict, key: str) -> uuid.UUID:
    return uuid.UUID(str(payload[key]))


# ------------------------------------------------------------------ components


@action(
    key="payroll.components.search",
    module="payroll",
    permission="payroll.view",
    risk="read",
    describe="List salary components",
    output=ComponentList,
)
async def search_components(ctx: ActionContext, payload: dict | None = None) -> ComponentList:
    return await components.list_components(
        ctx.session,
        include_inactive=bool((payload or {}).get("include_inactive")),
    )


@action(
    key="payroll.components.get",
    module="payroll",
    permission="payroll.view",
    risk="read",
    describe="Read one salary component",
    output=ComponentOut,
)
async def get_component(ctx: ActionContext, payload: dict) -> ComponentOut:
    return await components.get_component(ctx.session, _id(payload, "component_id"))


@action(
    key="payroll.components.create",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Create a salary component",
    input=ComponentInput,
    output=ComponentOut,
)
async def create_component(ctx: ActionContext, payload: dict) -> ComponentOut:
    return await components.create_component(
        ctx.session,
        ctx.principal,
        ComponentInput(**payload),
        via=ctx.via,
    )


@action(
    key="payroll.components.update",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Update a salary component",
    input=ComponentUpdate,
    output=ComponentOut,
)
async def update_component(ctx: ActionContext, payload: dict) -> ComponentOut:
    return await components.update_component(
        ctx.session,
        ctx.principal,
        _id(payload, "component_id"),
        ComponentUpdate(**{key: value for key, value in payload.items() if key != "component_id"}),
        via=ctx.via,
    )


@action(
    key="payroll.components.delete",
    module="payroll",
    permission="payroll.manage",
    risk="destructive",
    describe="Soft-delete an unused salary component",
    output=dict,
)
async def delete_component(ctx: ActionContext, payload: dict) -> dict:
    return await components.delete_component(
        ctx.session,
        ctx.principal,
        _id(payload, "component_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="payroll.components.restore",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Restore a soft-deleted salary component",
    output=ComponentOut,
)
async def restore_component(ctx: ActionContext, payload: dict) -> ComponentOut:
    return await components.restore_component(
        ctx.session,
        ctx.principal,
        _id(payload, "component_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


# ---------------------------------------------------------- staff assignments


@action(
    key="payroll.staff_components.search",
    module="payroll",
    permission="payroll.view",
    risk="read",
    describe="List a staff member's salary components",
    output=StaffComponentList,
)
async def search_staff_components(ctx: ActionContext, payload: dict) -> StaffComponentList:
    return await components.list_staff_components(ctx.session, _id(payload, "staff_id"))


@action(
    key="payroll.staff_components.create",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Assign a salary component to a staff member",
    input=StaffComponentInput,
    output=StaffComponentOut,
)
async def create_staff_component(ctx: ActionContext, payload: dict) -> StaffComponentOut:
    return await components.create_staff_component(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        StaffComponentInput(**{key: value for key, value in payload.items() if key != "staff_id"}),
        via=ctx.via,
    )


@action(
    key="payroll.staff_components.update",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Update a staff member's salary component",
    input=StaffComponentUpdate,
    output=StaffComponentOut,
)
async def update_staff_component(ctx: ActionContext, payload: dict) -> StaffComponentOut:
    return await components.update_staff_component(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        _id(payload, "assignment_id"),
        StaffComponentUpdate(
            **{key: value for key, value in payload.items() if key not in {"staff_id", "assignment_id"}}
        ),
        via=ctx.via,
    )


@action(
    key="payroll.staff_components.delete",
    module="payroll",
    permission="payroll.manage",
    risk="destructive",
    describe="Soft-delete a staff member's salary component",
    output=dict,
)
async def delete_staff_component(ctx: ActionContext, payload: dict) -> dict:
    return await components.delete_staff_component(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        _id(payload, "assignment_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="payroll.staff_components.restore",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Restore a staff member's salary component",
    output=StaffComponentOut,
)
async def restore_staff_component(ctx: ActionContext, payload: dict) -> StaffComponentOut:
    return await components.restore_staff_component(
        ctx.session,
        ctx.principal,
        _id(payload, "staff_id"),
        _id(payload, "assignment_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


# ------------------------------------------------------------------ rule sets


@action(
    key="payroll.rule_sets.search",
    module="payroll",
    permission="payroll.view",
    risk="read",
    describe="List payroll rule sets",
    output=RuleSetList,
)
async def search_rule_sets(ctx: ActionContext, payload: dict | None = None) -> RuleSetList:
    return await rules.list_rule_sets(
        ctx.session,
        include_archived=bool((payload or {}).get("include_archived")),
    )


@action(
    key="payroll.rule_sets.get",
    module="payroll",
    permission="payroll.view",
    risk="read",
    describe="Read one payroll rule set with its rules",
    output=RuleSetOut,
)
async def get_rule_set(ctx: ActionContext, payload: dict) -> RuleSetOut:
    return await rules.get_rule_set(ctx.session, _id(payload, "rule_set_id"))


@action(
    key="payroll.rule_sets.create",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Create a draft payroll rule set",
    input=RuleSetInput,
    output=RuleSetOut,
)
async def create_rule_set(ctx: ActionContext, payload: dict) -> RuleSetOut:
    return await rules.create_rule_set(
        ctx.session,
        ctx.principal,
        RuleSetInput(**payload),
        via=ctx.via,
    )


@action(
    key="payroll.rule_sets.update",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Update a rule set's metadata or accountant flag",
    input=RuleSetUpdate,
    output=RuleSetOut,
)
async def update_rule_set(ctx: ActionContext, payload: dict) -> RuleSetOut:
    return await rules.update_rule_set(
        ctx.session,
        ctx.principal,
        _id(payload, "rule_set_id"),
        RuleSetUpdate(**{key: value for key, value in payload.items() if key != "rule_set_id"}),
        via=ctx.via,
    )


@action(
    key="payroll.rule_sets.activate",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Activate a rule set and archive the previous one",
    output=RuleSetOut,
)
async def activate_rule_set(ctx: ActionContext, payload: dict) -> RuleSetOut:
    return await rules.activate_rule_set(
        ctx.session,
        ctx.principal,
        _id(payload, "rule_set_id"),
        via=ctx.via,
    )


@action(
    key="payroll.rule_sets.archive",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Archive an active rule set",
    output=RuleSetOut,
)
async def archive_rule_set(ctx: ActionContext, payload: dict) -> RuleSetOut:
    return await rules.archive_rule_set(
        ctx.session,
        ctx.principal,
        _id(payload, "rule_set_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="payroll.rule_sets.delete",
    module="payroll",
    permission="payroll.manage",
    risk="destructive",
    describe="Soft-delete an unused rule set",
    output=dict,
)
async def delete_rule_set(ctx: ActionContext, payload: dict) -> dict:
    return await rules.delete_rule_set(
        ctx.session,
        ctx.principal,
        _id(payload, "rule_set_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="payroll.rule_sets.restore",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Restore a soft-deleted rule set",
    output=RuleSetOut,
)
async def restore_rule_set(ctx: ActionContext, payload: dict) -> RuleSetOut:
    return await rules.restore_rule_set(
        ctx.session,
        ctx.principal,
        _id(payload, "rule_set_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


# ---------------------------------------------------------------------- rules


@action(
    key="payroll.rules.create",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Add a rule to a draft rule set",
    input=RuleInput,
    output=RuleOut,
)
async def create_rule(ctx: ActionContext, payload: dict) -> RuleOut:
    rule_set_id = _id(payload, "rule_set_id")
    return await rules.create_rule(
        ctx.session,
        ctx.principal,
        rule_set_id,
        RuleInput(**{key: value for key, value in payload.items() if key != "rule_set_id"}),
        via=ctx.via,
    )


@action(
    key="payroll.rules.update",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Update a rule in a draft rule set",
    input=RuleUpdate,
    output=RuleOut,
)
async def update_rule(ctx: ActionContext, payload: dict) -> RuleOut:
    return await rules.update_rule(
        ctx.session,
        ctx.principal,
        _id(payload, "rule_set_id"),
        _id(payload, "rule_id"),
        RuleUpdate(**{key: value for key, value in payload.items() if key not in {"rule_set_id", "rule_id"}}),
        via=ctx.via,
    )


@action(
    key="payroll.rules.delete",
    module="payroll",
    permission="payroll.manage",
    risk="destructive",
    describe="Soft-delete a rule from a draft rule set",
    output=dict,
)
async def delete_rule(ctx: ActionContext, payload: dict) -> dict:
    return await rules.delete_rule(
        ctx.session,
        ctx.principal,
        _id(payload, "rule_set_id"),
        _id(payload, "rule_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="payroll.rules.restore",
    module="payroll",
    permission="payroll.manage",
    risk="write",
    describe="Restore a rule in a draft rule set",
    output=RuleOut,
)
async def restore_rule(ctx: ActionContext, payload: dict) -> RuleOut:
    return await rules.restore_rule(
        ctx.session,
        ctx.principal,
        _id(payload, "rule_set_id"),
        _id(payload, "rule_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


# ----------------------------------------------------------------------- runs


@action(
    key="payroll.runs.search",
    module="payroll",
    permission="payroll.view",
    risk="read",
    describe="List payroll runs",
    output=RunList,
)
async def search_runs(ctx: ActionContext, payload: dict | None = None) -> RunList:
    payload = payload or {}
    return await runs.list_runs(
        ctx.session,
        RunQuery(
            period_year=payload.get("period_year"),
            period_month=payload.get("period_month"),
            status=payload.get("status"),
        ),
    )


@action(
    key="payroll.runs.get",
    module="payroll",
    permission="payroll.view",
    risk="read",
    describe="Read one payroll run",
    output=RunOut,
)
async def get_run(ctx: ActionContext, payload: dict) -> RunOut:
    return await runs.get_run(ctx.session, _id(payload, "run_id"))


@action(
    key="payroll.runs.create",
    module="payroll",
    permission="payroll.run",
    risk="write",
    describe="Create a draft payroll run for a month",
    input=RunInput,
    output=RunOut,
)
async def create_run(ctx: ActionContext, payload: dict) -> RunOut:
    return await runs.create_run(
        ctx.session,
        ctx.principal,
        RunInput(**payload),
        via=ctx.via,
    )


@action(
    key="payroll.runs.calculate",
    module="payroll",
    permission="payroll.run",
    risk="bulk",
    describe="Calculate or recalculate every payslip in a run",
    output=RunOut,
)
async def calculate_run(ctx: ActionContext, payload: dict) -> RunOut:
    return await runs.calculate_run(
        ctx.session,
        ctx.principal,
        _id(payload, "run_id"),
        via=ctx.via,
    )


@action(
    key="payroll.runs.finalize",
    module="payroll",
    permission="payroll.run",
    risk="write",
    describe="Finalize a calculated payroll run",
    output=RunOut,
)
async def finalize_run(ctx: ActionContext, payload: dict) -> RunOut:
    return await runs.finalize_run(
        ctx.session,
        ctx.principal,
        _id(payload, "run_id"),
        via=ctx.via,
    )


@action(
    key="payroll.runs.delete",
    module="payroll",
    permission="payroll.run",
    risk="destructive",
    describe="Soft-delete an unfinalized payroll run and its payslips",
    output=dict,
)
async def delete_run(ctx: ActionContext, payload: dict) -> dict:
    return await runs.delete_run(
        ctx.session,
        ctx.principal,
        _id(payload, "run_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="payroll.payslips.search",
    module="payroll",
    permission="payroll.view",
    risk="read",
    describe="List the payslips in a payroll run",
    output=PayslipList,
)
async def search_payslips(ctx: ActionContext, payload: dict) -> PayslipList:
    return await runs.list_payslips(ctx.session, _id(payload, "run_id"))


@action(
    key="payroll.payslips.get",
    module="payroll",
    permission="payroll.view",
    risk="read",
    describe="Read one payslip with its line breakdown",
    output=PayslipOut,
)
async def get_payslip(ctx: ActionContext, payload: dict) -> PayslipOut:
    return await runs.get_payslip(ctx.session, _id(payload, "payslip_id"))


@action(
    key="payroll.payslips.by_staff",
    module="payroll",
    permission="payroll.view",
    risk="read",
    describe="Read one staff member's payslip in a run",
    output=PayslipOut,
)
async def payslip_by_staff(ctx: ActionContext, payload: dict) -> PayslipOut:
    return await runs.payslip_for_staff(
        ctx.session,
        _id(payload, "run_id"),
        _id(payload, "staff_id"),
    )


__all__ = [
    "activate_rule_set",
    "archive_rule_set",
    "calculate_run",
    "create_component",
    "create_rule",
    "create_rule_set",
    "create_run",
    "create_staff_component",
    "delete_component",
    "delete_rule",
    "delete_rule_set",
    "delete_run",
    "delete_staff_component",
    "finalize_run",
    "get_component",
    "get_payslip",
    "get_rule_set",
    "get_run",
    "payslip_by_staff",
    "restore_component",
    "restore_rule",
    "restore_rule_set",
    "restore_staff_component",
    "search_components",
    "search_payslips",
    "search_rule_sets",
    "search_runs",
    "search_staff_components",
    "update_component",
    "update_rule",
    "update_rule_set",
    "update_staff_component",
]
