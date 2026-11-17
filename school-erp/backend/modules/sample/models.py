from __future__ import annotations

import uuid

from core.db.base import BusinessModel
from sqlalchemy import Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column


class SampleNote(BusinessModel):
    __tablename__ = "sample_notes"
    __table_args__ = (
        # Partial index: the list endpoint only ever reads live rows.
        Index(
            "ix_sample_notes_live",
            "created_at",
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str] = mapped_column(String(200), default="")
    author_id: Mapped[uuid.UUID | None] = mapped_column()
