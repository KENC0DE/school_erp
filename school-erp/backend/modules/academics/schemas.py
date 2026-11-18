from __future__ import annotations

import uuid

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
]
