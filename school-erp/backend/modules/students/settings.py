"""Configurable student numbering (ARCH §9.2).

The school owns the number format, its scope and the first value. Sequences are
stored per scope so turning the feature on never re-numbers existing students.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from modules.students.number_formats import (
    MAX_FORMAT_LENGTH,
    validate_number_format,
)


class NumberingSettings(BaseModel):
    format: str = Field(
        "STU-{year}-{seq:04d}",
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
    def _year_scope_needs_year_token(self) -> NumberingSettings:
        if self.scope == "year" and "{year}" not in self.format:
            raise ValueError(
                "A year-scoped format must contain {year}; otherwise two years would issue the same number"
            )
        return self


class StudentSettings(BaseModel):
    """Module-owned settings rendered on the Settings page."""

    numbering: NumberingSettings = Field(default_factory=NumberingSettings)


__all__ = ["NumberingSettings", "StudentSettings"]
