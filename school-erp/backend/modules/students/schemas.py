"""Schemas for student records, enrollment, guardians and medical data."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from core.people.schemas import PersonInput
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

StudentStatus = Literal[
    "applicant",
    "active",
    "promoted",
    "repeating",
    "transferred_out",
    "withdrawn",
    "graduated",
    "alumni",
]

STUDENT_STATUSES: tuple[str, ...] = (
    "applicant",
    "active",
    "promoted",
    "repeating",
    "transferred_out",
    "withdrawn",
    "graduated",
    "alumni",
)


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


class EnrollmentInput(BaseModel):
    year_id: uuid.UUID
    level_id: uuid.UUID
    section_id: uuid.UUID | None = None
    roll_number: str | None = Field(default=None, max_length=30)
    status: StudentStatus = "active"
    notes: str | None = Field(default=None, max_length=2000)


class EnrollmentUpdate(BaseModel):
    year_id: uuid.UUID | None = None
    level_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    roll_number: str | None = Field(default=None, max_length=30)
    status: StudentStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)
    row_version: int = Field(ge=1)


class EnrollmentOut(BaseModel):
    id: str
    student_id: str
    year_id: str
    year_code: str | None = None
    year_name: str | None = None
    level_id: str
    level_code: str | None = None
    level_name: str | None = None
    section_id: str | None = None
    section_code: str | None = None
    roll_number: str | None = None
    status: StudentStatus
    notes: str | None = None
    row_version: int


class GuardianInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: uuid.UUID | None = None
    person: PersonInput | None = None
    relationship: str = Field(default="guardian", min_length=1, max_length=40)
    is_primary: bool = False
    can_pickup: bool = True
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _one_person_source(self) -> GuardianInput:
        if (self.person_id is None) == (self.person is None):
            raise ValueError("Provide either person_id or person, not both")
        return self


class GuardianUpdate(BaseModel):
    relationship: str | None = Field(default=None, min_length=1, max_length=40)
    is_primary: bool | None = None
    can_pickup: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)
    row_version: int = Field(ge=1)


class GuardianOut(BaseModel):
    id: str
    student_id: str
    person_id: str
    relationship: str
    is_primary: bool
    can_pickup: bool
    notes: str | None = None
    person: PersonOut
    row_version: int


class MedicalInput(BaseModel):
    blood_type: str | None = Field(default=None, max_length=10)
    allergies: str | None = Field(default=None, max_length=4000)
    chronic_conditions: str | None = Field(default=None, max_length=4000)
    medications: str | None = Field(default=None, max_length=4000)
    emergency_contact_name: str | None = Field(default=None, max_length=160)
    emergency_contact_phone: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=4000)
    consent_to_treat: bool = False


class MedicalOut(BaseModel):
    id: str
    student_id: str
    blood_type: str | None = None
    allergies: str | None = None
    chronic_conditions: str | None = None
    medications: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    notes: str | None = None
    consent_to_treat: bool
    row_version: int


class StudentQuery(BaseModel):
    q: str | None = Field(default=None, max_length=120)
    status: StudentStatus | None = None
    year_id: uuid.UUID | None = None
    level_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    limit: int = Field(default=25, ge=1, le=200)
    cursor: str | None = Field(default=None, max_length=1000)
    sort: str | None = Field(default=None, max_length=60)
    order: Literal["asc", "desc"] = "desc"


class StudentRegister(BaseModel):
    person: PersonInput
    student_number: str | None = Field(default=None, min_length=1, max_length=40)
    status: StudentStatus | None = None
    admission_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    custom: dict[str, Any] | None = None
    enrollment: EnrollmentInput | None = None
    guardians: list[GuardianInput] = Field(default_factory=list, max_length=10)
    medical: MedicalInput | None = None

    @field_validator("student_number")
    @classmethod
    def _blank_means_generated(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class StudentUpdate(BaseModel):
    person: PersonInput | None = None
    student_number: str | None = Field(default=None, min_length=1, max_length=40)
    status: StudentStatus | None = None
    admission_date: date | None = None
    exit_date: date | None = None
    exit_reason: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    custom: dict[str, Any] | None = None
    row_version: int = Field(ge=1)


class StudentSummary(BaseModel):
    id: str
    student_number: str
    status: StudentStatus
    admission_date: date | None = None
    person: PersonOut
    enrollment: EnrollmentOut | None = None
    row_version: int


class StudentList(BaseModel):
    items: list[StudentSummary]
    next_cursor: str | None = None
    total: int


class StudentOut(StudentSummary):
    exit_date: date | None = None
    exit_reason: str | None = None
    notes: str | None = None
    custom: dict[str, Any] = Field(default_factory=dict)
    enrollments: list[EnrollmentOut] = Field(default_factory=list)
    guardians: list[GuardianOut] = Field(default_factory=list)
    medical: MedicalOut | None = None


class StudentRegisterOut(StudentOut):
    duplicate_warnings: list[dict[str, Any]] = Field(default_factory=list)


class DuplicateCheck(BaseModel):
    person: PersonInput


class StudentNumberPreview(BaseModel):
    year_id: uuid.UUID | None = None


class StudentNumberPreviewOut(BaseModel):
    student_number: str
    scope: str
    year: int
    sequence: int


__all__ = [
    "DuplicateCheck",
    "EnrollmentInput",
    "EnrollmentOut",
    "EnrollmentUpdate",
    "GuardianInput",
    "GuardianOut",
    "GuardianUpdate",
    "MedicalInput",
    "MedicalOut",
    "PersonOut",
    "STUDENT_STATUSES",
    "StudentList",
    "StudentNumberPreview",
    "StudentNumberPreviewOut",
    "StudentOut",
    "StudentQuery",
    "StudentRegister",
    "StudentRegisterOut",
    "StudentStatus",
    "StudentSummary",
    "StudentUpdate",
]
