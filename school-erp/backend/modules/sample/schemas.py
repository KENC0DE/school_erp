from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from core.api.pagination import DEFAULT_LIMIT, MAX_LIMIT
from pydantic import BaseModel, Field


class NoteQuery(BaseModel):
    limit: int = Field(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    cursor: str | None = Field(None, max_length=1000)
    sort: str = Field("created_at", max_length=60)
    order: Literal["asc", "desc"] = "desc"
    q: str | None = Field(None, max_length=200, description="Substring match on the note body")
    author: str | None = Field(None, max_length=200, description="Substring match on the author name")


class NoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class NoteUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    row_version: int = Field(ge=1, description="The row_version the client last read")


class NoteOut(BaseModel):
    id: str
    content: str
    author_name: str
    created_at: datetime | None = None
    row_version: int = 1

    @classmethod
    def from_model(cls, note) -> NoteOut:  # type: ignore[no-untyped-def]
        return cls(
            id=str(note.id),
            content=note.content,
            author_name=note.author_name,
            created_at=note.created_at,
            row_version=note.row_version,
        )


class NoteList(BaseModel):
    items: list[NoteOut]
    next_cursor: str | None = None
    total: int | None = None


__all__ = ["NoteCreate", "NoteList", "NoteOut", "NoteQuery", "NoteUpdate", "uuid"]
