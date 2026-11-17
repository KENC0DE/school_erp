"""P1-19: the "Suggest with AI" hook in the translation editor."""

from __future__ import annotations

from core.i18n.actions import register_translation_suggester

from tests.conftest import create_role, create_user, login


async def suggest(client, headers, **overrides):
    payload = {"namespace": "core", "key": "nav.dashboard", "locale": "am", **overrides}
    return await client.post("/api/v1/i18n/editor/suggest", json=payload, headers=headers)


async def test_suggestions_report_a_clear_unconfigured_state(client, superadmin_headers):
    response = await suggest(client, superadmin_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "configured": False,
        "status": "not_configured",
        "message_key": "ai.not_configured",
    }

    entries = await client.get(
        "/api/v1/i18n/editor/entries",
        params={"locale": "am", "namespace": "core", "status": "needs_review"},
        headers=superadmin_headers,
    )
    assert entries.json()["items"] == []
    bundle = await client.get("/api/v1/i18n/am/core")
    assert bundle.json()["messages"]["nav.dashboard"] == "ዳሽቦርድ"


async def test_a_configured_suggester_creates_a_needs_review_draft(
    app, client, superadmin_headers
):
    calls: list[tuple[str, str, str, str]] = []

    async def fake(source: str, namespace: str, key: str, locale: str) -> str:
        calls.append((source, namespace, key, locale))
        return "ዋና ገጽ"

    app.state.settings.ai_provider = "openai"
    app.state.settings.ai_api_key = "test-key"
    register_translation_suggester(fake)
    try:
        response = await suggest(client, superadmin_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["configured"] is True
        assert body["written"] is True
        assert body["status"] == "needs_review"
        assert body["draft"] == "ዋና ገጽ"
        assert calls == [("Dashboard", "core", "nav.dashboard", "am")]

        drafts = await client.get(
            "/api/v1/i18n/editor/entries",
            params={"locale": "am", "namespace": "core", "status": "needs_review"},
            headers=superadmin_headers,
        )
        row = next(item for item in drafts.json()["items"] if item["key"] == "nav.dashboard")
        assert row["value"] == "ዋና ገጽ"
        assert row["layer"] == "school"
        assert row["source_kind"] == "ai"

        bundle = await client.get("/api/v1/i18n/am/core")
        assert bundle.json()["messages"]["nav.dashboard"] == "ዋና ገጽ"

        activity = await client.get(
            "/api/v1/audit/activity",
            params={"entity_type": "translation_entry"},
            headers=superadmin_headers,
        )
        entry = activity.json()["items"][0]
        assert entry["action"] == "i18n.suggest"
        assert entry["after"]["source"] == "ai"
        assert entry["after"]["status"] == "needs_review"
    finally:
        register_translation_suggester(None)
        app.state.settings.ai_provider = "fake"
        app.state.settings.ai_api_key = ""


async def test_a_human_override_is_never_overwritten(app, client, superadmin_headers):
    await client.put(
        "/api/v1/i18n/editor/entries/core/nav.dashboard/am",
        json={"value": "የሰው ትርጉም", "status": "approved"},
        headers=superadmin_headers,
    )

    async def fake(source: str, namespace: str, key: str, locale: str) -> str:
        return "የAI ረቂቅ"

    app.state.settings.ai_provider = "openai"
    app.state.settings.ai_api_key = "test-key"
    register_translation_suggester(fake)
    try:
        response = await suggest(client, superadmin_headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["written"] is False
        assert body["draft"] == "የAI ረቂቅ"
        assert body["current"] == "የሰው ትርጉም"

        bundle = await client.get("/api/v1/i18n/am/core")
        assert bundle.json()["messages"]["nav.dashboard"] == "የሰው ትርጉም"
    finally:
        register_translation_suggester(None)
        app.state.settings.ai_provider = "fake"
        app.state.settings.ai_api_key = ""


async def test_suggest_permissions_and_input_validation(app, client, superadmin_headers):
    await create_role(app, "translator", [("i18n.view", "all")])
    await create_user(app, "translator@demo.school", display_name="Translator", roles=["translator"])
    translator = await login(client, "translator@demo.school")
    assert (await suggest(client, translator)).status_code == 403

    assert (await suggest(client, superadmin_headers, key="not.a.key")).status_code == 200
    # Unconfigured wins over key validation, so the same call still reports the
    # not-configured state instead of leaking key existence.
    assert (await suggest(client, superadmin_headers, locale="en")).status_code == 200

    app.state.settings.ai_provider = "openai"
    app.state.settings.ai_api_key = "test-key"

    async def fake(source: str, namespace: str, key: str, locale: str) -> str:
        return "ዋና ገጽ"

    register_translation_suggester(fake)
    try:
        assert (await suggest(client, superadmin_headers, key="not.a.key")).status_code == 404
        source = await suggest(client, superadmin_headers, locale="en")
        assert source.status_code == 422
        assert source.json()["error"]["message_key"] == "error.i18n.suggest_source"
    finally:
        register_translation_suggester(None)
        app.state.settings.ai_provider = "fake"
        app.state.settings.ai_api_key = ""


async def test_the_action_is_visible_to_managers_only(client, superadmin_headers, limited_headers):
    tools = await client.get("/api/v1/ai/tools", headers=superadmin_headers)
    keys = {tool["key"] for tool in tools.json()["items"]}
    assert "i18n.suggest_translation" in keys

    denied = await client.get("/api/v1/ai/tools", headers=limited_headers)
    assert "i18n.suggest_translation" not in {
        tool["key"] for tool in denied.json()["items"]
    }
