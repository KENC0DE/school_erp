"""Schemas for leave types, balances, requests and the calendar view."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LeaveStatus = Literal["draft", "submitted", "approved", "rejected", "cancelled"]

LEAVE_STATUSES: tuple[str, ...] = (
    "draft",
    "submitted",
    "approved",
    "rejected",
    "cancelled",
)


def _assert_half_day_steps(value: float) -> float:
    doubled = value * 2
    if abs(doubled - round(doubled)) > 1e-9:
        raise ValueError("Leave days must be a whole or half day")
    return value


class LeaveTypeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    is_paid: bool = True
    annual_entitlement_days: float = Field(default=0, ge=0, le=365)
    counts_against_balance: bool = True
    requires_approval: bool = True
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10_000)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _half_days(self) -> LeaveTypeInput:
        _assert_half_day_steps(self.annual_entitlement_days)
        return self


class LeaveTypeUpdate(BaseModel):
    code: str | None = Field(
        default=None, min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
    )
    name: str | None = Field(default=None, min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    is_paid: bool | None = None
    annual_entitlement_days: float | None = Field(default=None, ge=0, le=365)
    counts_against_balance: bool | None = None
    requires_approval: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    notes: str | None = Field(default=None, max_length=2000)
    row_version: int = Field(ge=1)

    @model_validator(mode="after")
    def _half_days(self) -> LeaveTypeUpdate:
        if self.annual_entitlement_days is not None:
            _assert_half_day_steps(self.annual_entitlement_days)
        return self


class LeaveTypeOut(BaseModel):
    id: str
    code: str
    name: str
    name_am: str | None = None
    is_paid: bool
    annual_entitlement_days: float
    counts_against_balance: bool
    requires_approval: bool
    is_active: bool
    sort_order: int
    notes: str | None = None
    row_version: int


class LeaveTypeList(BaseModel):
    items: list[LeaveTypeOut]
    total: int


class LeaveBalanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_id: uuid.UUID
    year_id: uuid.UUID
    leave_type_id: uuid.UUID
    entitled_days: float = Field(ge=0, le=365)
    carried_days: float = Field(default=0, ge=0, le=365)
    adjustment_days: float = Field(default=0, ge=-365, le=365)
    notes: str | None = Field(default=None, max_length=2000)
    row_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _half_days(self) -> LeaveBalanceInput:
        _assert_half_day_steps(self.entitled_days)
        _assert_half_day_steps(self.carried_days)
        _assert_half_day_steps(self.adjustment_days)
        return self


class LeaveBalanceOut(BaseModel):
    id: str
    staff_id: str
    staff_number: str
    staff_name: str
    year_id: str
    year_code: str
    leave_type_id: str
    leave_type_code: str
    leave_type_name: str
    entitled_days: float
    carried_days: float
    adjustment_days: float
    used_days: float
    pending_days: float
    remaining_days: float
    notes: str | None = None
    row_version: int


class LeaveBalanceList(BaseModel):
    items: list[LeaveBalanceOut]
    total: int


class LeaveRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_id: uuid.UUID
    year_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    is_half_day: bool = False
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _dates(self) -> LeaveRequestInput:
        if self.end_date < self.start_date:
            raise ValueError("The end date cannot be before the start date")
        if self.is_half_day and self.start_date != self.end_date:
            raise ValueError("A half-day request must start and end on the same date")
        return self


class LeaveRequestUpdate(BaseModel):
    year_id: uuid.UUID | None = None
    leave_type_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_half_day: bool | None = None
    reason: str | None = Field(default=None, max_length=2000)
    row_version: int = Field(ge=1)


class LeaveDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=2000)


class LeaveRequestOut(BaseModel):
    id: str
    staff_id: str
    staff_number: str
    staff_name: str
    year_id: str
    year_code: str
    leave_type_id: str
    leave_type_code: str
    leave_type_name: str
    start_date: date
    end_date: date
    is_half_day: bool
    days: float
    reason: str | None = None
    status: LeaveStatus
    submitted_at: datetime | None = None
    decided_at: datetime | None = None
    decided_by: str | None = None
    decided_by_name: str | None = None
    decision_note: str | None = None
    row_version: int


class LeaveRequestList(BaseModel):
    items: list[LeaveRequestOut]
    total: int


class LeaveCalendarOut(BaseModel):
    from_date: date
    to_date: date
    items: list[LeaveRequestOut]
    total: int


__all__ = [
    "LEAVE_STATUSES",
    "LeaveBalanceInput",
    "LeaveBalanceList",
    "LeaveBalanceOut",
    "LeaveCalendarOut",
    "LeaveDecisionInput",
    "LeaveRequestInput",
    "LeaveRequestList",
    "LeaveRequestOut",
    "LeaveRequestUpdate",
    "LeaveStatus",
    "LeaveTypeInput",
    "LeaveTypeList",
    "LeaveTypeOut",
    "LeaveTypeUpdate",
]
