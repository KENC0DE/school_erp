"""Configurable admissions form, entrance test and auto-assignment (ARCH §9.2).

Every choice a school makes about admissions lives here: the number format, the
optional entrance test, the guardian defaults and whether the office or the
system picks the section. Nothing is hard-coded per school.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from modules.students.number_formats import MAX_FORMAT_LENGTH, validate_number_format


class AdmissionNumbering(BaseModel):
    format: str = Field(
        "ADM-{year}-{seq:04d}",
        min_length=1,
        max_length=MAX_FORMAT_LENGTH,
        description="Placeholders: {year} and exactly one {seq} or {seq:04d}",
    )
    scope: Literal["year", "global"] = Field(
        "year",
        description="Reset the sequence each academic year, or keep one global sequence",
    )
    start: int = Field(
        1,
        ge=1,
        le=999_999_999,
        description="The first value used when a scope has no sequence yet",
    )

    @field_validator("format")
    @classmethod
    def _check_format(cls, value: str) -> str:
        return validate_number_format(value)

    @model_validator(mode="after")
    def _year_scope_needs_year_token(self) -> AdmissionNumbering:
        if self.scope == "year" and "{year}" not in self.format:
            raise ValueError(
                "A year-scoped format must contain {year}; otherwise two years would issue the same number"
            )
        return self


class EntranceTestSettings(BaseModel):
    enabled: bool = Field(True, description="Ask for an entrance test before an offer")
    max_score: int = Field(100, ge=1, le=1000, description="Highest possible test score")
    pass_score: int | None = Field(
        50,
        ge=0,
        le=1000,
        description="Minimum score for an offer; blank means any recorded score passes",
    )

    @model_validator(mode="after")
    def _pass_within_max(self) -> EntranceTestSettings:
        if self.pass_score is not None and self.pass_score > self.max_score:
            raise ValueError("pass_score cannot be higher than max_score")
        return self


class AdmissionFormSettings(BaseModel):
    require_guardian: bool = Field(True, description="An application needs at least one guardian")
    public_enabled: bool = Field(
        False,
        description="Expose the optional public application page; off by default",
    )
    public_min_seconds: int = Field(
        3,
        ge=0,
        le=300,
        description="Reject a public submission returned faster than this many seconds",
    )
    public_rate_limit: int = Field(
        5,
        ge=1,
        le=100,
        description="Public submissions accepted from one address per hour",
    )
    guardian_accounts_on_conversion: bool = Field(
        True, description="Create parent accounts for guardians that asked for one"
    )
    guardian_role_key: str = Field(
        "parent",
        min_length=1,
        max_length=60,
        description="The only role a guardian account may receive",
    )


class AssignmentSettings(BaseModel):
    auto_assign_section: bool = Field(True, description="Pick a section when the application has none")
    section_strategy: Literal["least_filled", "first"] = Field(
        "least_filled",
        description="Least filled picks the empty seat; first follows section code order",
    )


class AdmissionSettings(BaseModel):
    numbering: AdmissionNumbering = Field(default_factory=AdmissionNumbering)
    entrance_test: EntranceTestSettings = Field(default_factory=EntranceTestSettings)
    form: AdmissionFormSettings = Field(default_factory=AdmissionFormSettings)
    assignment: AssignmentSettings = Field(default_factory=AssignmentSettings)


__all__ = [
    "AdmissionFormSettings",
    "AdmissionNumbering",
    "AdmissionSettings",
    "AssignmentSettings",
    "EntranceTestSettings",
]
