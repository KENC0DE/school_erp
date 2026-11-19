"""Schemas for staff profiles, departments, positions, contracts and qualifications."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from core.people.schemas import PersonInput
from pydantic import BaseModel, ConfigDict, Field, model_validator

StaffStatus = Literal["active", "on_leave", "suspended", "terminated"]
ContractType = Literal["permanent", "fixed_term", "part_time", "temporary", "internship"]
ContractStatus = Literal["draft", "active", "ended"]
QualificationKind = Literal["education", "training", "certification", "experience"]

STAFF_STATUSES: tuple[str, ...] = ("active", "on_leave", "suspended", "terminated")
CONTRACT_TYPES: tuple[str, ...] = ("permanent", "fixed_term", "part_time", "temporary", "internship")
CONTRACT_STATUSES: tuple[str, ...] = ("draft", "active", "ended")
QUALIFICATION_KINDS: tuple[str, ...] = ("education", "training", "certification", "experience")


class PersonOut(BaseModel):
    id: str
    given_name_en: str | None = None
    father_name_en: str | None = None
    grandfather_name_en: str | None = None
    given_name_am: str | None = None
    father_name_am: str | None = None
    grandfather_name_am: str | None = None
    mother_name_en: str | None = None
    mother_name_am: str | None = None
    baptismal_name: str | None = None
    nickname: str | None = None
    sex: str | None = None
    date_of_birth: date | None = None
    place_of_birth: str | None = None
    nationality: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    photo_file_id: str | None = None
    custom: dict[str, Any] = Field(default_factory=dict)
    full_name: str
    short_name: str
    row_version: int


class DepartmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9/_-]*$")
    name: str = Field(min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    parent_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10_000)


class DepartmentUpdate(BaseModel):
    code: str | None = Field(
        default=None, min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9/_-]*$"
    )
    name: str | None = Field(default=None, min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    parent_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    row_version: int = Field(ge=1)


class DepartmentOut(BaseModel):
    id: str
    code: str
    name: str
    name_am: str | None = None
    parent_id: str | None = None
    description: str | None = None
    is_active: bool
    sort_order: int
    row_version: int


class DepartmentList(BaseModel):
    items: list[DepartmentOut]
    total: int


class PositionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9/_-]*$")
    name: str = Field(min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    department_id: uuid.UUID | None = None
    is_teaching: bool = False
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10_000)


class PositionUpdate(BaseModel):
    code: str | None = Field(
        default=None, min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9/_-]*$"
    )
    name: str | None = Field(default=None, min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    department_id: uuid.UUID | None = None
    is_teaching: bool | None = None
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    row_version: int = Field(ge=1)


class PositionOut(BaseModel):
    id: str
    code: str
    name: str
    name_am: str | None = None
    department_id: str | None = None
    department_code: str | None = None
    department_name: str | None = None
    is_teaching: bool
    description: str | None = None
    is_active: bool
    sort_order: int
    row_version: int


class PositionList(BaseModel):
    items: list[PositionOut]
    total: int


class StaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Either register a new person, or hire somebody the school already knows
    # (for example a guardian who becomes a teacher).
    person: PersonInput | None = None
    person_id: uuid.UUID | None = None
    staff_number: str | None = Field(default=None, min_length=1, max_length=40)
    status: StaffStatus = "active"
    department_id: uuid.UUID | None = None
    position_id: uuid.UUID | None = None
    hire_date: date | None = None
    end_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    custom: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _one_person_source(self) -> StaffCreate:
        if (self.person is None) == (self.person_id is None):
            raise ValueError("Provide either a person or an existing person id")
        return self

    @model_validator(mode="after")
    def _dates_in_order(self) -> StaffCreate:
        if self.hire_date and self.end_date and self.end_date < self.hire_date:
            raise ValueError("The end date cannot be before the hire date")
        return self


class StaffUpdate(BaseModel):
    person: PersonInput | None = None
    staff_number: str | None = Field(default=None, min_length=1, max_length=40)
    status: StaffStatus | None = None
    department_id: uuid.UUID | None = None
    position_id: uuid.UUID | None = None
    hire_date: date | None = None
    end_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    custom: dict[str, Any] | None = None
    row_version: int = Field(ge=1)


class AccountLink(BaseModel):
    user_id: uuid.UUID


class StaffQuery(BaseModel):
    q: str | None = Field(default=None, max_length=120)
    status: StaffStatus | None = None
    department_id: uuid.UUID | None = None
    position_id: uuid.UUID | None = None
    linked: bool | None = None
    limit: int = Field(default=25, ge=1, le=200)
    cursor: str | None = Field(default=None, max_length=1000)
    sort: str | None = Field(default=None, max_length=60)
    order: Literal["asc", "desc"] = "desc"


class ContractInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ContractType = "permanent"
    status: ContractStatus = "active"
    start_date: date
    end_date: date | None = None
    salary_santim: int | None = Field(default=None, ge=0, le=10_000_000_000)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _dates_in_order(self) -> ContractInput:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("The contract end date cannot be before its start date")
        return self


class ContractUpdate(BaseModel):
    type: ContractType | None = None
    status: ContractStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    salary_santim: int | None = Field(default=None, ge=0, le=10_000_000_000)
    notes: str | None = Field(default=None, max_length=4000)
    row_version: int = Field(ge=1)


class ContractOut(BaseModel):
    id: str
    staff_id: str
    type: ContractType
    status: ContractStatus
    start_date: date
    end_date: date | None = None
    salary_santim: int | None = None
    notes: str | None = None
    row_version: int


class ContractList(BaseModel):
    items: list[ContractOut]
    total: int


class QualificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: QualificationKind = "education"
    title: str = Field(min_length=1, max_length=200)
    institution: str | None = Field(default=None, max_length=200)
    field_of_study: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    result: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _dates_in_order(self) -> QualificationInput:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("The qualification end date cannot be before its start date")
        return self


class QualificationUpdate(BaseModel):
    kind: QualificationKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    institution: str | None = Field(default=None, max_length=200)
    field_of_study: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    result: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=4000)
    row_version: int = Field(ge=1)


class QualificationOut(BaseModel):
    id: str
    staff_id: str
    kind: QualificationKind
    title: str
    institution: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    result: str | None = None
    notes: str | None = None
    row_version: int


class QualificationList(BaseModel):
    items: list[QualificationOut]
    total: int


class TeachingAssignmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year_id: uuid.UUID
    section_id: uuid.UUID
    subject_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=2000)


class TeachingAssignmentUpdate(BaseModel):
    year_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    row_version: int = Field(ge=1)


class TeachingAssignmentOut(BaseModel):
    id: str
    staff_id: str
    staff_number: str
    year_id: str
    year_code: str
    section_id: str
    section_code: str
    section_name: str | None = None
    level_id: str
    level_code: str
    level_name: str
    subject_id: str
    subject_code: str
    subject_name: str
    notes: str | None = None
    row_version: int


class TeachingAssignmentList(BaseModel):
    items: list[TeachingAssignmentOut]
    total: int


class StaffSummary(BaseModel):
    id: str
    staff_number: str
    status: StaffStatus
    person: PersonOut
    user_id: str | None = None
    department: DepartmentOut | None = None
    position: PositionOut | None = None
    hire_date: date | None = None
    end_date: date | None = None
    row_version: int


class StaffList(BaseModel):
    items: list[StaffSummary]
    next_cursor: str | None = None
    total: int


class StaffOut(StaffSummary):
    notes: str | None = None
    custom: dict[str, Any] = Field(default_factory=dict)
    contracts: list[ContractOut] = Field(default_factory=list)
    contracts_restricted: bool = False
    qualifications: list[QualificationOut] = Field(default_factory=list)


__all__ = [
    "AccountLink",
    "CONTRACT_STATUSES",
    "CONTRACT_TYPES",
    "ContractInput",
    "ContractList",
    "ContractOut",
    "ContractStatus",
    "ContractType",
    "ContractUpdate",
    "DepartmentInput",
    "DepartmentList",
    "DepartmentOut",
    "DepartmentUpdate",
    "PersonOut",
    "PositionInput",
    "PositionList",
    "PositionOut",
    "PositionUpdate",
    "QUALIFICATION_KINDS",
    "QualificationInput",
    "QualificationKind",
    "QualificationList",
    "QualificationOut",
    "QualificationUpdate",
    "STAFF_STATUSES",
    "StaffCreate",
    "StaffList",
    "StaffOut",
    "StaffQuery",
    "StaffStatus",
    "StaffSummary",
    "StaffUpdate",
    "TeachingAssignmentInput",
    "TeachingAssignmentList",
    "TeachingAssignmentOut",
    "TeachingAssignmentUpdate",
]
