"""P1-18: translation editor, layers, import/export and live bundles."""

from __future__ import annotations

import json

from sqlalchemy import text

from tests.conftest import create_role, create_user, login


async def entries(client, headers, **params):
    response = await client.get(
        "/api/v1/i18n/editor/entries", params={"limit": 500, **params}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_editor_lists_english_source_and_target_with_filters(client, superadmin_headers):
    listing = await entries(client, superadmin_headers, locale="am", namespace="core")
    assert listing["total"] > 100
    dashboard = next(item for item in listing["items"] if item["key"] == "nav.dashboard")
    assert dashboard["source"] == "Dashboard"
    assert dashboard["value"] == "ዳሽቦርድ"
    assert dashboard["layer"] == "default"
    assert dashboard["status"] == "approved"
    assert dashboard["source_kind"] == "human"

    search = await entries(client, superadmin_headers, locale="am", namespace="core", q="dashboard")
    assert "nav.dashboard" in [item["key"] for item in search["items"]]

    missing = await entries(client, superadmin_headers, locale="am", namespace="core", status="missing")
    assert all(item["value"] == "" and item["status"] == "missing" for item in missing["items"])

    school = await entries(client, superadmin_headers, locale="am", namespace="core", layer="school")
    assert school["items"] == []

    stats = await client.get(
        "/api/v1/i18n/editor/stats",
        params={"locale": "am", "namespace": "core"},
        headers=superadmin_headers,
    )
    assert stats.status_code == 200
    assert stats.json()["total"] == listing["total"]
    assert stats.json()["missing"] == missing["total"]
    assert stats.json()["overrides"] == 0

    namespaces = await client.get("/api/v1/i18n/editor/namespaces", headers=superadmin_headers)
    assert set(namespaces.json()["items"]) >= {"core", "sample"}


async def test_edit_changes_the_live_bundle_without_redeploy(client, superadmin_headers):
    before_bundle = await client.get("/api/v1/i18n/am/core")
    old_etag = before_bundle.headers["etag"]
    assert before_bundle.json()["messages"]["nav.dashboard"] == "ዳሽቦርድ"

    updated = await client.put(
        "/api/v1/i18n/editor/entries/core/nav.dashboard/am",
        json={"value": "ዋና ገጽ", "status": "approved"},
        headers=superadmin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["value"] == "ዋና ገጽ"
    assert updated.json()["layer"] == "school"

    after_bundle = await client.get("/api/v1/i18n/am/core")
    assert after_bundle.json()["messages"]["nav.dashboard"] == "ዋና ገጽ"
    assert after_bundle.headers["etag"] != old_etag

    overrides = await entries(client, superadmin_headers, locale="am", namespace="core", layer="school")
    assert [item["key"] for item in overrides["items"]] == ["nav.dashboard"]

    activity = await client.get(
        "/api/v1/audit/activity",
        params={"entity_type": "translation_entry"},
        headers=superadmin_headers,
    )
    create_entry = activity.json()["items"][0]
    assert create_entry["action"] == "i18n.create"
    assert create_entry["before"] is None
    assert create_entry["after"]["value"] == "ዋና ገጽ"
    assert create_entry["after"]["layer"] == "school"

    second = await client.put(
        "/api/v1/i18n/editor/entries/core/nav.dashboard/am",
        json={"value": "መጀመሪያ ገጽ"},
        headers=superadmin_headers,
    )
    assert second.status_code == 200
    activity = await client.get(
        "/api/v1/audit/activity",
        params={"entity_type": "translation_entry"},
        headers=superadmin_headers,
    )
    update_entry = activity.json()["items"][0]
    assert update_entry["action"] == "i18n.update"
    assert update_entry["before"]["value"] == "ዋና ገጽ"
    assert update_entry["after"]["value"] == "መጀመሪያ ገጽ"

    reset = await client.post(
        "/api/v1/i18n/editor/entries/core/nav.dashboard/am/reset",
        headers=superadmin_headers,
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["value"] == "ዳሽቦርድ"
    bundle = await client.get("/api/v1/i18n/am/core")
    assert bundle.json()["messages"]["nav.dashboard"] == "ዳሽቦርድ"

    activity = await client.get(
        "/api/v1/audit/activity",
        params={"entity_type": "translation_entry"},
        headers=superadmin_headers,
    )
    assert activity.json()["items"][0]["action"] == "i18n.reset"

    missing_override = await client.post(
        "/api/v1/i18n/editor/entries/core/common.cancel/am/reset",
        headers=superadmin_headers,
    )
    assert missing_override.status_code == 404


async def test_school_layer_wins_over_central_and_reset_keeps_central(app, client, superadmin_headers):
    async with app.state.db.session() as session:
        await session.execute(
            text(
                "INSERT INTO translation_entries (id, namespace, key, locale, value, status, source, layer, row_version, created_at, updated_at) "
                "VALUES ('22222222-2222-2222-2222-222222222222', 'core', 'nav.dashboard', 'am', "
                "'የመቆጣጠሪያ ገጽ', 'approved', 'human', 'central', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        await session.commit()

    central = await client.get("/api/v1/i18n/am/core")
    assert central.json()["messages"]["nav.dashboard"] == "የመቆጣጠሪያ ገጽ"

    await client.put(
        "/api/v1/i18n/editor/entries/core/nav.dashboard/am",
        json={"value": "የትምህርት ቤቴ ገጽ"},
        headers=superadmin_headers,
    )
    school = await client.get("/api/v1/i18n/am/core")
    assert school.json()["messages"]["nav.dashboard"] == "የትምህርት ቤቴ ገጽ"

    reset = await client.post(
        "/api/v1/i18n/editor/entries/core/nav.dashboard/am/reset",
        headers=superadmin_headers,
    )
    assert reset.status_code == 200
    assert reset.json()["value"] == "የመቆጣጠሪያ ገጽ"

    central_only = await entries(client, superadmin_headers, locale="am", namespace="core", layer="central")
    assert [item["key"] for item in central_only["items"]] == ["nav.dashboard"]

    # Editing the key again restores the soft-deleted override row.
    again = await client.put(
        "/api/v1/i18n/editor/entries/core/nav.dashboard/am",
        json={"value": "አዲስ ገጽ"},
        headers=superadmin_headers,
    )
    assert again.status_code == 200, again.text
    assert again.json()["layer"] == "school"
    bundle = await client.get("/api/v1/i18n/am/core")
    assert bundle.json()["messages"]["nav.dashboard"] == "አዲስ ገጽ"


async def test_import_and_export_round_trip(client, superadmin_headers):
    imported = await client.post(
        "/api/v1/i18n/editor/import",
        json={
            "namespace": "core",
            "locale": "am",
            "format": "json",
            "content": json.dumps({"common.cancel": "ተወው", "nav.dashboard": "ዋና ገጽ"}),
        },
        headers=superadmin_headers,
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["imported"] == 2

    bundle = await client.get("/api/v1/i18n/am/core")
    assert bundle.json()["messages"]["common.cancel"] == "ተወው"

    csv_content = 'key,value\napp.name,"የእኛ, ትምህርት ቤት"\n'
    csv_import = await client.post(
        "/api/v1/i18n/editor/import",
        json={
            "namespace": "core",
            "locale": "am",
            "format": "csv",
            "content": csv_content,
            "status": "needs_review",
        },
        headers=superadmin_headers,
    )
    assert csv_import.status_code == 200, csv_import.text
    bundle = await client.get("/api/v1/i18n/am/core")
    assert bundle.json()["messages"]["app.name"] == "የእኛ, ትምህርት ቤት"

    review = await entries(client, superadmin_headers, locale="am", namespace="core", status="needs_review")
    assert [item["key"] for item in review["items"]] == ["app.name"]

    activity = await client.get(
        "/api/v1/audit/activity",
        params={"entity_type": "translation_batch"},
        headers=superadmin_headers,
    )
    batch = activity.json()["items"][0]
    assert batch["action"] == "i18n.import"
    assert batch["after"]["count"] == 1
    assert batch["after"]["keys"] == ["app.name"]

    exported_json = await client.get(
        "/api/v1/i18n/editor/export",
        params={"locale": "am", "namespace": "core", "format": "json"},
        headers=superadmin_headers,
    )
    assert exported_json.status_code == 200
    assert "attachment" in exported_json.headers["content-disposition"]
    payload = exported_json.json()
    assert payload["common.cancel"] == "ተወው"
    assert payload["app.name"] == "የእኛ, ትምህርት ቤት"

    exported_csv = await client.get(
        "/api/v1/i18n/editor/export",
        params={"locale": "am", "namespace": "core", "format": "csv"},
        headers=superadmin_headers,
    )
    assert exported_csv.headers["content-type"].startswith("text/csv")
    lines = exported_csv.text.splitlines()
    assert lines[0] == "key,value,source,status,layer"
    assert any(line.startswith("common.cancel,ተወው,") for line in lines)


async def test_import_validation_is_atomic(client, superadmin_headers):
    before = await client.get("/api/v1/i18n/am/core")

    unknown = await client.post(
        "/api/v1/i18n/editor/import",
        json={
            "namespace": "core",
            "locale": "am",
            "format": "json",
            "content": json.dumps({"common.cancel": "ተወው", "not.a.key": "x"}),
        },
        headers=superadmin_headers,
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["details"]["keys"] == ["not.a.key"]
    after = await client.get("/api/v1/i18n/am/core")
    assert after.json() == before.json()

    dry_run = await client.post(
        "/api/v1/i18n/editor/import",
        json={
            "namespace": "core",
            "locale": "am",
            "format": "json",
            "content": json.dumps({"common.cancel": "ተወው"}),
            "dry_run": True,
        },
        headers=superadmin_headers,
    )
    assert dry_run.status_code == 200
    assert dry_run.json()["would_import"] == 1
    after = await client.get("/api/v1/i18n/am/core")
    assert after.json()["messages"]["common.cancel"] == "ሰርዝ"

    for content, fmt in (
        ("{not json", "json"),
        ('["a"]', "json"),
        ("value\nx", "csv"),
        ("", "json"),
    ):
        response = await client.post(
            "/api/v1/i18n/editor/import",
            json={
                "namespace": "core",
                "locale": "am",
                "format": fmt,
                "content": content,
            },
            headers=superadmin_headers,
        )
        assert response.status_code == 422, (content, response.text)


async def test_editor_permissions(app, client, limited_headers):
    denied = await client.get("/api/v1/i18n/editor/entries", params={"locale": "am"}, headers=limited_headers)
    assert denied.status_code == 403

    await create_role(app, "translator", [("i18n.view", "all")])
    await create_user(app, "translator@demo.school", display_name="Translator", roles=["translator"])
    translator = await login(client, "translator@demo.school")

    readable = await client.get("/api/v1/i18n/editor/entries", params={"locale": "am"}, headers=translator)
    assert readable.status_code == 200

    write_denied = await client.put(
        "/api/v1/i18n/editor/entries/core/nav.dashboard/am",
        json={"value": "ዋና ገጽ"},
        headers=translator,
    )
    assert write_denied.status_code == 403
