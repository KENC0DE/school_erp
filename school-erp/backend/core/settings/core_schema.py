"""The core (code-layer) settings model shown on the Settings page."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SchoolProfile(BaseModel):
    name: str = Field("Demo Academy", min_length=1, max_length=200)
    default_language: Literal["en", "am"] = "en"
    enabled_languages: list[str] = Field(default_factory=lambda: ["en", "am"])
    timezone: str = Field("Africa/Addis_Ababa", min_length=1, max_length=80)
    calendar: Literal["ethiopian", "gregorian", "both"] = "both"
    # Set by the first-run wizard (P1-24); kept in settings so branding follows
    # the school profile instead of a separate table.
    logo_file_id: str | None = Field(default=None, max_length=64)


class AcademicScope(BaseModel):
    first_level: int = Field(0, ge=0, le=12)
    last_level: int = Field(12, ge=0, le=12)


class Branding(BaseModel):
    theme: str = Field("default", min_length=1, max_length=60)


class CoreSettings(BaseModel):
    school_profile: SchoolProfile = Field(default_factory=SchoolProfile)
    academic_scope: AcademicScope = Field(default_factory=AcademicScope)
    branding: Branding = Field(default_factory=Branding)


__all__ = ["AcademicScope", "Branding", "CoreSettings", "SchoolProfile"]
