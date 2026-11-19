from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class SectionCreate(BaseModel):
    year_id: uuid.UUID
    level_id: uuid.UUID
    code: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    name: str | None = Field(default=None, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    capacity: int = Field(40, ge=1, le=500)
    homeroom_user_id: uuid.UUID | None = None
    is_active: bool = True


class SectionUpdate(BaseModel):
    code: str | None = Field(
        default=None, min_length=1, max_length=30, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
    )
    name: str | None = Field(default=None, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    capacity: int | None = Field(default=None, ge=1, le=500)
    homeroom_user_id: uuid.UUID | None = None
    is_active: bool | None = None
    row_version: int = Field(ge=1)


class SectionOut(BaseModel):
    id: str
    year_id: str
    year_code: str
    level_id: str
    level_code: str
    level_name: str
    code: str
    name: str | None = None
    name_am: str | None = None
    capacity: int
    homeroom_user_id: str | None = None
    homeroom_name: str | None = None
    is_active: bool
    row_version: int


class SectionList(BaseModel):
    items: list[SectionOut]
    next_cursor: None = None
    total: int


__all__ = ["SectionCreate", "SectionList", "SectionOut", "SectionUpdate"]
