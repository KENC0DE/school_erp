"""Notification templates, in-app notifications and delivery logs (P1-23)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import (
    Base,
    BusinessModel,
    JSONType,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class NotificationTemplate(BusinessModel):
    """A reusable, translatable message with ``{{variable}}`` placeholders."""

    __tablename__ = "notification_templates"
    __table_args__ = (
        Index("ix_notification_templates_category", "category"),
        Index(
            "uq_notification_templates_key_live",
            "key",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(30), default="general", nullable=False)
    # Translation bundle that holds the title/body keys.
    namespace: Mapped[str] = mapped_column(String(60), default="core", nullable=False)
    title_key: Mapped[str] = mapped_column(String(200), nullable=False)
    body_key: Mapped[str] = mapped_column(String(200), nullable=False)
    default_channels: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)
    module: Mapped[str] = mapped_column(String(60), default="core", nullable=False)


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One recipient's copy of a notification (the in-app centre)."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "read_at"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    template_key: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="general", nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    link: Mapped[str | None] = mapped_column(String(300))
    channels: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeliveryLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-channel delivery attempt, including failures and skipped channels."""

    __tablename__ = "delivery_logs"
    __table_args__ = (Index("ix_delivery_logs_notification", "notification_id", "channel"),)

    notification_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    template_key: Mapped[str] = mapped_column(String(80), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    # Email address, phone number, device token or internal user id.
    recipient: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(60))
    response: Mapped[dict | None] = mapped_column(JSONType)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["DeliveryLog", "Notification", "NotificationTemplate"]
