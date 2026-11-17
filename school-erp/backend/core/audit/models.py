from __future__ import annotations

import uuid
from datetime import datetime

from core.db.base import Base, BigIntPK, JSONType, Uuid, UUIDPrimaryKeyMixin
from sqlalchemy import DateTime, String, Text, event, func
from sqlalchemy.orm import Mapped, mapped_column


class AuditLog(Base):
    """Append-only, hash-chained audit entries (ARCH §5.4)."""

    __tablename__ = "audit_log"

    seq: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_type: Mapped[str] = mapped_column(String(20), default="system")
    actor_id: Mapped[str | None] = mapped_column(String(80))
    on_behalf_of: Mapped[str | None] = mapped_column(String(80))
    via: Mapped[str] = mapped_column(String(20), default="api")
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    module: Mapped[str | None] = mapped_column(String(60))
    entity_type: Mapped[str | None] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(120))
    before: Mapped[dict | None] = mapped_column(JSONType)
    after: Mapped[dict | None] = mapped_column(JSONType)
    reason: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(80))
    reverts_id: Mapped[str | None] = mapped_column(String(80))
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), nullable=False)


class AuditOutbox(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_outbox"

    audit_seq: Mapped[int] = mapped_column(BigIntPK, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    batch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    attempts: Mapped[int] = mapped_column(default=0)


@event.listens_for(AuditLog.__table__, "after_create")
def _guard_audit_log(target, connection, **kwargs):  # type: ignore[no-untyped-def]
    """The app role may append to the chain only (ARCH §5.4).

    PostgreSQL enforces this with REVOKE on the app role (see the Alembic
    migration). SQLite has no role system, so triggers enforce the same rule in
    development and tests.
    """
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql(
            "CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log "
            "BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END"
        )
        connection.exec_driver_sql(
            "CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log "
            "BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END"
        )
