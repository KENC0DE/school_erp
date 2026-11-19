from __future__ import annotations

from core.db.base import (
    ActorMixin,
    Base,
    JSONType,
    RowVersionMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column


class Theme(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    SoftDeleteMixin,
    ActorMixin,
    RowVersionMixin,
    Base,
):
    __tablename__ = "themes"

    key: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    tokens: Mapped[dict] = mapped_column(JSONType, nullable=False)
    # is_active means "available to this school's users"; is_default is the
    # school-wide fallback. Both are independent so an admin can hide a theme
    # without changing anybody's default.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="builtin")
    source_url: Mapped[str | None] = mapped_column(String(500))
