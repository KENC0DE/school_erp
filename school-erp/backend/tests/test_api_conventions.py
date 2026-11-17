"""P1-01: pagination, filtering/sorting, error contract, idempotency and row_version."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.errors import AppError
from core.api.concurrency import parse_if_match, version_from_payload
from core.api.models import IdempotencyRecord
from sqlalchemy import select

NOTES = "/api/v1/sample/notes"


async def _create_note(client, headers, content: str, key: str | None = None) -> dict:
    extra = {"Idempotency-Key": key} if key else {}
    response = await client.post(NOTES, json={"content": content}, headers={**headers, **extra})
    assert response.status_code == 200, response.text
    return response.json()


async def _count_notes(client, headers, query: str) -> int:
    response = await client.get(NOTES, params={"q": query, "limit": 200}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["total"]


# --- error contract ---------------------------------------------------------


def _all_error_classes() -> list[type[AppError]]:
    found: list[type[AppError]] = [AppError]
    queue = list(AppError.__subclasses__())
    while queue:
        cls = queue.pop()
        found.append(cls)
        queue.extend(cls.__subclasses__())
    return found


def test_every_error_class_has_a_stable_code_and_message_key():
    seen: set[str] = set()
    for cls in _all_error_classes():
        error = cls()
        assert error.code == error.code.upper()
        assert " " not in error.code
        assert error.message_key.startswith("error.")
        assert 400 <= error.status_code < 500
        seen.add(error.code)
    # The codes the rest of the platform may switch on today.
    assert {
        "BAD_REQUEST",
        "NOT_FOUND",
        "UNAUTHORIZED",
        "PERMISSION_DENIED",
        "MODULE_DISABLED",
        "CONFLICT",
        "VALIDATION_ERROR",
        "RATE_LIMITED",
        "INVALID_CURSOR",
        "INVALID_SORT",
        "INVALID_FILTER",
        "VERSION_REQUIRED",
        "IDEMPOTENCY_KEY_REUSED",
        "IDEMPOTENCY_IN_PROGRESS",
    } <= seen


async def test_error_envelope_is_the_same_everywhere(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    error = response.json()["error"]
    assert set(error) == {"code", "message_key", "message", "details", "request_id"}
    assert error["code"] == "UNAUTHORIZED"
    assert error["message_key"].startswith("error.")
    assert error["request_id"] == response.headers["x-request-id"]


async def test_version_conflict_message_key_is_specific(client, superadmin_headers):
    note = await _create_note(client, superadmin_headers, "version target")
    await client.patch(
        f"{NOTES}/{note['id']}",
        json={"content": "first update", "row_version": 1},
        headers=superadmin_headers,
    )
    stale = await client.patch(
        f"{NOTES}/{note['id']}",
        json={"content": "stale update", "row_version": 1},
        headers=superadmin_headers,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CONFLICT"
    assert stale.json()["error"]["message_key"] == "error.version_conflict"


# --- pagination, filtering and sorting -------------------------------------


async def test_limit_bounds_are_validated(client, superadmin_headers):
    for value in (0, 500):
        response = await client.get(NOTES, params={"limit": value}, headers=superadmin_headers)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_cursor_walks_every_row_exactly_once(client, superadmin_headers):
    created = [await _create_note(client, superadmin_headers, f"page note {i}") for i in range(5)]

    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        params = {"limit": 2, "sort": "id", "order": "asc"}
        if cursor:
            params["cursor"] = cursor
        response = await client.get(NOTES, params=params, headers=superadmin_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 5
        seen.extend(item["id"] for item in body["items"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert pages == 3
    assert len(seen) == len(set(seen)) == 5
    assert set(seen) == {item["id"] for item in created}


async def test_invalid_sort_and_cursor_are_rejected(client, superadmin_headers):
    bad_sort = await client.get(NOTES, params={"sort": "password"}, headers=superadmin_headers)
    assert bad_sort.status_code == 422
    assert bad_sort.json()["error"]["code"] == "INVALID_SORT"
    assert bad_sort.json()["error"]["details"]["allowed"] == ["author_name", "created_at", "id"]

    bad_cursor = await client.get(NOTES, params={"cursor": "not-a-cursor"}, headers=superadmin_headers)
    assert bad_cursor.status_code == 422
    assert bad_cursor.json()["error"]["code"] == "INVALID_CURSOR"


async def test_filter_is_an_explicit_parameter_and_escapes_wildcards(client, superadmin_headers):
    await _create_note(client, superadmin_headers, "hundred 100% done")
    await _create_note(client, superadmin_headers, "ordinary note")

    literal = await client.get(NOTES, params={"q": "100%"}, headers=superadmin_headers)
    assert literal.status_code == 200
    assert literal.json()["total"] == 1
    assert literal.json()["items"][0]["content"] == "hundred 100% done"

    wildcard = await client.get(NOTES, params={"q": "%"}, headers=superadmin_headers)
    assert wildcard.json()["total"] == 1

    author = await client.get(NOTES, params={"author": "Super"}, headers=superadmin_headers)
    assert author.status_code == 200
    assert author.json()["total"] >= 1


async def test_default_sort_is_newest_first(client, superadmin_headers):
    first = await _create_note(client, superadmin_headers, "oldest marker")
    second = await _create_note(client, superadmin_headers, "newest marker")
    response = await client.get(NOTES, params={"limit": 100}, headers=superadmin_headers)
    ids = [item["id"] for item in response.json()["items"]]
    assert ids.index(second["id"]) < ids.index(first["id"])


# --- idempotency -----------------------------------------------------------


async def test_replaying_an_idempotent_request_returns_the_stored_response(client, superadmin_headers):
    key = f"idem-{uuid.uuid4().hex}"
    first = await client.post(
        NOTES,
        json={"content": "only once"},
        headers={**superadmin_headers, "Idempotency-Key": key},
    )
    assert first.status_code == 200, first.text
    assert "x-idempotent-replay" not in first.headers

    replay = await client.post(
        NOTES,
        json={"content": "only once"},
        headers={**superadmin_headers, "Idempotency-Key": key},
    )
    assert replay.status_code == 200
    assert replay.headers["x-idempotent-replay"] == "true"
    assert replay.json() == first.json()
    assert await _count_notes(client, superadmin_headers, "only once") == 1


async def test_same_key_with_a_different_body_is_a_conflict(client, superadmin_headers):
    key = f"idem-{uuid.uuid4().hex}"
    await client.post(
        NOTES,
        json={"content": "first body"},
        headers={**superadmin_headers, "Idempotency-Key": key},
    )
    conflict = await client.post(
        NOTES,
        json={"content": "different body"},
        headers={**superadmin_headers, "Idempotency-Key": key},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert await _count_notes(client, superadmin_headers, "different body") == 0


async def test_expired_idempotency_records_are_executed_again(client, app, superadmin_headers):
    key = f"idem-{uuid.uuid4().hex}"
    body = {"content": "expiry check"}
    first = await client.post(NOTES, json=body, headers={**superadmin_headers, "Idempotency-Key": key})
    async with app.state.db.session() as session:
        record = (await session.execute(select(IdempotencyRecord))).scalars().one()
        record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    again = await client.post(NOTES, json=body, headers={**superadmin_headers, "Idempotency-Key": key})
    assert again.status_code == 200
    assert "x-idempotent-replay" not in again.headers
    assert again.json()["id"] != first.json()["id"]
    assert await _count_notes(client, superadmin_headers, "expiry check") == 2


async def test_an_in_progress_key_is_rejected(client, app, superadmin_headers):
    import hashlib
    import json

    from core.api.idempotency import IdempotencyMiddleware

    key = f"idem-{uuid.uuid4().hex}"
    body = json.dumps({"content": "should not run"}, separators=(",", ":")).encode()
    fingerprint = IdempotencyMiddleware(None, database=app.state.db)._fingerprint(
        {
            "method": "POST",
            "path": NOTES,
            "query_string": b"",
            "headers": [(b"authorization", superadmin_headers["Authorization"].encode())],
        },
        body,
    )

    async with app.state.db.session() as session:
        session.add(
            IdempotencyRecord(
                key_hash=hashlib.sha256(key.encode()).hexdigest(),
                scope=f"POST {NOTES}",
                request_hash=fingerprint,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        await session.commit()

    response = await client.post(
        NOTES,
        json={"content": "should not run"},
        headers={**superadmin_headers, "Idempotency-Key": key},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_IN_PROGRESS"


async def test_overlong_key_is_rejected(client, superadmin_headers):
    response = await client.post(
        NOTES,
        json={"content": "too long"},
        headers={**superadmin_headers, "Idempotency-Key": "k" * 201},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- optimistic concurrency ------------------------------------------------


async def test_update_bumps_row_version_and_a_stale_write_returns_current_state(client, superadmin_headers):
    note = await _create_note(client, superadmin_headers, "concurrency original")
    assert note["row_version"] == 1

    updated = await client.patch(
        f"{NOTES}/{note['id']}",
        json={"content": "concurrency updated", "row_version": 1},
        headers=superadmin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["content"] == "concurrency updated"
    assert updated.json()["row_version"] == 2

    stale = await client.patch(
        f"{NOTES}/{note['id']}",
        json={"content": "concurrency loser", "row_version": 1},
        headers=superadmin_headers,
    )
    assert stale.status_code == 409
    error = stale.json()["error"]
    assert error["code"] == "CONFLICT"
    assert error["details"]["expected"] == 1
    assert error["details"]["current"] == 2
    assert error["details"]["state"]["content"] == "concurrency updated"

    listing = await client.get(NOTES, params={"q": "concurrency original"}, headers=superadmin_headers)
    assert listing.json()["total"] == 0


async def test_missing_row_version_is_rejected(client, superadmin_headers):
    note = await _create_note(client, superadmin_headers, "needs a version")
    response = await client.patch(
        f"{NOTES}/{note['id']}",
        json={"content": "no version"},
        headers=superadmin_headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_if_match_and_payload_versions_are_parsed_strictly():
    assert parse_if_match(None) is None
    assert parse_if_match('W/"7"') == 7
    assert parse_if_match("3") == 3
    with pytest.raises(AppError) as exc:
        parse_if_match("not-an-int")
    assert exc.value.code == "VERSION_REQUIRED"
    assert version_from_payload({"row_version": 4}) == 4
    with pytest.raises(AppError):
        version_from_payload({})
