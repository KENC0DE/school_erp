from __future__ import annotations

import secrets
import time
import uuid

from sqlalchemy import JSON, BigInteger, DateTime, Integer, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

JSONType = JSON().with_variant(JSONB(), "postgresql")


def uuid7() -> uuid.UUID:
    """RFC 9562 UUIDv7. Python 3.14 ships uuid.uuid7; fall back for 3.12/3.13."""
    builtin = getattr(uuid, "uuid7", None)
    if builtin is not None:
        return builtin()
    timestamp_ms = int(time.time() * 1000)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (timestamp_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b
    return uuid.UUID(int=value)


BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7)


class TimestampMixin:
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDeleteMixin:
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class ActorMixin:
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)


class RowVersionMixin:
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class BusinessModel(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, ActorMixin, RowVersionMixin, Base):
    __abstract__ = True


class UTCDateTime(TypeDecorator):
    """Store naive UTC and return timezone-aware values on every backend."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        return value.astimezone(tz=None) if value.tzinfo else value
