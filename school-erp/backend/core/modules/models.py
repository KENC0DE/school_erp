from __future__ import annotations

import uuid
from datetime import datetime

from core.db.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class InstanceModule(TimestampMixin, Base):
    __tablename__ = "instance_modules"

    module_key: Mapped[str] = mapped_column(String(60), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column()


class LicenseState(TimestampMixin, Base):
    """The last verified license. One row per instance."""

    __tablename__ = "license_state"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default="current")
    token: Mapped[str | None] = mapped_column(Text)
    instance_id: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="active")
    modules: Mapped[list | None] = mapped_column(JSONType)
    plan: Mapped[str | None] = mapped_column(String(40))
    limits: Mapped[dict | None] = mapped_column(JSONType)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    controller_public_key: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InstanceIdentity(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "instance_identity"

    private_key: Mapped[str] = mapped_column(Text, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
