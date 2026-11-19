"""P5-11: staff fields and staff-targeted document generation.

The experience-letter starter binds `staff.*` tokens, so the staff module now
registers fields and the worker builds the same kind of data snapshot for a
staff recipient that it already builds for a student. Fee fields stay deferred:
the receipts starter renders, but wiring live invoice data waits for Phase 7.
"""

from __future__ import annotations

from tests.test_document_generation import (
    _fake_render,
    _layout,
    _request_batch,
    _run_batch,
)
from tests.test_staff import _department, _position, _staff

GENERATION = "/api/v1/documents/generation"
STAFF_SEARCH = f"{GENERATION}/staff"
TEMPLATES = "/api/v1/documents/templates"
ISSUED = "/api/v1/documents/issued"
FIELDS = "/api/v1/documents/fields"


def _fake_render_fixture(monkeypatch):
    monkeypatch.setattr("modules.documents.generation.render_layout", _fake_render)
    return _fake_render


async def _experience_template(client, headers) -> dict:
    created = await client.post(
        TEMPLATES,
        headers=headers,
        json={
            "name": "Experience letter",
            "doc_type": "experience_letter",
            "layout": _layout(
                "{{staff.full_name}}",
                "{{staff.position}}",
                "{{staff.start_date}}",
            ),
        },
    )
    assert created.status_code == 201, created.text
    template = created.json()
    published = await client.post(
        f"{TEMPLATES}/{template['id']}/versions/{template['draft_version_id']}/publish",
        headers=headers,
    )
    assert published.status_code == 200, published.text
    template["published_version"] = published.json()
    return template


async def test_staff_fields_and_transcript_starter_are_registered(client, superadmin_headers) -> None:
    fields = await client.get(FIELDS, headers=superadmin_headers)
    assert fields.status_code == 200, fields.text
    by_key = {item["key"]: item for item in fields.json()["items"]}
    assert by_key["staff.full_name"]["module"] == "staff"
    assert by_key["staff.position"]["module"] == "staff"
    assert by_key["staff.start_date"]["kind"] == "date"
    assert "calendar" in by_key["staff.start_date"]["formats"]
    assert by_key["staff.full_name"]["sample"]

    starters = await client.get(f"{TEMPLATES}/starters", headers=superadmin_headers)
    assert starters.status_code == 200, starters.text
    transcript = next(item for item in starters.json()["items"] if item["key"] == "transcript")
    assert transcript["doc_type"] == "transcript"
    # The transcript binds the year snapshot, not a single term's marks.
    tokens = str(transcript["layout"])
    assert "student.marks.year.total" in tokens
    assert "student.marks.term.total" not in tokens


async def test_experience_letter_generates_for_a_staff_member(
    client, app, superadmin_headers, monkeypatch
) -> None:
    _fake_render_fixture(monkeypatch)
    department = await _department(client, superadmin_headers)
    position = await _position(client, superadmin_headers, department["id"])
    staff = await _staff(
        client,
        superadmin_headers,
        number="STF-2026-0001",
        department_id=department["id"],
        position_id=position["id"],
    )
    template = await _experience_template(client, superadmin_headers)

    started = await _request_batch(
        client,
        superadmin_headers,
        template,
        {"type": "staff", "staff_id": staff["id"]},
    )
    assert started["status"] == "queued"
    assert started["count"] == 1

    await _run_batch(app, started["batch_id"])

    issued = await client.get(ISSUED, headers=superadmin_headers)
    assert issued.status_code == 200, issued.text
    assert issued.json()["total"] == 1
    document = issued.json()["items"][0]
    assert document["recipient_type"] == "staff"
    assert document["recipient_id"] == staff["id"]
    assert document["recipient_name"] == "Solomon Tesfaye Gebre"

    detail = await client.get(f"{ISSUED}/{document['id']}", headers=superadmin_headers)
    assert detail.status_code == 200, detail.text
    snapshot = detail.json()["data_snapshot"]
    assert snapshot["staff"]["full_name"] == "Solomon Tesfaye Gebre"
    assert snapshot["staff"]["position"] == "Mathematics Teacher"
    assert snapshot["staff"]["department"] == "Science"
    assert snapshot["staff"]["start_date"] == "2026-09-01"
    assert snapshot["document"]["number"] == document["number"]


async def test_staff_picker_searches_number_and_name(client, superadmin_headers) -> None:
    department = await _department(client, superadmin_headers)
    position = await _position(client, superadmin_headers, department["id"])
    staff = await _staff(
        client,
        superadmin_headers,
        number="STF-2026-0042",
        department_id=department["id"],
        position_id=position["id"],
    )

    by_name = await client.get(STAFF_SEARCH, headers=superadmin_headers, params={"q": "Solomon"})
    assert by_name.status_code == 200, by_name.text
    assert [item["id"] for item in by_name.json()["items"]] == [staff["id"]]
    assert by_name.json()["items"][0]["position_name"] == "Mathematics Teacher"
    assert by_name.json()["items"][0]["department_name"] == "Science"

    by_number = await client.get(STAFF_SEARCH, headers=superadmin_headers, params={"q": "0042"})
    assert [item["id"] for item in by_number.json()["items"]] == [staff["id"]]


async def test_staff_target_rejects_a_missing_staff_member(client, superadmin_headers) -> None:
    template = await _experience_template(client, superadmin_headers)
    missing = "00000000-0000-0000-0000-000000000001"
    response = await client.post(
        GENERATION,
        headers=superadmin_headers,
        json={
            "template_id": template["id"],
            "version_id": template["published_version"]["id"],
            "target": {"type": "staff", "staff_id": missing},
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["message_key"] == "staff.error.not_found"
