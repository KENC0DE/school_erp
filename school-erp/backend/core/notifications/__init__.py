"""Notification adapters (email/SMS/push stubs)."""

from core.notifications.adapters import (
    EmailAdapter,
    LoggingEmailAdapter,
    LoggingSMSAdapter,
    OutboxMessage,
    SMSAdapter,
    SMTPEmailAdapter,
    build_adapters,
)

__all__ = [
    "EmailAdapter",
    "LoggingEmailAdapter",
    "LoggingSMSAdapter",
    "OutboxMessage",
    "SMSAdapter",
    "SMTPEmailAdapter",
    "build_adapters",
]
