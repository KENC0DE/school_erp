"""Payment adapter contract and a sandbox test double (ARCH §9.7, P7-01)."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


@dataclass
class CheckoutRequest:
    invoice_id: str
    amount_santim: int
    currency: str = "ETB"
    customer_email: str | None = None
    return_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckoutSession:
    provider: str
    provider_ref: str
    checkout_url: str
    status: PaymentStatus = PaymentStatus.PENDING


@dataclass
class PaymentEvent:
    provider: str
    event_id: str
    provider_ref: str
    status: PaymentStatus
    amount_santim: int
    currency: str
    occurred_at: datetime
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(Protocol):
    key: str

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession: ...

    async def verify(self, provider_ref: str) -> PaymentEvent: ...

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> PaymentEvent: ...

    async def refund(self, provider_ref: str, amount_santim: int | None = None) -> PaymentEvent: ...


class SignatureError(ValueError):
    pass


def compute_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, signature: str) -> None:
    expected = compute_signature(secret, body)
    if not hmac.compare_digest(expected, signature or ""):
        raise SignatureError("Invalid webhook signature")


class SandboxProvider:
    """In-memory provider used by tests and the dev environment."""

    key = "sandbox"

    def __init__(self, secret: str = "sandbox-secret") -> None:
        self.secret = secret
        self.sessions: dict[str, CheckoutSession] = {}
        self._counter = 0

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        self._counter += 1
        ref = f"sbx_{self._counter}"
        session = CheckoutSession(
            provider=self.key,
            provider_ref=ref,
            checkout_url=f"https://sandbox.invalid/checkout/{ref}",
        )
        self.sessions[ref] = session
        session.metadata = request.metadata  # type: ignore[attr-defined]
        return session

    async def verify(self, provider_ref: str) -> PaymentEvent:
        session = self.sessions[provider_ref]
        return PaymentEvent(
            provider=self.key,
            event_id=f"evt_{provider_ref}",
            provider_ref=provider_ref,
            status=session.status,
            amount_santim=0,
            currency="ETB",
            occurred_at=datetime.now(UTC),
        )

    def sign(self, body: bytes) -> str:
        return compute_signature(self.secret, body)

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> PaymentEvent:
        signature = headers.get("x-sandbox-signature", "")
        verify_signature(self.secret, body, signature)
        data = json.loads(body)
        return PaymentEvent(
            provider=self.key,
            event_id=data["event_id"],
            provider_ref=data["provider_ref"],
            status=PaymentStatus(data["status"]),
            amount_santim=int(data["amount_santim"]),
            currency=data.get("currency", "ETB"),
            occurred_at=datetime.now(UTC),
            raw=data,
        )

    async def refund(self, provider_ref: str, amount_santim: int | None = None) -> PaymentEvent:
        session = self.sessions[provider_ref]
        session.status = PaymentStatus.REFUNDED
        return await self.verify(provider_ref)
