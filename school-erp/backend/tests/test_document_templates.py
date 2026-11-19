"""P5-04: document templates, versions, publish rules and file interchange.

The tests drive the API the canvas will use. They pin the rules generation
depends on: one draft per template, published versions never change, deleting is
soft, and an exported template can be imported elsewhere without losing its
history. Starter layouts are validated against the same schema as hand-authored
ones, and their translation keys must exist in both bundles.
"""

from __future__ import annotations

import json
from pathlib import Path

BASE = "/api/v1/documents/templates"
MODULES = "/api/v1/system/modules"
BUNDLE = Path(__file__).resolve().parents[1] / "modules" / "documents" / "i18n"

STARTER_KEYS = {
    "report_card",
    "transcript",
    "certificate_completion",
    "certificate_appreciation",
    "id_card",
    "admission_letter",
    "receipt",
    "experience_letter",
}


def _layout(text: str = "Hello") -> dict:
    return {
        "version": 1,
        "page": {"size": "A5"},
        "elements": [
            {
                "id": "note",
                "type": "text",
                "rect": {"x_mm": 10, "y_mm": 10, "w_mm": 100, "h_mm": 12},
                "content": text,
                "style": {"font_family": "Inter", "font_size_pt": 11},
            }
        ],
    }


async def _create(client, headers, **body):
    response = await client.post(BASE, json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _versions(client, headers, template_id: str) -> list[dict]:
    response = await client.get(f"{BASE}/{template_id}/versions", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def _enable(client, headers, enabled: bool) -> None:
    response = await client.put(f"{MODULES}/documents", json={"enabled": enabled}, headers=headers)
    assert response.status_code == 200, response.text


# --- starter library --------------------------------------------------------


async def test_starter_library_offers_validated_translated_layouts(client, superadmin_headers) -> None:
    response = await client.get(f"{BASE}/starters", headers=superadmin_headers)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert {item["key"] for item in items} == STARTER_KEYS

    english = json.loads((BUNDLE / "en.json").read_text(encoding="utf-8"))
    amharic = json.loads((BUNDLE / "am.json").read_text(encoding="utf-8"))
    for item in items:
        name_key = item["name_key"].removeprefix("documents.")
        description_key = item["description_key"].removeprefix("documents.")
        assert name_key in english and name_key in amharic
        assert description_key in english and description_key in amharic
        # A library layout is a normal layout: create it once and let the
        # schema decide, rather than a second validation path in the library.
        created = await _create(
            client,
            superadmin_headers,
            name=english[name_key],
            starter=item["key"],
        )
        assert created["doc_type"] == item["doc_type"]
        assert created["draft_version_number"] == 1
        detail = await client.get(f"{BASE}/{created['id']}", headers=superadmin_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["versions"][0]["status"] == "draft"


async def test_creating_without_a_layout_starts_a_blank_a4_draft(client, superadmin_headers) -> None:
    created = await _create(client, superadmin_headers, name="Blank design")
    assert created["doc_type"] == "custom"
    assert created["current_version_number"] is None
    assert created["draft_version_number"] == 1
    assert created["version_count"] == 1
    version = (
        await client.get(
            f"{BASE}/{created['id']}/versions/{created['draft_version_id']}",
            headers=superadmin_headers,
        )
    ).json()
    assert version["status"] == "draft"
    assert version["layout"]["page"]["size"] == "A4"
    assert version["layout"]["elements"] == []


async def test_layout_errors_are_reported_against_the_schema(client, superadmin_headers) -> None:
    broken = _layout()
    broken["elements"][0]["type"] = "hologram"
    response = await client.post(
        BASE,
        json={"name": "Broken", "layout": broken},
        headers=superadmin_headers,
    )
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["message_key"] == "error.documents.layout_invalid"
    assert error["details"]["errors"]

    both = await client.post(
        BASE,
        json={"name": "Both", "starter": "report_card", "layout": _layout()},
        headers=superadmin_headers,
    )
    assert both.status_code == 422, both.text
    assert both.json()["error"]["message_key"] == "error.documents.starter_layout_conflict"


# --- CRUD and optimistic concurrency ---------------------------------------


async def test_template_crud_list_filters_and_soft_delete(client, superadmin_headers) -> None:
    first = await _create(
        client,
        superadmin_headers,
        name="Grade 8 report",
        doc_type="report_card",
        layout=_layout("Grade 8"),
    )
    second = await _create(
        client,
        superadmin_headers,
        name="Library card",
        doc_type="id_card",
        layout=_layout("Library"),
    )

    listed = await client.get(BASE, headers=superadmin_headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 2
    assert {item["id"] for item in listed.json()["items"]} == {first["id"], second["id"]}

    filtered = await client.get(BASE, params={"doc_type": "id_card"}, headers=superadmin_headers)
    assert [item["id"] for item in filtered.json()["items"]] == [second["id"]]

    searched = await client.get(BASE, params={"q": "grade 8"}, headers=superadmin_headers)
    assert [item["id"] for item in searched.json()["items"]] == [first["id"]]

    updated = await client.patch(
        f"{BASE}/{first['id']}",
        json={"name": "Grade 8 report card", "row_version": first["row_version"]},
        headers=superadmin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Grade 8 report card"
    assert updated.json()["row_version"] == first["row_version"] + 1

    stale = await client.patch(
        f"{BASE}/{first['id']}",
        json={"name": "Stale write", "row_version": first["row_version"]},
        headers=superadmin_headers,
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["error"]["code"] == "CONFLICT"
    assert stale.json()["error"]["details"]["current"] == first["row_version"] + 1

    deleted = await client.delete(f"{BASE}/{first['id']}", headers=superadmin_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert deleted.json()["versions_deleted"] == 1

    assert (await client.get(f"{BASE}/{first['id']}", headers=superadmin_headers)).status_code == 404
    # The key may be reused: the partial index ignores deleted rows.
    replacement = await _create(
        client,
        superadmin_headers,
        name="Replacement",
        key=first["key"],
        layout=_layout(),
    )
    assert replacement["key"] == first["key"]


async def test_a_template_key_must_be_unique(client, superadmin_headers) -> None:
    created = await _create(client, superadmin_headers, name="Original")
    clash = await client.post(
        BASE,
        json={"name": "Clash", "key": created["key"]},
        headers=superadmin_headers,
    )
    assert clash.status_code == 422, clash.text
    assert clash.json()["error"]["message_key"] == "error.documents.template_key_taken"


# --- draft and publish lifecycle -------------------------------------------


async def test_publish_freezes_the_version_and_allows_one_draft(client, superadmin_headers) -> None:
    created = await _create(client, superadmin_headers, name="Certificate", layout=_layout("First"))
    first_id = created["draft_version_id"]

    published = await client.post(
        f"{BASE}/{created['id']}/versions/{first_id}/publish", headers=superadmin_headers
    )
    assert published.status_code == 200, published.text
    body = published.json()
    assert body["status"] == "published"
    assert body["published_at"]
    assert body["layout"]["elements"][0]["content"] == "First"

    detail = (await client.get(f"{BASE}/{created['id']}", headers=superadmin_headers)).json()
    assert detail["current_version_number"] == 1
    assert detail["draft_version_number"] is None

    frozen = await client.patch(
        f"{BASE}/{created['id']}/versions/{first_id}",
        json={"layout": _layout("Rewritten"), "row_version": body["row_version"]},
        headers=superadmin_headers,
    )
    assert frozen.status_code == 409, frozen.text
    assert frozen.json()["error"]["message_key"] == "error.documents.version_not_draft"

    second = await client.post(f"{BASE}/{created['id']}/versions", headers=superadmin_headers)
    assert second.status_code == 201, second.text
    draft = second.json()
    assert draft["version_number"] == 2
    assert draft["status"] == "draft"
    # A new draft starts from the published layout, not an empty page.
    assert draft["layout"]["elements"][0]["content"] == "First"

    competing = await client.post(f"{BASE}/{created['id']}/versions", headers=superadmin_headers)
    assert competing.status_code == 409, competing.text
    assert competing.json()["error"]["message_key"] == "error.documents.draft_exists"
    assert competing.json()["error"]["details"]["draft_version_number"] == 2

    saved = await client.patch(
        f"{BASE}/{created['id']}/versions/{draft['id']}",
        json={
            "layout": _layout("Second"),
            "change_note": "Fixed the title",
            "row_version": draft["row_version"],
        },
        headers=superadmin_headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["layout"]["elements"][0]["content"] == "Second"
    assert saved.json()["change_note"] == "Fixed the title"
    assert saved.json()["row_version"] == draft["row_version"] + 1

    stale = await client.patch(
        f"{BASE}/{created['id']}/versions/{draft['id']}",
        json={"layout": _layout("Stale"), "row_version": draft["row_version"]},
        headers=superadmin_headers,
    )
    assert stale.status_code == 409, stale.text

    invalid = await client.patch(
        f"{BASE}/{created['id']}/versions/{draft['id']}",
        json={"layout": {"version": 1}, "row_version": saved.json()["row_version"]},
        headers=superadmin_headers,
    )
    assert invalid.status_code == 422, invalid.text
    assert invalid.json()["error"]["message_key"] == "error.documents.layout_invalid"

    republished = await client.post(
        f"{BASE}/{created['id']}/versions/{draft['id']}/publish",
        headers=superadmin_headers,
    )
    assert republished.status_code == 200, republished.text
    detail = (await client.get(f"{BASE}/{created['id']}", headers=superadmin_headers)).json()
    assert detail["current_version_number"] == 2
    assert {item["version_number"] for item in detail["versions"]} == {1, 2}
    assert detail["draft_version_number"] is None


async def test_a_version_cannot_be_read_through_another_template(client, superadmin_headers) -> None:
    one = await _create(client, superadmin_headers, name="One", layout=_layout())
    two = await _create(client, superadmin_headers, name="Two", layout=_layout())
    response = await client.get(
        f"{BASE}/{one['id']}/versions/{two['draft_version_id']}",
        headers=superadmin_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["message_key"] == "error.documents.version_not_found"


# --- duplicate, export and import ------------------------------------------


async def test_duplicate_copies_the_current_published_layout(client, superadmin_headers) -> None:
    source = await _create(client, superadmin_headers, name="Source", layout=_layout("Published"))
    await client.post(
        f"{BASE}/{source['id']}/versions/{source['draft_version_id']}/publish",
        headers=superadmin_headers,
    )

    copy = await client.post(
        f"{BASE}/{source['id']}/duplicate",
        json={"name": "Source copy"},
        headers=superadmin_headers,
    )
    assert copy.status_code == 201, copy.text
    body = copy.json()
    assert body["key"] != source["key"]
    assert body["key"].startswith("custom-")
    assert body["doc_type"] == "custom"
    assert body["draft_version_number"] == 1
    version = (
        await client.get(
            f"{BASE}/{body['id']}/versions/{body['draft_version_id']}",
            headers=superadmin_headers,
        )
    ).json()
    assert version["layout"]["elements"][0]["content"] == "Published"

    original = (await client.get(f"{BASE}/{source['id']}", headers=superadmin_headers)).json()
    assert original["name"] == "Source"
    assert original["draft_version_number"] is None


async def test_export_import_round_trip_keeps_every_version(client, superadmin_headers) -> None:
    source = await _create(client, superadmin_headers, name="Travel", layout=_layout("Version one"))
    await client.post(
        f"{BASE}/{source['id']}/versions/{source['draft_version_id']}/publish",
        headers=superadmin_headers,
    )
    draft = (await client.post(f"{BASE}/{source['id']}/versions", headers=superadmin_headers)).json()
    await client.patch(
        f"{BASE}/{source['id']}/versions/{draft['id']}",
        json={"layout": _layout("Version two"), "row_version": draft["row_version"]},
        headers=superadmin_headers,
    )

    exported = await client.get(f"{BASE}/{source['id']}/export", headers=superadmin_headers)
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-disposition"] == (f'attachment; filename="{source["key"]}.json"')
    payload = exported.json()
    assert payload["format"] == "school-erp.doc-template"
    assert payload["format_version"] == 1
    assert payload["template"]["key"] == source["key"]
    assert [item["status"] for item in payload["versions"]] == ["published", "draft"]

    imported = await client.post(f"{BASE}/import", json=payload, headers=superadmin_headers)
    assert imported.status_code == 201, imported.text
    body = imported.json()
    assert body["id"] != source["id"]
    assert body["key"] != source["key"]  # the source key is still in use
    assert body["current_version_number"] == 1
    assert body["draft_version_number"] == 2
    assert body["version_count"] == 2

    versions = await _versions(client, superadmin_headers, body["id"])
    assert [item["status"] for item in versions] == ["published", "draft"]
    first = (
        await client.get(f"{BASE}/{body['id']}/versions/{versions[0]['id']}", headers=superadmin_headers)
    ).json()
    assert first["layout"]["elements"][0]["content"] == "Version one"


async def test_import_rejects_files_that_break_the_lifecycle(client, superadmin_headers) -> None:
    source = await _create(client, superadmin_headers, name="Source", layout=_layout())
    payload = (await client.get(f"{BASE}/{source['id']}/export", headers=superadmin_headers)).json()

    two_drafts = json.loads(json.dumps(payload))
    two_drafts["versions"].append({**two_drafts["versions"][0], "version_number": 2})
    rejected = await client.post(f"{BASE}/import", json=two_drafts, headers=superadmin_headers)
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["error"]["message_key"] == "error.documents.import_invalid"

    broken = json.loads(json.dumps(payload))
    broken["versions"][0]["layout"]["page"]["size"] = "Poster"
    rejected = await client.post(f"{BASE}/import", json=broken, headers=superadmin_headers)
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["error"]["message_key"] == "error.documents.layout_invalid"

    wrong_format = json.loads(json.dumps(payload))
    wrong_format["format"] = "something-else"
    rejected = await client.post(f"{BASE}/import", json=wrong_format, headers=superadmin_headers)
    assert rejected.status_code == 422, rejected.text


# --- permissions, module gate and audit ------------------------------------


async def test_template_routes_need_design_permission_and_the_module(
    client, superadmin_headers, limited_headers
) -> None:
    denied = await client.get(BASE, headers=limited_headers)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

    anonymous = await client.get(BASE)
    assert anonymous.status_code == 401

    await _enable(client, superadmin_headers, False)
    blocked = await client.get(BASE, headers=superadmin_headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "MODULE_DISABLED"
    await _enable(client, superadmin_headers, True)


async def test_every_mutation_writes_an_audit_entry(client, superadmin_headers) -> None:
    created = await _create(client, superadmin_headers, name="Audited", layout=_layout("Audited"))
    await client.patch(
        f"{BASE}/{created['id']}",
        json={"description": "A description", "row_version": created["row_version"]},
        headers=superadmin_headers,
    )
    published = await client.post(
        f"{BASE}/{created['id']}/versions/{created['draft_version_id']}/publish",
        headers=superadmin_headers,
    )
    second = (await client.post(f"{BASE}/{created['id']}/versions", headers=superadmin_headers)).json()
    await client.patch(
        f"{BASE}/{created['id']}/versions/{second['id']}",
        json={"layout": _layout("Audited again"), "row_version": second["row_version"]},
        headers=superadmin_headers,
    )
    await client.post(
        f"{BASE}/{created['id']}/duplicate",
        json={"name": "Audited copy"},
        headers=superadmin_headers,
    )
    exported = (await client.get(f"{BASE}/{created['id']}/export", headers=superadmin_headers)).json()
    await client.post(f"{BASE}/import", json=exported, headers=superadmin_headers)
    await client.delete(f"{BASE}/{created['id']}", headers=superadmin_headers)

    activity = await client.get(
        "/api/v1/audit/activity",
        params={"module": "documents", "limit": 200},
        headers=superadmin_headers,
    )
    assert activity.status_code == 200, activity.text
    actions = {item["action"] for item in activity.json()["items"]}
    assert {
        "document.template.create",
        "document.template.update",
        "document.template.delete",
        "document.template.duplicate",
        "document.template.import",
        "document.template.version.create",
        "document.template.version.save",
        "document.template.version.publish",
    } <= actions
    # Layouts are summarised by digest, not copied wholesale into the chain.
    save_entry = next(
        item for item in activity.json()["items"] if item["action"] == "document.template.version.save"
    )
    assert save_entry["after"]["layout_digest"]
    assert "layout" not in (save_entry["after"] or {})
    assert published.status_code == 200
