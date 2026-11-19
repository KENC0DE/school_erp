from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import Base, JSONType, UUIDPrimaryKeyMixin


class IdempotencyRecord(UUIDPrimaryKeyMixin, Base):
    """One stored response for a mutating request (ARCH §5.1).

    ``status_code`` is NULL while the original request is still running, which
    lets a concurrent replay answer ``IDEMPOTENCY_IN_PROGRESS`` instead of
    executing the mutation twice.
    """

    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("key_hash", "scope", name="uq_idempotency_key_scope"),)

    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(300), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    response_headers: Mapped[list | None] = mapped_column(JSONType)
    response_body: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


__all__ = ["IdempotencyRecord"]
