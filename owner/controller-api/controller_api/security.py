from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from controller_api.settings import ControllerSettings

_hasher = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, ValueError):
        return False


def create_token(settings: ControllerSettings, user_id: str, role: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "role": role,
            "type": "cp_access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
        },
        settings.controller_secret_key,
        algorithm="HS256",
    )


def decode_token(settings: ControllerSettings, token: str) -> dict:
    return jwt.decode(
        token, settings.controller_secret_key, algorithms=["HS256"], options={"require": ["sub", "exp"]}
    )
