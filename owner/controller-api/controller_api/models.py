from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


def uuid7() -> uuid.UUID:
    builtin = getattr(uuid, "uuid7", None)
    if builtin is not None:
        return builtin()
    return uuid.uuid4()


def new_id() -> str:
    return str(uuid7())


class CPUser(Base):
    __tablename__ = "cp_users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="owner")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class School(Base):
    __tablename__ = "schools"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    school_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    api_base_url: Mapped[str] = mapped_column(String(300), default="")
    logo_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="active")
    min_app_version: Mapped[str] = mapped_column(String(20), default="0.0.0")
    plan: Mapped[str] = mapped_column(String(40), default="standard")
    size_profile: Mapped[str] = mapped_column(String(20), default="small")
    modules: Mapped[list] = mapped_column(JSONType, default=list)
    instance_public_key: Mapped[str | None] = mapped_column(Text)
    app_version: Mapped[str] = mapped_column(String(20), default="0.0.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EnrollmentToken(Base):
    __tablename__ = "enrollments"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(40), ForeignKey("schools.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LicenseRecord(Base):
    __tablename__ = "licenses"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(40), ForeignKey("schools.id"), index=True)
    token: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    modules: Mapped[list] = mapped_column(JSONType)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Heartbeat(Base):
    __tablename__ = "heartbeats"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(40), ForeignKey("schools.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSONType)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VaultEntry(Base):
    __tablename__ = "vault_audit_entries"
    __table_args__ = (UniqueConstraint("school_id", "seq", name="uq_vault_school_seq"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(40), ForeignKey("schools.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    entry: Mapped[dict] = mapped_column(JSONType)
    chain_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VaultChainHead(Base):
    __tablename__ = "vault_chain_heads"

    school_id: Mapped[str] = mapped_column(String(40), ForeignKey("schools.id"), primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer, default=0)
    last_hash: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    school_id: Mapped[str | None] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SigningKey(Base):
    __tablename__ = "signing_keys"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    key_type: Mapped[str] = mapped_column(String(30), index=True)
    kid: Mapped[str] = mapped_column(String(30))
    private_pem: Mapped[str] = mapped_column(Text)
    public_pem: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SupportSession(Base):
    __tablename__ = "support_sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(40), ForeignKey("schools.id"), index=True)
    cp_user_id: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    read_only: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CPAudit(Base):
    __tablename__ = "cp_audit"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(60))
    details: Mapped[dict | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
