"""Schemas for the optional payroll sub-module."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from modules.payroll.engine import (
    Basis,
    Bracket,
    Payer,
    PayrollError,
    Rule,
    RuleKind,
    RuleMethod,
    validate_brackets,
    validate_rule,
)

ComponentKind = Literal["earning", "deduction"]
RuleSetStatus = Literal["draft", "active", "archived"]
RunStatus = Literal["draft", "calculated", "finalized"]

COMPONENT_KINDS: tuple[str, ...] = ("earning", "deduction")
RULE_SET_STATUSES: tuple[str, ...] = ("draft", "active", "archived")
RUN_STATUSES: tuple[str, ...] = ("draft", "calculated", "finalized")


class ComponentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9/_-]*$")
    name: str = Field(min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    kind: ComponentKind = "earning"
    is_taxable: bool = True
    is_pensionable: bool = True
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10_000)
    notes: str | None = Field(default=None, max_length=2000)


class ComponentUpdate(BaseModel):
    code: str | None = Field(
        default=None, min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9/_-]*$"
    )
    name: str | None = Field(default=None, min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    kind: ComponentKind | None = None
    is_taxable: bool | None = None
    is_pensionable: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    notes: str | None = Field(default=None, max_length=2000)
    row_version: int = Field(ge=1)


class ComponentOut(BaseModel):
    id: str
    code: str
    name: str
    name_am: str | None = None
    kind: str
    is_taxable: bool
    is_pensionable: bool
    is_active: bool
    sort_order: int
    notes: str | None = None
    row_version: int


class ComponentList(BaseModel):
    items: list[ComponentOut]
    total: int


class StaffComponentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: uuid.UUID
    amount_santim: int | None = Field(default=None, ge=0)
    rate_basis_points: int | None = Field(default=None, ge=0, le=10_000)
    starts_on: date
    ends_on: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _one_amount_form(self) -> StaffComponentInput:
        if (self.amount_santim is None) == (self.rate_basis_points is None):
            raise ValueError("Set exactly one of amount_santim or rate_basis_points")
        if self.ends_on is not None and self.ends_on < self.starts_on:
            raise ValueError("ends_on cannot be before starts_on")
        return self


class StaffComponentUpdate(BaseModel):
    amount_santim: int | None = Field(default=None, ge=0)
    rate_basis_points: int | None = Field(default=None, ge=0, le=10_000)
    starts_on: date | None = None
    ends_on: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    row_version: int = Field(ge=1)


class StaffComponentOut(BaseModel):
    id: str
    staff_id: str
    component_id: str
    component_code: str
    component_name: str
    kind: str
    amount_santim: int | None = None
    rate_basis_points: int | None = None
    starts_on: date
    ends_on: date | None = None
    notes: str | None = None
    row_version: int


class StaffComponentList(BaseModel):
    items: list[StaffComponentOut]
    total: int


class BracketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lower_santim: int = Field(ge=0)
    upper_santim: int | None = Field(default=None, ge=0)
    rate_basis_points: int = Field(ge=0, le=10_000)


class BracketOut(BaseModel):
    lower_santim: int
    upper_santim: int | None = None
    rate_basis_points: int


class RuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9/_-]*$")
    name: str = Field(min_length=1, max_length=120)
    kind: RuleKind = RuleKind.OTHER
    payer: Payer = Payer.EMPLOYEE
    method: RuleMethod = RuleMethod.PERCENT
    base: Basis = Basis.GROSS
    rate_basis_points: int | None = Field(default=None, ge=0, le=10_000)
    brackets: list[BracketInput] = Field(default_factory=list)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10_000)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _valid_rule(self) -> RuleInput:
        _validate_rule_payload(
            key=self.key,
            name=self.name,
            method=self.method,
            rate_basis_points=self.rate_basis_points,
            brackets=[item.model_dump() for item in self.brackets],
        )
        return self


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    kind: RuleKind | None = None
    payer: Payer | None = None
    method: RuleMethod | None = None
    base: Basis | None = None
    rate_basis_points: int | None = Field(default=None, ge=0, le=10_000)
    brackets: list[BracketInput] | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    notes: str | None = Field(default=None, max_length=2000)
    row_version: int = Field(ge=1)


class RuleOut(BaseModel):
    id: str
    rule_set_id: str
    key: str
    name: str
    kind: str
    payer: str
    method: str
    base: str
    rate_basis_points: int | None = None
    brackets: list[BracketOut] = Field(default_factory=list)
    is_active: bool
    sort_order: int
    notes: str | None = None
    row_version: int


class RuleSetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9/_-]*$")
    name: str = Field(min_length=1, max_length=120)
    effective_from: date
    effective_to: date | None = None
    verified_by_accountant: bool = False
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _dates_ordered(self) -> RuleSetInput:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        return self


class RuleSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    effective_from: date | None = None
    effective_to: date | None = None
    verified_by_accountant: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)
    row_version: int = Field(ge=1)


class RuleSetOut(BaseModel):
    id: str
    code: str
    name: str
    effective_from: date
    effective_to: date | None = None
    status: str
    verified_by_accountant: bool
    accountant_notice: str
    notes: str | None = None
    rules: list[RuleOut] = Field(default_factory=list)
    row_version: int


class RuleSetList(BaseModel):
    items: list[RuleSetOut]
    total: int


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_year: int = Field(ge=2000, le=2200)
    period_month: int = Field(ge=1, le=12)
    rule_set_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class RunOut(BaseModel):
    id: str
    period_year: int
    period_month: int
    rule_set_id: str
    rule_set_code: str
    status: str
    payslip_count: int
    skipped_count: int
    gross_santim: int
    deductions_santim: int
    net_santim: int
    employer_santim: int
    calculated_at: datetime | None = None
    finalized_at: datetime | None = None
    notes: str | None = None
    row_version: int


class RunList(BaseModel):
    items: list[RunOut]
    total: int


class PayslipLineOut(BaseModel):
    id: str
    kind: str
    code: str
    name: str
    source: str
    rule_key: str | None = None
    amount_santim: int
    base_santim: int | None = None
    rate_basis_points: int | None = None
    sort_order: int


class PayslipOut(BaseModel):
    id: str
    run_id: str
    staff_id: str
    staff_number: str
    staff_name: str
    contract_id: str | None = None
    base_salary_santim: int
    gross_santim: int
    taxable_santim: int
    pensionable_santim: int
    total_deductions_santim: int
    net_santim: int
    employer_contributions_santim: int
    notes: str | None = None
    lines: list[PayslipLineOut] = Field(default_factory=list)
    row_version: int


class PayslipList(BaseModel):
    items: list[PayslipOut]
    total: int


class RunQuery(BaseModel):
    period_year: int | None = None
    period_month: int | None = None
    status: RunStatus | None = None


def _validate_rule_payload(
    *,
    key: str,
    name: str,
    method: RuleMethod,
    rate_basis_points: int | None,
    brackets: list[dict],
) -> None:
    try:
        rule = Rule(
            key=key,
            name=name,
            kind=RuleKind.OTHER,
            payer=Payer.EMPLOYEE,
            method=method,
            base=Basis.GROSS,
            rate_basis_points=rate_basis_points,
            brackets=tuple(
                Bracket(
                    lower_santim=item["lower_santim"],
                    upper_santim=item["upper_santim"],
                    rate_basis_points=item["rate_basis_points"],
                )
                for item in brackets
            ),
        )
        validate_rule(rule)
    except PayrollError as exc:
        raise ValueError(str(exc)) from exc


def bracket_rows(brackets: list[BracketInput]) -> list[Bracket]:
    return [
        Bracket(
            lower_santim=item.lower_santim,
            upper_santim=item.upper_santim,
            rate_basis_points=item.rate_basis_points,
        )
        for item in brackets
    ]


def validate_bracket_inputs(brackets: list[BracketInput]) -> None:
    try:
        validate_brackets(bracket_rows(brackets))
    except PayrollError as exc:
        raise ValueError(str(exc)) from exc


__all__ = [
    "COMPONENT_KINDS",
    "BracketInput",
    "BracketOut",
    "ComponentInput",
    "ComponentList",
    "ComponentOut",
    "ComponentUpdate",
    "PayslipLineOut",
    "PayslipList",
    "PayslipOut",
    "RUN_STATUSES",
    "RULE_SET_STATUSES",
    "RuleInput",
    "RuleOut",
    "RuleSetInput",
    "RuleSetList",
    "RuleSetOut",
    "RuleSetUpdate",
    "RuleUpdate",
    "RunInput",
    "RunList",
    "RunOut",
    "RunQuery",
    "StaffComponentInput",
    "StaffComponentList",
    "StaffComponentOut",
    "StaffComponentUpdate",
    "bracket_rows",
    "validate_bracket_inputs",
]
