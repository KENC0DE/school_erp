from __future__ import annotations

from core.db.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column


class Theme(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "themes"

    key: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tokens: Mapped[dict] = mapped_column(JSONType, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
