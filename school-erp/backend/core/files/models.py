from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import (
    ActorMixin,
    Base,
    BigInteger,
    RowVersionMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class StoredFile(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    SoftDeleteMixin,
    ActorMixin,
    RowVersionMixin,
    Base,
):
    """Metadata for one object in the configured storage driver (ARCH §5.12)."""

    __tablename__ = "files"
    __table_args__ = (
        Index("ix_files_owner", "owner_entity_type", "owner_entity_id"),
        Index("ix_files_deleted_at", "deleted_at"),
        Index(
            "uq_files_object_key_live",
            "object_key",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    object_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # The entity this file belongs to (for example ``student``/``<uuid>``).
    owner_entity_type: Mapped[str | None] = mapped_column(String(80))
    owner_entity_id: Mapped[str | None] = mapped_column(String(80))
    is_private: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    thumbnail_key: Mapped[str | None] = mapped_column(String(255))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column()
