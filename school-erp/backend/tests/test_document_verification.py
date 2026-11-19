"""P5-09: public verification of an issued document.

The QR code on a printed document points at ``/verify/{code}``. The page works
without an account, so the endpoint must be public, must reveal only the small
set of facts that prove the paper is genuine, and must not become an oracle for
enumerating every document the school ever issued.

These tests cover the happy path, the deliberately indistinguishable 404 for an
unknown or stale code, and the per-client rate limit.
"""

from __future__ import annotations

import uuid

import pytest

from tests.test_document_generation import (
    _fake_render,
    _layout,
    _level,
    _published_template,
    _request_batch,
    _run_batch,
    _section,
    _student,
    _year,
)

VERIFY = "/api/v1/documents/public/verify"


@pytest.fixture(autouse=True)
def _clean_limiter():
    from modules.documents.verification import verify_limiter

    verify_limiter.reset()
    yield
    verify_limiter.reset()


@pytest.fixture
def fake_render(monkeypatch):
    """Replace the heavy renderer with a tiny valid PDF."""
    monkeypatch.setattr("modules.documents.generation.render_layout", _fake_render)
    return _fake_render


async def _issue_one(client, app, headers) -> dict:
    """Generate a single document and return the issued summary."""
    year = await _year(client, headers)
    level = await _level(client, headers)
    section = await _section(client, headers, year, level)
    student = await _student(client, headers, year, level, section, number="VER-0001")
    template = await _published_template(
        client,
        headers,
        _layout("{{student.full_name}}", "{{document.number}}", "{{school.name}}"),
    )
    started = await _request_batch(
        client,
        headers,
        template,
        {"type": "student", "student_id": student["id"]},
    )
    await _run_batch(app, started["batch_id"])
    listing = await client.get("/api/v1/documents/issued", headers=headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    return listing.json()["items"][0]


async def test_public_verification_returns_only_the_minimal_view(
    client, app, superadmin_headers, fake_render
) -> None:
    summary = await _issue_one(client, app, superadmin_headers)

    # No Authorization header: the guardian scanning the QR code is anonymous.
    response = await client.get(f"{VERIFY}/{summary['verification_code']}")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body == {
        "valid": True,
        "number": "DOC-2026-00001",
        "doc_type": "certificate_completion",
        "recipient_name": "Hana Tesfaye Bekele",
        "issued_at": body["issued_at"],
        "school_name": "Demo Academy",
    }
    assert body["issued_at"]

    # Nothing from the snapshot, the layout or the stored file leaks through.
    for forbidden in ("layout", "data_snapshot", "file_id", "url", "verification_code"):
        assert forbidden not in body


async def test_unknown_code_is_a_generic_404(client) -> None:
    response = await client.get(f"{VERIFY}/{uuid.uuid4().hex}")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["message_key"] == "error.documents.verification_not_found"


async def test_verification_stops_after_the_per_client_limit(
    client, app, superadmin_headers, fake_render, monkeypatch
) -> None:
    summary = await _issue_one(client, app, superadmin_headers)
    monkeypatch.setattr(app.state.settings, "document_verify_rate_limit", 2)
    code = summary["verification_code"]

    first = await client.get(f"{VERIFY}/{code}")
    second = await client.get(f"{VERIFY}/{code}")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    limited = await client.get(f"{VERIFY}/{code}")
    assert limited.status_code == 429
    error = limited.json()["error"]
    assert error["code"] == "RATE_LIMITED"
    assert error["message_key"] == "error.rate_limited"

    # Even a correct code is refused while the window is exhausted, so the
    # limit cannot be bypassed by guessing only known-good codes.
    still_limited = await client.get(f"{VERIFY}/{code}")
    assert still_limited.status_code == 429


async def test_verification_still_requires_the_documents_module(
    client, app, superadmin_headers, fake_render
) -> None:
    summary = await _issue_one(client, app, superadmin_headers)

    disabled = await client.put(
        "/api/v1/system/modules/documents",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    try:
        response = await client.get(f"{VERIFY}/{summary['verification_code']}")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "MODULE_DISABLED"
    finally:
        restored = await client.put(
            "/api/v1/system/modules/documents",
            headers=superadmin_headers,
            json={"enabled": True},
        )
        assert restored.status_code == 200, restored.text
