from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class NoteOut(BaseModel):
    id: str
    content: str
    author_name: str
    created_at: datetime | None = None

    @classmethod
    def from_model(cls, note) -> NoteOut:  # type: ignore[no-untyped-def]
        return cls(
            id=str(note.id),
            content=note.content,
            author_name=note.author_name,
            created_at=note.created_at,
        )


class NoteList(BaseModel):
    items: list[NoteOut]
    next_cursor: str | None = None


__all__ = ["NoteCreate", "NoteList", "NoteOut", "uuid"]
