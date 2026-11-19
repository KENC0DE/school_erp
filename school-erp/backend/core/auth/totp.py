"""RFC 6238 TOTP without an external dependency (ARCH §5.2)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlencode

DIGITS = 6
PERIOD = 30
SECRET_BYTES = 20


def generate_secret() -> str:
    """A base32 secret suitable for authenticator apps."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    padded = secret.upper() + "=" * (-len(secret) % 8)
    return base64.b32decode(padded)


def code_at(secret: str, at: datetime | None = None) -> str:
    moment = at or datetime.now(UTC)
    counter = int(moment.timestamp()) // PERIOD
    digest = hmac.new(_key(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % (10**DIGITS):0{DIGITS}d}"


def verify_code(secret: str, code: str, *, at: datetime | None = None, window: int = 1) -> bool:
    value = (code or "").strip().replace(" ", "")
    if len(value) != DIGITS or not value.isdigit():
        return False
    moment = at or datetime.now(UTC)
    for offset in range(-window, window + 1):
        candidate = code_at(secret, moment + timedelta(seconds=offset * PERIOD))
        if secrets.compare_digest(candidate, value):
            return True
    return False


def provisioning_uri(secret: str, account: str, issuer: str) -> str:
    label = quote(f"{issuer}:{account}")
    query = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": DIGITS,
            "period": PERIOD,
        }
    )
    return f"otpauth://totp/{label}?{query}"


def new_recovery_codes(count: int = 10) -> list[str]:
    """Human-friendly one-time codes, returned once at enrollment."""
    codes: list[str] = []
    for _ in range(count):
        raw = secrets.token_hex(4).upper()
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


def _normalize(code: str) -> str:
    return code.strip().replace(" ", "").replace("-", "").upper()


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(_normalize(code).encode()).hexdigest()


def consume_recovery_code(hashes: list[str], code: str) -> list[str] | None:
    """Return the remaining hashes, or None when the code is not valid."""
    digest = hash_recovery_code(code)
    if not any(secrets.compare_digest(digest, stored) for stored in hashes):
        return None
    return [stored for stored in hashes if not secrets.compare_digest(digest, stored)]


__all__ = [
    "DIGITS",
    "PERIOD",
    "code_at",
    "consume_recovery_code",
    "generate_secret",
    "hash_recovery_code",
    "new_recovery_codes",
    "provisioning_uri",
    "verify_code",
]
