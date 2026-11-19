"""HTTP routes for the optional payroll sub-module."""

from __future__ import annotations

import uuid

from app.logging import request_id_var
from core.actions.registry import ActionContext
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payroll.actions import (
    activate_rule_set,
    archive_rule_set,
    calculate_run,
    create_component,
    create_rule,
    create_rule_set,
    create_run,
    create_staff_component,
    delete_component,
    delete_rule,
    delete_rule_set,
    delete_run,
    delete_staff_component,
    finalize_run,
    get_component,
    get_payslip,
    get_rule_set,
    get_run,
    payslip_by_staff,
    restore_component,
    restore_rule,
    restore_rule_set,
    restore_staff_component,
    search_components,
    search_payslips,
    search_rule_sets,
    search_runs,
    search_staff_components,
    update_component,
    update_rule,
    update_rule_set,
    update_staff_component,
)
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
    RunStatus,
    StaffComponentInput,
    StaffComponentList,
    StaffComponentOut,
    StaffComponentUpdate,
)

router = APIRouter(tags=["payroll"])


def _context(principal: Principal, session: AsyncSession) -> ActionContext:
    return ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )


def _with(payload: dict, **values) -> dict:
    return {**payload, **values}


# ------------------------------------------------------------------ components


@router.get("/components", response_model=ComponentList)
async def list_components_route(
    include_inactive: bool = Query(False),
    principal: Principal = Depends(require("payroll.view")),
    session: AsyncSession = Depends(get_session),
) -> ComponentList:
    return await search_components(_context(principal, session), {"include_inactive": include_inactive})


@router.post("/components", response_model=ComponentOut, status_code=201)
async def create_component_route(
    payload: ComponentInput,
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> ComponentOut:
    return await create_component(_context(principal, session), payload.model_dump())


@router.get("/components/{component_id}", response_model=ComponentOut)
async def get_component_route(
    component_id: uuid.UUID,
    principal: Principal = Depends(require("payroll.view")),
    session: AsyncSession = Depends(get_session),
) -> ComponentOut:
    return await get_component(_context(principal, session), {"component_id": str(component_id)})


@router.patch("/components/{component_id}", response_model=ComponentOut)
async def update_component_route(
    component_id: uuid.UUID,
    payload: ComponentUpdate,
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> ComponentOut:
    return await update_component(
        _context(principal, session),
        _with(payload.model_dump(exclude_unset=True), component_id=str(component_id)),
    )


@router.delete("/components/{component_id}")
async def delete_component_route(
    component_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await delete_component(
        _context(principal, session),
        {"component_id": str(component_id), "reason": reason},
    )


@router.post("/components/{component_id}/restore", response_model=ComponentOut)
async def restore_component_route(
    component_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> ComponentOut:
    return await restore_component(
        _context(principal, session),
        {"component_id": str(component_id), "reason": reason},
    )


# ---------------------------------------------------------- staff assignments


@router.get("/staff/{staff_id}/components", response_model=StaffComponentList)
async def list_staff_components_route(
    staff_id: uuid.UUID,
    principal: Principal = Depends(require("payroll.view")),
    session: AsyncSession = Depends(get_session),
) -> StaffComponentList:
    return await search_staff_components(_context(principal, session), {"staff_id": str(staff_id)})


@router.post("/staff/{staff_id}/components", response_model=StaffComponentOut, status_code=201)
async def create_staff_component_route(
    staff_id: uuid.UUID,
    payload: StaffComponentInput,
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> StaffComponentOut:
    return await create_staff_component(
        _context(principal, session),
        _with(payload.model_dump(), staff_id=str(staff_id)),
    )


@router.patch(
    "/staff/{staff_id}/components/{assignment_id}",
    response_model=StaffComponentOut,
)
async def update_staff_component_route(
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: StaffComponentUpdate,
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> StaffComponentOut:
    return await update_staff_component(
        _context(principal, session),
        _with(
            payload.model_dump(exclude_unset=True),
            staff_id=str(staff_id),
            assignment_id=str(assignment_id),
        ),
    )


@router.delete("/staff/{staff_id}/components/{assignment_id}")
async def delete_staff_component_route(
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await delete_staff_component(
        _context(principal, session),
        {
            "staff_id": str(staff_id),
            "assignment_id": str(assignment_id),
            "reason": reason,
        },
    )


@router.post(
    "/staff/{staff_id}/components/{assignment_id}/restore",
    response_model=StaffComponentOut,
)
async def restore_staff_component_route(
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> StaffComponentOut:
    return await restore_staff_component(
        _context(principal, session),
        {
            "staff_id": str(staff_id),
            "assignment_id": str(assignment_id),
            "reason": reason,
        },
    )


# ------------------------------------------------------------------ rule sets


@router.get("/rule-sets", response_model=RuleSetList)
async def list_rule_sets_route(
    include_archived: bool = Query(False),
    principal: Principal = Depends(require("payroll.view")),
    session: AsyncSession = Depends(get_session),
) -> RuleSetList:
    return await search_rule_sets(_context(principal, session), {"include_archived": include_archived})


@router.post("/rule-sets", response_model=RuleSetOut, status_code=201)
async def create_rule_set_route(
    payload: RuleSetInput,
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> RuleSetOut:
    return await create_rule_set(_context(principal, session), payload.model_dump())


@router.get("/rule-sets/{rule_set_id}", response_model=RuleSetOut)
async def get_rule_set_route(
    rule_set_id: uuid.UUID,
    principal: Principal = Depends(require("payroll.view")),
    session: AsyncSession = Depends(get_session),
) -> RuleSetOut:
    return await get_rule_set(_context(principal, session), {"rule_set_id": str(rule_set_id)})


@router.patch("/rule-sets/{rule_set_id}", response_model=RuleSetOut)
async def update_rule_set_route(
    rule_set_id: uuid.UUID,
    payload: RuleSetUpdate,
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> RuleSetOut:
    return await update_rule_set(
        _context(principal, session),
        _with(payload.model_dump(exclude_unset=True), rule_set_id=str(rule_set_id)),
    )


@router.post("/rule-sets/{rule_set_id}/activate", response_model=RuleSetOut)
async def activate_rule_set_route(
    rule_set_id: uuid.UUID,
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> RuleSetOut:
    return await activate_rule_set(_context(principal, session), {"rule_set_id": str(rule_set_id)})


@router.post("/rule-sets/{rule_set_id}/archive", response_model=RuleSetOut)
async def archive_rule_set_route(
    rule_set_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> RuleSetOut:
    return await archive_rule_set(
        _context(principal, session),
        {"rule_set_id": str(rule_set_id), "reason": reason},
    )


@router.delete("/rule-sets/{rule_set_id}")
async def delete_rule_set_route(
    rule_set_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await delete_rule_set(
        _context(principal, session),
        {"rule_set_id": str(rule_set_id), "reason": reason},
    )


@router.post("/rule-sets/{rule_set_id}/restore", response_model=RuleSetOut)
async def restore_rule_set_route(
    rule_set_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> RuleSetOut:
    return await restore_rule_set(
        _context(principal, session),
        {"rule_set_id": str(rule_set_id), "reason": reason},
    )


# ---------------------------------------------------------------------- rules


@router.post("/rule-sets/{rule_set_id}/rules", response_model=RuleOut, status_code=201)
async def create_rule_route(
    rule_set_id: uuid.UUID,
    payload: RuleInput,
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> RuleOut:
    return await create_rule(
        _context(principal, session),
        _with(payload.model_dump(), rule_set_id=str(rule_set_id)),
    )


@router.patch("/rule-sets/{rule_set_id}/rules/{rule_id}", response_model=RuleOut)
async def update_rule_route(
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    payload: RuleUpdate,
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> RuleOut:
    return await update_rule(
        _context(principal, session),
        _with(
            payload.model_dump(exclude_unset=True),
            rule_set_id=str(rule_set_id),
            rule_id=str(rule_id),
        ),
    )


@router.delete("/rule-sets/{rule_set_id}/rules/{rule_id}")
async def delete_rule_route(
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await delete_rule(
        _context(principal, session),
        {
            "rule_set_id": str(rule_set_id),
            "rule_id": str(rule_id),
            "reason": reason,
        },
    )


@router.post("/rule-sets/{rule_set_id}/rules/{rule_id}/restore", response_model=RuleOut)
async def restore_rule_route(
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("payroll.manage")),
    session: AsyncSession = Depends(get_session),
) -> RuleOut:
    return await restore_rule(
        _context(principal, session),
        {
            "rule_set_id": str(rule_set_id),
            "rule_id": str(rule_id),
            "reason": reason,
        },
    )


# ----------------------------------------------------------------------- runs


@router.get("/runs", response_model=RunList)
async def list_runs_route(
    period_year: int | None = Query(None, ge=2000, le=2200),
    period_month: int | None = Query(None, ge=1, le=12),
    status: RunStatus | None = Query(None),
    principal: Principal = Depends(require("payroll.view")),
    session: AsyncSession = Depends(get_session),
) -> RunList:
    return await search_runs(
        _context(principal, session),
        {
            "period_year": period_year,
            "period_month": period_month,
            "status": status,
        },
    )


@router.post("/runs", response_model=RunOut, status_code=201)
async def create_run_route(
    payload: RunInput,
    principal: Principal = Depends(require("payroll.run")),
    session: AsyncSession = Depends(get_session),
) -> RunOut:
    return await create_run(
        _context(principal, session),
        payload.model_dump(mode="json"),
    )


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run_route(
    run_id: uuid.UUID,
    principal: Principal = Depends(require("payroll.view")),
    session: AsyncSession = Depends(get_session),
) -> RunOut:
    return await get_run(_context(principal, session), {"run_id": str(run_id)})


@router.post("/runs/{run_id}/calculate", response_model=RunOut)
async def calculate_run_route(
    run_id: uuid.UUID,
    principal: Principal = Depends(require("payroll.run")),
    session: AsyncSession = Depends(get_session),
) -> RunOut:
    return await calculate_run(_context(principal, session), {"run_id": str(run_id)})


@router.post("/runs/{run_id}/finalize", response_model=RunOut)
async def finalize_run_route(
    run_id: uuid.UUID,
    principal: Principal = Depends(require("payroll.run")),
    session: AsyncSession = Depends(get_session),
) -> RunOut:
    return await finalize_run(_context(principal, session), {"run_id": str(run_id)})


@router.delete("/runs/{run_id}")
async def delete_run_route(
    run_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("payroll.run")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await delete_run(_context(principal, session), {"run_id": str(run_id), "reason": reason})


@router.get("/runs/{run_id}/payslips", response_model=PayslipList)
async def list_payslips_route(
    run_id: uuid.UUID,
    principal: Principal = Depends(require("payroll.view")),
    session: AsyncSession = Depends(get_session),
) -> PayslipList:
    return await search_payslips(_context(principal, session), {"run_id": str(run_id)})


@router.get("/runs/{run_id}/payslips/{payslip_id}", response_model=PayslipOut)
async def get_payslip_route(
    run_id: uuid.UUID,
    payslip_id: uuid.UUID,
    principal: Principal = Depends(require("payroll.view")),
    session: AsyncSession = Depends(get_session),
) -> PayslipOut:
    return await get_payslip(_context(principal, session), {"payslip_id": str(payslip_id)})


@router.get("/runs/{run_id}/staff/{staff_id}/payslip", response_model=PayslipOut)
async def payslip_by_staff_route(
    run_id: uuid.UUID,
    staff_id: uuid.UUID,
    principal: Principal = Depends(require("payroll.view")),
    session: AsyncSession = Depends(get_session),
) -> PayslipOut:
    return await payslip_by_staff(
        _context(principal, session),
        {"run_id": str(run_id), "staff_id": str(staff_id)},
    )


__all__ = ["router"]
