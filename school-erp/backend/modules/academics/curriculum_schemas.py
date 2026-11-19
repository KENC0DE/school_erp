from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from modules.academics.schemas import TermSystem
from modules.academics.subject_schemas import LevelSubjectOut


class CurriculumProfileCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    term_system: TermSystem = "semester"
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool = True


class CurriculumProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    term_system: TermSystem | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool | None = None
    is_verified: bool | None = None
    row_version: int = Field(ge=1)


class CurriculumProfileDuplicate(BaseModel):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    reason: str | None = Field(default=None, max_length=500)


class CurriculumSubjectEntry(BaseModel):
    subject_id: uuid.UUID
    credit: int = Field(1, ge=0, le=100)


class CurriculumLevelReplace(BaseModel):
    subjects: list[CurriculumSubjectEntry]
    reason: str | None = Field(default=None, max_length=500)


class CurriculumLevelOut(BaseModel):
    level_id: str
    level_code: str
    level_name: str
    subjects: list[LevelSubjectOut]
    total: int


class CurriculumProfileOut(BaseModel):
    id: str
    code: str
    name: str
    name_am: str | None = None
    description: str | None = None
    term_system: TermSystem
    sort_order: int
    is_active: bool
    is_starter: bool
    is_verified: bool
    in_use: bool
    levels: list[CurriculumLevelOut]
    row_version: int


class CurriculumProfileList(BaseModel):
    items: list[CurriculumProfileOut]
    next_cursor: None = None
    total: int


class CurriculumApply(BaseModel):
    year_id: uuid.UUID
    # Preview first, then repeat with confirm=True to write the changes.
    confirm: bool = False
    row_version: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=500)


class CurriculumApplyOut(BaseModel):
    year_id: str
    year_code: str
    profile_id: str
    profile_code: str
    profile_name: str
    profile_term_system: TermSystem
    year_term_system: TermSystem
    term_system_matches: bool
    applied: bool
    levels_changed: int
    assignments_added: int
    assignments_removed: int
    credits_changed: int
    changed_levels: list[str]
    skipped_inactive_subjects: list[str]


__all__ = [
    "CurriculumApply",
    "CurriculumApplyOut",
    "CurriculumLevelOut",
    "CurriculumLevelReplace",
    "CurriculumProfileCreate",
    "CurriculumProfileDuplicate",
    "CurriculumProfileList",
    "CurriculumProfileOut",
    "CurriculumProfileUpdate",
    "CurriculumSubjectEntry",
]
