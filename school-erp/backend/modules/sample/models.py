from __future__ import annotations

import uuid

from core.db.base import BusinessModel
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column


class SampleNote(BusinessModel):
    __tablename__ = "sample_notes"

    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str] = mapped_column(String(200), default="")
    author_id: Mapped[uuid.UUID | None] = mapped_column()
