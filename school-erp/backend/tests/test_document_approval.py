"""P5-10: optional approval before a certificate is issued.

The school enables certificate approval in settings. A matching batch is then
recorded but not handed to the worker, so nothing is numbered or printed until
somebody with ``documents.approve`` releases it. Rejection is a terminal,
audited outcome; the batch can never be generated afterwards.

The tests also pin the permission split: a designer cannot generate, a generator
cannot approve and an approver cannot design or generate.
"""

from __future__ import annotations

import pytest
from app.errors import Conflict

from tests.conftest import create_role, create_user, login, unique_email
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

GENERATION = "/api/v1/documents/generation"
APPROVALS = f"{GENERATION}/approvals"
TEMPLATES = "/api/v1/documents/templates"
ISSUED = "/api/v1/documents/issued"
SETTINGS = "/api/v1/settings"
AUDIT = "/api/v1/audit/activity"


@pytest.fixture
def fake_render(monkeypatch):
    """Replace the heavy renderer with a tiny valid PDF."""
    monkeypatch.setattr("modules.documents.generation.render_layout", _fake_render)
    return _fake_render


async def _set_approval(client, headers, enabled: bool) -> None:
    response = await client.put(
        f"{SETTINGS}/documents/require_certificate_approval",
        headers=headers,
        json={"value": enabled},
    )
    assert response.status_code == 200, response.text


async def _certificate_setup(client, headers, *, number: str = "APR-0001") -> dict:
    year = await _year(client, headers)
    level = await _level(client, headers)
    section = await _section(client, headers, year, level)
    student = await _student(client, headers, year, level, section, number=number)
    template = await _published_template(
        client,
        headers,
        _layout("{{student.full_name}}", "{{document.number}}"),
    )
    return {"year": year, "level": level, "section": section, "student": student, "template": template}


async def _request(client, headers, setup: dict) -> dict:
    return await _request_batch(
        client,
        headers,
        setup["template"],
        {"type": "student", "student_id": setup["student"]["id"]},
    )


async def _actions(client, headers) -> set[str]:
    response = await client.get(AUDIT, headers=headers, params={"module": "documents", "limit": 200})
    assert response.status_code == 200, response.text
    return {item["action"] for item in response.json()["items"]}


async def test_certificate_batch_waits_for_approval_then_issues(
    client, app, superadmin_headers, fake_render
) -> None:
    await _set_approval(client, superadmin_headers, True)
    setup = await _certificate_setup(client, superadmin_headers)

    started = await _request(client, superadmin_headers, setup)
    assert started["status"] == "pending_approval"
    assert started["count"] == 1

    pending = await client.get(APPROVALS, headers=superadmin_headers)
    assert pending.status_code == 200, pending.text
    items = pending.json()["items"]
    assert [item["id"] for item in items] == [started["batch_id"]]
    assert items[0]["approval_required"] is True
    assert items[0]["status"] == "pending_approval"
    assert items[0]["requested_by"] == "Super Admin"

    # The worker refuses to run before approval, so a stray enqueue cannot
    # number a document that nobody has released.
    with pytest.raises(Conflict):
        await _run_batch(app, started["batch_id"])
    assert (await client.get(ISSUED, headers=superadmin_headers)).json()["total"] == 0

    approved = await client.post(
        f"{GENERATION}/batches/{started['batch_id']}/approve",
        headers=superadmin_headers,
        json={"note": "Checked the class list"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "queued"
    assert approved.json()["approved_at"]
    assert (await client.get(APPROVALS, headers=superadmin_headers)).json()["items"] == []

    again = await client.post(
        f"{GENERATION}/batches/{started['batch_id']}/approve",
        headers=superadmin_headers,
        json={},
    )
    assert again.status_code == 409
    assert again.json()["error"]["message_key"] == "error.documents.batch_not_pending"

    await _run_batch(app, started["batch_id"])
    issued = await client.get(ISSUED, headers=superadmin_headers)
    assert issued.json()["total"] == 1
    assert issued.json()["items"][0]["number"] == "DOC-2026-00001"

    actions = await _actions(client, superadmin_headers)
    assert {"documents.batch.approve", "documents.issue"} <= actions


async def test_rejection_is_terminal_and_issues_nothing(client, app, superadmin_headers, fake_render) -> None:
    await _set_approval(client, superadmin_headers, True)
    setup = await _certificate_setup(client, superadmin_headers, number="APR-0002")
    started = await _request(client, superadmin_headers, setup)

    rejected = await client.post(
        f"{GENERATION}/batches/{started['batch_id']}/reject",
        headers=superadmin_headers,
        json={"reason": "The wrong class list was chosen"},
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "The wrong class list was chosen"

    assert (await client.get(APPROVALS, headers=superadmin_headers)).json()["items"] == []
    with pytest.raises(Conflict):
        await _run_batch(app, started["batch_id"])
    assert (await client.get(ISSUED, headers=superadmin_headers)).json()["total"] == 0

    actions = await _actions(client, superadmin_headers)
    assert "documents.batch.reject" in actions
    assert "documents.issue" not in actions

    # A rejected batch cannot be approved afterwards either.
    late = await client.post(
        f"{GENERATION}/batches/{started['batch_id']}/approve",
        headers=superadmin_headers,
        json={},
    )
    assert late.status_code == 409


async def test_approval_is_optional_and_only_holds_certificates(
    client, superadmin_headers, fake_render
) -> None:
    setup = await _certificate_setup(client, superadmin_headers, number="APR-0003")

    # Default policy: certificates are queued immediately.
    immediate = await _request(client, superadmin_headers, setup)
    assert immediate["status"] == "queued"

    # A non-certificate template is never held, even with the policy on.
    await _set_approval(client, superadmin_headers, True)
    created = await client.post(
        TEMPLATES,
        headers=superadmin_headers,
        json={
            "name": "Library card",
            "doc_type": "custom",
            "layout": _layout("{{student.full_name}}"),
        },
    )
    assert created.status_code == 201, created.text
    template = created.json()
    published = await client.post(
        f"{TEMPLATES}/{template['id']}/versions/{template['draft_version_id']}/publish",
        headers=superadmin_headers,
    )
    assert published.status_code == 200, published.text
    template["published_version"] = published.json()

    custom = await _request_batch(
        client,
        superadmin_headers,
        template,
        {"type": "student", "student_id": setup["student"]["id"]},
    )
    assert custom["status"] == "queued"


async def test_approval_permission_is_separate_from_design_and_generate(
    client, app, superadmin_headers, fake_render
) -> None:
    await _set_approval(client, superadmin_headers, True)
    setup = await _certificate_setup(client, superadmin_headers, number="APR-0004")
    started = await _request(client, superadmin_headers, setup)

    await create_role(app, "document_generator", [("documents.generate", "all")])
    generator_email = unique_email("generator")
    await create_user(app, generator_email, roles=["document_generator"])
    generator = await login(client, generator_email)
    assert (await client.get(APPROVALS, headers=generator)).status_code == 403
    denied_approve = await client.post(
        f"{GENERATION}/batches/{started['batch_id']}/approve",
        headers=generator,
        json={},
    )
    assert denied_approve.status_code == 403

    await create_role(app, "document_approver", [("documents.approve", "all")])
    approver_email = unique_email("approver")
    await create_user(app, approver_email, display_name="Approver", roles=["document_approver"])
    approver = await login(client, approver_email)
    assert (await client.get(APPROVALS, headers=approver)).status_code == 200
    assert (await client.get(TEMPLATES, headers=approver)).status_code == 403
    denied_generate = await client.post(
        GENERATION,
        headers=approver,
        json={
            "template_id": setup["template"]["id"],
            "target": {"type": "student", "student_id": setup["student"]["id"]},
        },
    )
    assert denied_generate.status_code == 403

    released = await client.post(
        f"{GENERATION}/batches/{started['batch_id']}/approve",
        headers=approver,
        json={"note": "Approved by the head teacher"},
    )
    assert released.status_code == 200, released.text

    # The audit names the approver, not the requester.
    entries = await client.get(
        "/api/v1/audit/activity",
        headers=superadmin_headers,
        params={"module": "documents", "action": "documents.batch.approve", "limit": 20},
    )
    assert entries.status_code == 200, entries.text
    entry = entries.json()["items"][0]
    assert entry["actor_name"] == "Approver"
    assert entry["entity_id"] == started["batch_id"]


async def test_approval_setting_is_typed_and_visible(client, superadmin_headers) -> None:
    response = await client.get(SETTINGS, headers=superadmin_headers)
    assert response.status_code == 200, response.text
    documents = next(item for item in response.json()["items"] if item["module"] == "documents")
    field = next(item for item in documents["fields"] if item["key"] == "require_certificate_approval")
    assert field["type"] == "boolean"
    assert field["value"] is False
    assert field["label_key"] == "settings.documents.require_certificate_approval"
