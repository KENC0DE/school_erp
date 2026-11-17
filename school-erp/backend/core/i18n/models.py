from __future__ import annotations

import uuid

from core.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class TranslationEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "translation_entries"
    __table_args__ = (UniqueConstraint("namespace", "key", "locale", "layer", name="uq_translation_key"),)

    namespace: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    locale: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="approved")
    source: Mapped[str] = mapped_column(String(20), default="human")
    layer: Mapped[str] = mapped_column(String(20), default="default")
    updated_by: Mapped[uuid.UUID | None] = mapped_column()
