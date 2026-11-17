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


__all__ = [
    "EmailAdapter",
    "LoggingEmailAdapter",
    "LoggingSMSAdapter",
    "OutboxMessage",
    "SMSAdapter",
    "SMTPEmailAdapter",
    "build_adapters",
]
