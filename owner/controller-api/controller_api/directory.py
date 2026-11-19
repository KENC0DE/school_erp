from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from erp_shared.license import sign_payload
from fastapi import Request

from controller_api.keys import KeyMaterial
from controller_api.models import School


async def build_directory_record(school: School, key: KeyMaterial) -> dict:
    record = {
        "instance_id": school.id,
        "name": school.name,
        "api_base_url": school.api_base_url,
        "logo_url": school.logo_url,
        "status": school.status,
        "min_app_version": school.min_app_version,
        "iat": int(time.time()),
        "exp": int((datetime.now(UTC) + timedelta(hours=24)).timestamp()),
        "kid": key.kid,
    }
    record["signature"] = sign_payload(key.private_pem, record, kid=key.kid)
    return record


class SlidingWindowLimiter:
    """Small in-process limiter. Redis-backed in production (Phase 11)."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window = window_seconds
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self.hits[key]
        while bucket and bucket[0] < now - self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True

    def reset(self) -> None:
        self.hits.clear()


def client_key(request: Request, code: str = "") -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{code.upper()}" if code else host


def new_school_code(length: int = 6) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
