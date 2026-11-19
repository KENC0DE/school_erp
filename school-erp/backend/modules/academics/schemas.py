from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ScopeOut(BaseModel):
    first_level: int
    last_level: int
    level_count: int
    stage_count: int
    scope_levels: list[int]


class ScopeUpdate(BaseModel):
    first_level: int = Field(ge=0, le=12)
    last_level: int = Field(ge=0, le=12)
    reason: str | None = Field(default=None, max_length=500)


class LevelCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=80)
    name_am: str | None = Field(default=None, max_length=80)
    scope_level: int = Field(ge=0, le=12)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool = True
    is_verified: bool = True


class LevelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    name_am: str | None = Field(default=None, max_length=80)
    scope_level: int | None = Field(default=None, ge=0, le=12)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool | None = None
    is_verified: bool | None = None
    row_version: int = Field(ge=1)


class LevelOut(BaseModel):
    id: str
    code: str
    name: str
    name_am: str | None = None
    scope_level: int
    sort_order: int
    is_active: bool
    is_starter: bool
    is_verified: bool
    in_scope: bool
    row_version: int


class LevelList(BaseModel):
    items: list[LevelOut]
    next_cursor: None = None
    total: int
    scope: ScopeOut


class StageCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=80)
    name_am: str | None = Field(default=None, max_length=80)
    level_ids: list[uuid.UUID] = Field(min_length=1)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool = True
    is_verified: bool = True


class StageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    name_am: str | None = Field(default=None, max_length=80)
    level_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool | None = None
    is_verified: bool | None = None
    row_version: int = Field(ge=1)


class StageOut(BaseModel):
    id: str
    code: str
    name: str
    name_am: str | None = None
    sort_order: int
    is_active: bool
    is_starter: bool
    is_verified: bool
    in_scope: bool
    levels: list[LevelOut]
    row_version: int


class StageList(BaseModel):
    items: list[StageOut]
    next_cursor: None = None
    total: int
    scope: ScopeOut


YearStatus = Literal["draft", "open", "closed"]
TermStatus = Literal["pending", "open", "closed"]
TermSystem = Literal["semester", "quarter"]


class TermInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    start_date: date
    end_date: date


class YearCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9/_-]*$")
    name: str = Field(min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    start_date: date
    end_date: date
    # Optional explicit term boundaries; omitted terms are split evenly across
    # the year using the school's term system.
    terms: list[TermInput] | None = Field(default=None, max_length=6)
    # Choose a curriculum bundle when creating the year; its term system and
    # subjects become the year's starting point.
    curriculum_profile_id: uuid.UUID | None = None


class YearUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    row_version: int = Field(ge=1)


class TermUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    row_version: int = Field(ge=1)


class TermOut(BaseModel):
    id: str
    year_id: str
    number: int
    name: str
    name_am: str | None = None
    start_date: date
    end_date: date
    start_date_ec: str
    end_date_ec: str
    start_date_display: str
    end_date_display: str
    status: TermStatus
    row_version: int


class YearOut(BaseModel):
    id: str
    code: str
    name: str
    name_am: str | None = None
    start_date: date
    end_date: date
    start_date_ec: str
    end_date_ec: str
    start_date_display: str
    end_date_display: str
    term_system: TermSystem
    status: YearStatus
    current_term_id: str | None = None
    curriculum_profile_id: str | None = None
    curriculum_profile_code: str | None = None
    terms: list[TermOut]
    row_version: int


class YearList(BaseModel):
    items: list[YearOut]
    next_cursor: None = None
    total: int
    current_year_id: str | None = None


__all__ = [
    "LevelCreate",
    "LevelList",
    "LevelOut",
    "LevelUpdate",
    "ScopeOut",
    "ScopeUpdate",
    "StageCreate",
    "StageList",
    "StageOut",
    "StageUpdate",
    "TermInput",
    "TermOut",
    "TermStatus",
    "TermSystem",
    "TermUpdate",
    "YearCreate",
    "YearList",
    "YearOut",
    "YearStatus",
    "YearUpdate",
]
