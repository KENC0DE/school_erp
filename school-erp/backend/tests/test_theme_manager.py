"""P1-21: Theme Manager import, validation, preview, scope and user choice."""

from __future__ import annotations

import json

import pytest
from core.themes.models import Theme
from core.themes.tokens import DARK, DEFAULT_THEME, LIGHT
from sqlalchemy import select


def css_from(light: dict, dark: dict) -> str:
    def block(tokens: dict) -> str:
        return "\n".join(f"  --{key}: {value};" for key, value in tokens.items())

    return f":root {{\n{block(light)}\n}}\n.dark {{\n{block(dark)}\n}}\n"


def ocean_tokens() -> dict:
    light = dict(LIGHT)
    dark = dict(DARK)
    light["background"] = "oklch(0.98 0.02 220)"
    light["foreground"] = "oklch(0.18 0.03 220)"
    light["primary"] = "oklch(0.5 0.12 220)"
    light["primary-foreground"] = "oklch(0.99 0 0)"
    dark["background"] = "oklch(0.16 0.03 220)"
    dark["foreground"] = "oklch(0.94 0.02 220)"
    return {"light": light, "dark": dark}


def json_import(name: str = "Ocean", tokens: dict | None = None) -> dict:
    return {
        "format": "json",
        "content": json.dumps({"name": name, "tokens": tokens or ocean_tokens()}),
    }


async def test_the_default_theme_is_valid_and_has_readable_pairs(client):
    response = await client.get("/api/v1/themes/active")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["key"] == "default"
    assert body["source"] in {"builtin", "instance"}
    assert body["fallback"] is False
    for mode in ("light", "dark"):
        assert body["tokens"][mode]["chart-1"]
        assert body["tokens"][mode]["sidebar"]
    assert (await client.get("/api/v1/themes/active")).json()["tokens"] == DEFAULT_THEME["tokens"]


async def test_import_css_and_json_and_generate_both_clients(client, superadmin_headers):
    css = css_from(ocean_tokens()["light"], ocean_tokens()["dark"])
    imported = await client.post(
        "/api/v1/themes/import",
        json={"format": "css", "content": css, "name": "Ocean CSS", "key": "ocean-css"},
        headers=superadmin_headers,
    )
    assert imported.status_code == 201, imported.text
    theme = imported.json()
    assert theme["key"] == "ocean-css"
    assert theme["name"] == "Ocean CSS"
    assert theme["valid"] is True
    assert theme["tokens"]["light"]["background"] == ocean_tokens()["light"]["background"]
    assert "--background: oklch(0.98 0.02 220);" in theme["css"]["light"]
    assert theme["mobile"]["light"]["colors"]["background"].startswith("#")
    assert theme["mobile"]["dark"]["fonts"]["ethiopic"]
    assert theme["issues"] == []

    registry_item = {
        "name": "Lagoon",
        "type": "registry:theme",
        "cssVars": {
            "theme": {"radius": "0.75rem"},
            "light": {f"--{key}": value for key, value in ocean_tokens()["light"].items() if key != "radius"},
            "dark": {f"--{key}": value for key, value in ocean_tokens()["dark"].items() if key != "radius"},
        },
    }
    uploaded = await client.post(
        "/api/v1/themes/import",
        json={"format": "json", "content": json.dumps(registry_item)},
        headers=superadmin_headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["key"] == "lagoon"
    assert uploaded.json()["tokens"]["light"]["radius"] == "0.75rem"

    listed = await client.get("/api/v1/themes")
    keys = {item["key"] for item in listed.json()["items"]}
    assert {"default", "ocean-css", "lagoon"} <= keys


async def test_an_unreadable_pair_is_rejected_with_a_clear_reason(client, superadmin_headers):
    tokens = ocean_tokens()
    tokens["light"]["foreground"] = tokens["light"]["background"]
    response = await client.post(
        "/api/v1/themes/import",
        json=json_import("Unreadable", tokens),
        headers=superadmin_headers,
    )
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["message_key"] == "error.theme.invalid"
    issues = error["details"]["issues"]
    contrast = next(issue for issue in issues if issue["code"] == "contrast")
    assert contrast["mode"] == "light"
    assert contrast["minimum"] == 4.5
    assert contrast["ratio"] < 4.5
    assert "contrast ratio" in contrast["message"]
    assert "must be at least 4.5:1" in contrast["message"]

    # Nothing was saved and the shipped theme still serves.
    listed = await client.get("/api/v1/themes")
    assert "unreadable" not in {item["key"] for item in listed.json()["items"]}
    assert (await client.get("/api/v1/themes/active")).json()["key"] == "default"


async def test_missing_modes_and_tokens_are_rejected(client, superadmin_headers):
    partial = css_from(ocean_tokens()["light"], {})
    response = await client.post(
        "/api/v1/themes/import",
        json={"format": "css", "content": partial, "key": "partial"},
        headers=superadmin_headers,
    )
    assert response.status_code == 422
    codes = {issue["code"] for issue in response.json()["error"]["details"]["issues"]}
    assert "missing_mode" in codes

    missing = ocean_tokens()
    del missing["dark"]["chart-3"]
    response = await client.post(
        "/api/v1/themes/import",
        json=json_import("Missing chart", missing),
        headers=superadmin_headers,
    )
    assert response.status_code == 422
    issues = response.json()["error"]["details"]["issues"]
    assert any(issue["code"] == "missing_token" and issue["token"] == "chart-3" for issue in issues)


async def test_preview_is_side_effect_free_and_shows_the_fallback(client, superadmin_headers):
    tokens = ocean_tokens()
    tokens["dark"]["foreground"] = tokens["dark"]["background"]
    preview = await client.post(
        "/api/v1/themes/preview",
        json=json_import("Broken preview", tokens),
        headers=superadmin_headers,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["valid"] is False
    assert body["fallback"]["key"] == "default"
    assert body["fallback"]["fallback"] is True
    assert any(issue["code"] == "contrast" for issue in body["issues"])
    assert body["tokens"]["dark"]["foreground"] == tokens["dark"]["foreground"]

    listed = await client.get("/api/v1/themes")
    assert "broken-preview" not in {item["key"] for item in listed.json()["items"]}

    good = await client.post(
        "/api/v1/themes/preview",
        json=json_import("Nice preview"),
        headers=superadmin_headers,
    )
    assert good.status_code == 200
    assert good.json()["valid"] is True
    assert good.json()["fallback"] is None
    assert good.json()["mobile"]["light"]["colors"]["primary"].startswith("#")


async def test_a_broken_stored_theme_falls_back_to_default(app, client):
    async with app.state.db.session() as session:
        row = (await session.execute(select(Theme).where(Theme.key == "default"))).scalar_one()
        broken = {"light": dict(LIGHT), "dark": dict(DARK)}
        broken["light"]["foreground"] = broken["light"]["background"]
        row.tokens = broken
        row.is_default = True
        row.is_active = True
        await session.commit()

    response = await client.get("/api/v1/themes/active")
    assert response.status_code == 200
    body = response.json()
    assert body["key"] == "default"
    assert body["source"] == "builtin"
    assert body["fallback"] is True
    assert body["tokens"] == DEFAULT_THEME["tokens"]
    assert any(reason["code"] == "contrast" for reason in body["reason"])

    mobile = await client.get("/api/v1/themes/active/mobile?mode=dark")
    assert mobile.status_code == 200
    assert mobile.json()["fallback"] is True
    assert mobile.json()["theme"]["colors"]["background"].startswith("#")


async def test_registry_urls_are_imported_and_local_urls_are_blocked(client, superadmin_headers, monkeypatch):
    from core.themes import importers

    real_registry = importers.fetch_registry

    async def fake_registry(url: str, *, client=None) -> str:
        if "example.com" in url:
            return json.dumps({"name": "Registry Ocean", "tokens": ocean_tokens()})
        return await real_registry(url, client=client)

    monkeypatch.setattr("core.themes.importers.fetch_registry", fake_registry)
    response = await client.post(
        "/api/v1/themes/preview",
        json={"format": "registry", "content": "https://themes.example.com/ocean.json"},
        headers=superadmin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["valid"] is True
    assert response.json()["source"] == "registry"

    blocked = await client.post(
        "/api/v1/themes/import",
        json={"format": "registry", "content": "http://localhost:9000/theme.json"},
        headers=superadmin_headers,
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["message_key"] == "error.theme.invalid_registry_url"


async def test_school_scope_default_and_per_user_choice(client, superadmin_headers, limited_headers):
    imported = await client.post(
        "/api/v1/themes/import",
        json=json_import("Ocean"),
        headers=superadmin_headers,
    )
    assert imported.status_code == 201, imported.text
    theme = imported.json()
    assert theme["is_active"] is True
    assert theme["is_default"] is False

    available = await client.get("/api/v1/themes/available", headers=limited_headers)
    assert available.status_code == 200
    assert {item["key"] for item in available.json()["items"]} == {"default", "ocean"}

    chosen = await client.put(
        "/api/v1/themes/preference",
        json={"theme_key": "ocean", "mode": "dark"},
        headers=limited_headers,
    )
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["theme_key"] == "ocean"
    assert chosen.json()["theme"]["source"] == "user"
    assert chosen.json()["theme"]["mode"] == "dark"

    with_auth = await client.get("/api/v1/themes/active", headers=limited_headers)
    assert with_auth.json()["key"] == "ocean"
    assert with_auth.json()["source"] == "user"
    anonymous = await client.get("/api/v1/themes/active")
    assert anonymous.json()["key"] == "default"

    mobile = await client.get("/api/v1/themes/active/mobile?mode=dark", headers=limited_headers)
    assert mobile.json()["key"] == "ocean"
    assert mobile.json()["theme"]["mode"] == "dark"

    missing = await client.put(
        "/api/v1/themes/preference",
        json={"theme_key": "nope", "mode": "light"},
        headers=limited_headers,
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["message_key"] == "error.theme.not_available"

    reset = await client.put(
        "/api/v1/themes/preference",
        json={"theme_key": None, "mode": "light"},
        headers=limited_headers,
    )
    assert reset.status_code == 200
    assert reset.json()["theme"]["key"] == "default"


async def test_managing_default_availability_and_soft_delete(client, superadmin_headers):
    imported = await client.post(
        "/api/v1/themes/import",
        json=json_import("Ocean"),
        headers=superadmin_headers,
    )
    theme = imported.json()

    made_default = await client.post("/api/v1/themes/ocean/default", headers=superadmin_headers)
    assert made_default.status_code == 200, made_default.text
    assert made_default.json()["is_default"] is True
    assert (await client.get("/api/v1/themes/active")).json()["key"] == "ocean"

    default_row = await client.get("/api/v1/themes/default", headers=superadmin_headers)
    assert default_row.json()["is_default"] is False

    unavailable = await client.patch(
        "/api/v1/themes/ocean",
        json={"row_version": theme["row_version"], "is_active": False},
        headers=superadmin_headers,
    )
    # A default theme cannot be hidden; choose another default first.
    assert unavailable.status_code == 422
    assert unavailable.json()["error"]["message_key"] == "error.theme.default_must_be_available"

    await client.post("/api/v1/themes/default/default", headers=superadmin_headers)
    current = (await client.get("/api/v1/themes/ocean", headers=superadmin_headers)).json()
    hidden = await client.patch(
        "/api/v1/themes/ocean",
        json={"row_version": current["row_version"], "is_active": False},
        headers=superadmin_headers,
    )
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["is_active"] is False
    assert "ocean" not in {
        item["key"]
        for item in (await client.get("/api/v1/themes/available", headers=superadmin_headers)).json()["items"]
    }

    deleted = await client.delete("/api/v1/themes/ocean", headers=superadmin_headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert (await client.get("/api/v1/themes/ocean", headers=superadmin_headers)).status_code == 404

    builtin = await client.delete("/api/v1/themes/default", headers=superadmin_headers)
    assert builtin.status_code == 422
    assert builtin.json()["error"]["message_key"] == "error.theme.builtin_required"

    replace_builtin = await client.post(
        "/api/v1/themes/import",
        json={**json_import("Hijack"), "key": "default"},
        headers=superadmin_headers,
    )
    assert replace_builtin.status_code == 422
    assert replace_builtin.json()["error"]["message_key"] == "error.theme.builtin_required"
    assert (await client.get("/api/v1/themes/default", headers=superadmin_headers)).json()[
        "is_builtin"
    ] is True

    activity = await client.get(
        "/api/v1/audit/activity",
        params={"entity_type": "theme"},
        headers=superadmin_headers,
    )
    actions = [item["action"] for item in activity.json()["items"]]
    assert "theme.import" in actions
    assert "theme.default" in actions
    assert "theme.update" in actions
    assert "theme.delete" in actions


async def test_permissions_for_the_manager_and_user_endpoints(client, limited_headers):
    denied = await client.post(
        "/api/v1/themes/import",
        json=json_import("Nope"),
        headers=limited_headers,
    )
    assert denied.status_code == 403
    assert (
        await client.post("/api/v1/themes/preview", json=json_import(), headers=limited_headers)
    ).status_code == 403
    assert (await client.get("/api/v1/themes/available")).status_code == 401


@pytest.mark.parametrize("mode", ["sepia", "auto"])
async def test_invalid_mode_is_rejected(client, limited_headers, mode):
    response = await client.put(
        "/api/v1/themes/preference",
        json={"theme_key": None, "mode": mode},
        headers=limited_headers,
    )
    assert response.status_code == 422
