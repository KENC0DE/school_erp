"""Idempotency-Key handling for mutating requests (ARCH §5.1).

A client may send ``Idempotency-Key`` on any POST/PUT/PATCH/DELETE. The first
completed JSON response is stored for 24 hours; a replay with the same key,
endpoint and payload gets the stored status/body back without running the
mutation again. Reusing a key with a different payload is a conflict.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.errors import error_body
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from core.api.models import IdempotencyRecord

HEADER = b"idempotency-key"
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
MAX_KEY_LENGTH = 200
MAX_STORED_BODY = 1_000_000
SKIP_RESPONSE_HEADERS = {
    b"content-length",
    b"transfer-encoding",
    b"connection",
    b"set-cookie",
    b"date",
    b"server",
}

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1")
    return None


def _error_response(scope: Scope, *, status: int, code: str, message_key: str, details: Any = None) -> bytes:
    request_id = scope.get("state", {}).get("request_id", "")
    return json.dumps(
        error_body(
            code=code,
            message_key=message_key,
            message=code.replace("_", " ").title(),
            details=details,
            request_id=request_id,
        )
    ).encode()


async def _read_body(receive: Receive) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


class IdempotencyMiddleware:
    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        *,
        database: Any,
        ttl_seconds: int = 86_400,
        enabled: bool = True,
    ) -> None:
        self.app = app
        self.database = database
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.enabled or scope["type"] != "http" or scope["method"] not in MUTATING_METHODS:
            await self.app(scope, receive, send)
            return

        raw_key = _header(scope, HEADER)
        if raw_key is None or not raw_key.strip():
            await self.app(scope, receive, send)
            return
        key = raw_key.strip()
        if len(key) > MAX_KEY_LENGTH:
            await self._send_error(
                scope,
                send,
                status=422,
                code="VALIDATION_ERROR",
                message_key="error.invalid_idempotency_key",
                details={"max_length": MAX_KEY_LENGTH},
            )
            return

        body = await _read_body(receive)
        request_hash = self._fingerprint(scope, body)
        scope_name = f"{scope['method']} {scope['path']}"
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        state = await self._begin(key_hash, scope_name, request_hash)
        if state["action"] == "replay":
            await self._replay(scope, send, state["record"])
            return
        if state["action"] == "conflict":
            await self._send_error(
                scope,
                send,
                status=409,
                code="IDEMPOTENCY_KEY_REUSED",
                message_key="error.idempotency_key_reused",
            )
            return
        if state["action"] == "in_progress":
            await self._send_error(
                scope,
                send,
                status=409,
                code="IDEMPOTENCY_IN_PROGRESS",
                message_key="error.idempotency_in_progress",
            )
            return

        received = False

        async def replay_receive() -> Message:
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        status: int | None = None
        headers: list[tuple[bytes, bytes]] = []
        captured = bytearray()
        too_large = False

        async def capture_send(message: Message) -> None:
            nonlocal status, headers, too_large
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if len(captured) + len(chunk) > MAX_STORED_BODY:
                    too_large = True
                elif not too_large:
                    captured.extend(chunk)
            await send(message)

        try:
            await self.app(scope, replay_receive, capture_send)
        except Exception:
            await self._discard(key_hash, scope_name)
            raise

        content_type = next((v for k, v in headers if k.lower() == b"content-type"), b"")
        storable = (
            status is not None
            and status < 500
            and not too_large
            and content_type.split(b";")[0].strip() == b"application/json"
        )
        if storable:
            await self._finish(
                key_hash,
                scope_name,
                status=status or 200,
                headers=headers,
                body=bytes(captured),
            )
        else:
            await self._discard(key_hash, scope_name)

    def _fingerprint(self, scope: Scope, body: bytes) -> str:
        token = _header(scope, b"authorization") or ""
        material = b"\n".join(
            [
                scope["method"].encode(),
                scope["path"].encode(),
                scope.get("query_string", b""),
                token.encode(),
                body,
            ]
        )
        return hashlib.sha256(material).hexdigest()

    async def _begin(self, key_hash: str, scope_name: str, request_hash: str) -> dict[str, Any]:
        now = _utcnow()
        async with self.database.session() as session:
            await session.execute(delete(IdempotencyRecord).where(IdempotencyRecord.expires_at < now))
            row = await self._find(session, key_hash, scope_name)
            if row is not None:
                result = self._classify(row, request_hash)
                if result is not None:
                    await session.commit()
                    return result
                await session.delete(row)
                await session.flush()
            session.add(
                IdempotencyRecord(
                    key_hash=key_hash,
                    scope=scope_name,
                    request_hash=request_hash,
                    expires_at=now + timedelta(seconds=self.ttl_seconds),
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                row = await self._find(session, key_hash, scope_name)
                if row is None:
                    return {"action": "insert"}
                return self._classify(row, request_hash) or {"action": "in_progress"}
        return {"action": "insert"}

    @staticmethod
    def _classify(row: IdempotencyRecord, request_hash: str) -> dict[str, Any] | None:
        if row.request_hash != request_hash:
            return {"action": "conflict"}
        if row.status_code is None:
            return {"action": "in_progress"}
        return {"action": "replay", "record": row}

    @staticmethod
    async def _find(session: Any, key_hash: str, scope_name: str) -> IdempotencyRecord | None:
        return (
            await session.execute(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.key_hash == key_hash,
                    IdempotencyRecord.scope == scope_name,
                )
            )
        ).scalar_one_or_none()

    async def _finish(
        self,
        key_hash: str,
        scope_name: str,
        *,
        status: int,
        headers: list[tuple[bytes, bytes]],
        body: bytes,
    ) -> None:
        stored_headers = [
            [name.decode("latin-1"), value.decode("latin-1")]
            for name, value in headers
            if name.lower() not in SKIP_RESPONSE_HEADERS
        ]
        async with self.database.session() as session:
            row = await self._find(session, key_hash, scope_name)
            if row is None:
                return
            row.status_code = status
            row.response_headers = stored_headers
            row.response_body = body
            row.expires_at = _utcnow() + timedelta(seconds=self.ttl_seconds)
            await session.commit()

    async def _discard(self, key_hash: str, scope_name: str) -> None:
        async with self.database.session() as session:
            row = await self._find(session, key_hash, scope_name)
            if row is not None:
                await session.delete(row)
                await session.commit()

    async def _replay(self, scope: Scope, send: Send, row: IdempotencyRecord) -> None:
        headers = [
            (name.encode("latin-1"), value.encode("latin-1")) for name, value in (row.response_headers or [])
        ]
        headers.append((b"x-idempotent-replay", b"true"))
        await send(
            {
                "type": "http.response.start",
                "status": row.status_code or 200,
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": row.response_body or b"",
                "more_body": False,
            }
        )

    async def _send_error(
        self,
        scope: Scope,
        send: Send,
        *,
        status: int,
        code: str,
        message_key: str,
        details: Any = None,
    ) -> None:
        body = _error_response(scope, status=status, code=code, message_key=message_key, details=details)
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})


__all__ = ["IdempotencyMiddleware", "MUTATING_METHODS"]
