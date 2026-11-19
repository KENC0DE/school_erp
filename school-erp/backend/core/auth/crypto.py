"""Symmetric encryption for secrets stored at rest (TOTP seeds)."""

from __future__ import annotations

import base64
import hashlib

from app.settings import Settings
from cryptography.fernet import Fernet, InvalidToken


def _fernet(settings: Settings) -> Fernet:
    digest = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(settings: Settings, value: str) -> str:
    return _fernet(settings).encrypt(value.encode()).decode()


def decrypt_secret(settings: Settings, token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet(settings).decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


__all__ = ["decrypt_secret", "encrypt_secret"]
