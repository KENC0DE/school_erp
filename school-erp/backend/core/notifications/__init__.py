"""Notification adapters (email/SMS/push stubs)."""

from core.notifications.adapters import (
    EmailAdapter,
    LoggingEmailAdapter,
    LoggingPushAdapter,
    LoggingSMSAdapter,
    OutboxMessage,
    PushAdapter,
    PushMessage,
    SMSAdapter,
    SMTPEmailAdapter,
    build_adapters,
    build_push_adapter,
)

__all__ = [
    "EmailAdapter",
    "LoggingEmailAdapter",
    "LoggingPushAdapter",
    "LoggingSMSAdapter",
    "OutboxMessage",
    "PushAdapter",
    "PushMessage",
    "SMSAdapter",
    "SMTPEmailAdapter",
    "build_adapters",
    "build_push_adapter",
]
