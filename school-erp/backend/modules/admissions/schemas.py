"""Schemas for admission applications, decisions and conversion."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from core.people.schemas import PersonInput
from pydantic import BaseModel, ConfigDict, Field, model_validator

from modules.students.schemas import PersonOut

AdmissionStatus = Literal[
    "applied",
    "reviewed",
    "test",
    "offered",
    "accepted",
    "enrolled",
    "rejected",
    "withdrawn",
]

DecisionStatus = Literal[
    "reviewed",
    "test",
    "offered",
    "accepted",
    "rejected",
    "withdrawn",
]

ApplicationSource = Literal["office", "phone", "walk_in", "public"]


class AdmissionGuardianInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: uuid.UUID | None = None
    person: PersonInput | None = None
    relationship: str = Field(default="guardian", min_length=1, max_length=40)
    is_primary: bool = False
    can_pickup: bool = True
    wants_account: bool = False
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _one_person_source(self) -> AdmissionGuardianInput:
        if (self.person_id is None) == (self.person is None):
            raise ValueError("Provide either person_id or person, not both")
        return self


class AdmissionGuardianOut(BaseModel):
    id: str
    application_id: str
    person_id: str
    relationship: str
    is_primary: bool
    can_pickup: bool
    wants_account: bool
    account_user_id: str | None = None
    notes: str | None = None
    person: PersonOut
    row_version: int


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: uuid.UUID | None = None
    person: PersonInput | None = None
    year_id: uuid.UUID | None = None
    level_id: uuid.UUID
    section_id: uuid.UUID | None = None
    entrance_test_score: int | None = Field(default=None, ge=0, le=1000)
    applied_on: date | None = None
    source: ApplicationSource = "office"
    notes: str | None = Field(default=None, max_length=4000)
    custom: dict[str, Any] | None = None
    guardians: list[AdmissionGuardianInput] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _one_person_source(self) -> ApplicationCreate:
        if (self.person_id is None) == (self.person is None):
            raise ValueError("Provide either person_id or person, not both")
        return self


class ApplicationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person: PersonInput | None = None
    year_id: uuid.UUID | None = None
    level_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    entrance_test_score: int | None = Field(default=None, ge=0, le=1000)
    applied_on: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    custom: dict[str, Any] | None = None
    row_version: int = Field(ge=1)


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DecisionStatus
    notes: str | None = Field(default=None, max_length=4000)
    entrance_test_score: int | None = Field(default=None, ge=0, le=1000)
    row_version: int = Field(ge=1)


class ConversionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_version: int = Field(ge=1)
    admission_date: date | None = None
    roll_number: str | None = Field(default=None, max_length=30)
    create_guardian_accounts: bool | None = None


class ApplicationSummary(BaseModel):
    id: str
    application_number: str
    status: AdmissionStatus
    applied_on: date | None = None
    source: str
    person: PersonOut
    year_id: str
    year_code: str | None = None
    year_name: str | None = None
    level_id: str
    level_code: str | None = None
    level_name: str | None = None
    section_id: str | None = None
    section_code: str | None = None
    entrance_test_score: int | None = None
    student_id: str | None = None
    student_number: str | None = None
    row_version: int


class ApplicationOut(ApplicationSummary):
    notes: str | None = None
    custom: dict[str, Any] = Field(default_factory=dict)
    guardians: list[AdmissionGuardianOut] = Field(default_factory=list)
    decision_notes: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    converted_at: datetime | None = None
    test_max_score: int = 0
    test_pass_score: int | None = None
    test_passed: bool | None = None


class ApplicationList(BaseModel):
    items: list[ApplicationSummary] = Field(default_factory=list)
    next_cursor: str | None = None
    total: int | None = None


class ApplicationCreateOut(ApplicationOut):
    duplicate_warnings: list[dict[str, Any]] = Field(default_factory=list)


class ApplicationQuery(BaseModel):
    q: str | None = Field(default=None, max_length=120)
    status: AdmissionStatus | None = None
    year_id: uuid.UUID | None = None
    level_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    limit: int = Field(default=25, ge=1, le=200)
    cursor: str | None = Field(default=None, max_length=1000)
    sort: str | None = Field(default=None, max_length=60)
    order: Literal["asc", "desc"] = "desc"


class AdmissionFormOut(BaseModel):
    entity_type: str = "admission_application"
    fields: list[dict[str, Any]] = Field(default_factory=list)
    entrance_test_enabled: bool = True
    entrance_test_max_score: int = 100
    entrance_test_pass_score: int | None = None
    require_guardian: bool = True
    public_form_enabled: bool = False


class ApplicationPreview(BaseModel):
    will_create: str = "admission_application"
    application_number: str
    full_name: str
    year_code: str | None = None
    level_code: str | None = None
    section_code: str | None = None
    guardian_count: int = 0
    custom_field_count: int = 0
    duplicate_warnings: list[dict[str, Any]] = Field(default_factory=list)


class GuardianAccountPlan(BaseModel):
    person_id: str
    name: str
    email: str | None = None
    action: Literal["create", "existing_user", "no_email", "role_missing"]


class ConversionPreview(BaseModel):
    can_convert: bool
    reason: str | None = None
    student_number: str | None = None
    student_number_generated: bool = True
    year_code: str | None = None
    level_code: str | None = None
    section_code: str | None = None
    section_source: Literal["application", "auto", "none"] = "none"
    guardian_count: int = 0
    accounts: list[GuardianAccountPlan] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ConversionOut(BaseModel):
    application: ApplicationOut
    student_id: str
    student_number: str
    enrollment_id: str
    guardian_ids: list[str] = Field(default_factory=list)
    accounts: list[GuardianAccountPlan] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DecisionOut(BaseModel):
    application: ApplicationOut
    previous_status: AdmissionStatus
    status: AdmissionStatus


__all__ = [
    "AdmissionFormOut",
    "AdmissionGuardianInput",
    "AdmissionGuardianOut",
    "AdmissionStatus",
    "ApplicationCreate",
    "ApplicationCreateOut",
    "ApplicationList",
    "ApplicationOut",
    "ApplicationPreview",
    "ApplicationQuery",
    "ApplicationSource",
    "ApplicationSummary",
    "ApplicationUpdate",
    "ConversionInput",
    "ConversionOut",
    "ConversionPreview",
    "DecisionInput",
    "DecisionOut",
    "DecisionStatus",
    "GuardianAccountPlan",
]
