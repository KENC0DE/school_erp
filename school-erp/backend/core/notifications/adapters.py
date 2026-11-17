"""Outbound email/SMS behind adapters (ARCH §8.11, §5.12)."""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

import anyio
from app.settings import Settings

logger = logging.getLogger("erp.notifications")


@dataclass
class OutboxMessage:
    channel: str
    to: str
    subject: str
    body: str
    meta: dict = field(default_factory=dict)


class EmailAdapter(Protocol):
    async def send(self, *, to: str, subject: str, body: str) -> None: ...


class SMSAdapter(Protocol):
    async def send(self, *, to: str, body: str) -> None: ...


class PushAdapter(Protocol):
    async def send(self, *, user_id: str, title: str, body: str, data: dict) -> None: ...


@dataclass
class PushMessage:
    user_id: str
    title: str
    body: str
    data: dict = field(default_factory=dict)


@dataclass
class LoggingPushAdapter:
    """Stand-in for the controller push relay until P11-12.

    Payloads stay minimal (title and deep link only) so the same interface can
    be pointed at the signed controller endpoint without changing callers.
    """

    outbox: list[PushMessage] = field(default_factory=list)

    async def send(self, *, user_id: str, title: str, body: str, data: dict) -> None:
        payload = {"link": data.get("link"), "notification_id": data.get("notification_id")}
        self.outbox.append(PushMessage(user_id=user_id, title=title, body="", data=payload))
        logger.info("push to %s: %s", user_id, title)


@dataclass
class LoggingEmailAdapter:
    """Dev/test adapter: keeps messages in memory and logs them."""

    outbox: list[OutboxMessage] = field(default_factory=list)

    async def send(self, *, to: str, subject: str, body: str) -> None:
        self.outbox.append(OutboxMessage("email", to, subject, body))
        logger.info("email to %s: %s", to, subject)


@dataclass
class LoggingSMSAdapter:
    outbox: list[OutboxMessage] = field(default_factory=list)

    async def send(self, *, to: str, body: str) -> None:
        self.outbox.append(OutboxMessage("sms", to, "", body))
        logger.info("sms to %s", to)


@dataclass
class SMTPEmailAdapter:
    """Mailpit in development, any SMTP relay in production."""

    settings: Settings

    async def send(self, *, to: str, subject: str, body: str) -> None:
        await anyio.to_thread.run_sync(self._send, to, subject, body)

    def _send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.settings.mail_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=5) as smtp:
                smtp.send_message(message)
        except OSError as exc:
            # A missing Mailpit must never turn a password reset into a 500.
            logger.warning("email delivery failed: %s", exc)


def build_adapters(settings: Settings) -> tuple[EmailAdapter, SMSAdapter]:
    if settings.mail_adapter == "log" or settings.app_env.lower() == "test":
        email: EmailAdapter = LoggingEmailAdapter()
    else:
        email = SMTPEmailAdapter(settings)
    return email, LoggingSMSAdapter()


def build_push_adapter(settings: Settings) -> PushAdapter:  # noqa: ARG001
    """Return the push transport.

    Until the controller relay lands in P11-12 every instance uses the logging
    stub; push credentials will stay in the controller, never here.
    """
    return LoggingPushAdapter()


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
