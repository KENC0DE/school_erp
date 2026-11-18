from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class SubjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool = True


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool | None = None
    row_version: int = Field(ge=1)


class SubjectOut(BaseModel):
    id: str
    code: str
    name: str
    name_am: str | None = None
    sort_order: int
    is_active: bool
    row_version: int


class SubjectList(BaseModel):
    items: list[SubjectOut]
    next_cursor: None = None
    total: int


class LevelSubjectEntry(BaseModel):
    subject_id: uuid.UUID
    credit: int = Field(1, ge=0, le=100)


class LevelSubjectReplace(BaseModel):
    subjects: list[LevelSubjectEntry]
    reason: str | None = Field(default=None, max_length=500)


class LevelSubjectOut(BaseModel):
    subject_id: str
    code: str
    name: str
    name_am: str | None = None
    credit: int
    is_active: bool


class LevelSubjectsOut(BaseModel):
    level_id: str
    level_code: str
    items: list[LevelSubjectOut]
    total: int


class SubjectGroupCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool = True
    subject_ids: list[uuid.UUID] = Field(default_factory=list)


class SubjectGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool | None = None
    subject_ids: list[uuid.UUID] | None = None
    row_version: int = Field(ge=1)


class SubjectGroupOut(BaseModel):
    id: str
    code: str
    name: str
    name_am: str | None = None
    sort_order: int
    is_active: bool
    subjects: list[SubjectOut]
    row_version: int


class SubjectGroupList(BaseModel):
    items: list[SubjectGroupOut]
    next_cursor: None = None
    total: int


__all__ = [
    "LevelSubjectEntry",
    "LevelSubjectOut",
    "LevelSubjectReplace",
    "LevelSubjectsOut",
    "SubjectCreate",
    "SubjectGroupCreate",
    "SubjectGroupList",
    "SubjectGroupOut",
    "SubjectGroupUpdate",
    "SubjectList",
    "SubjectOut",
    "SubjectUpdate",
]
