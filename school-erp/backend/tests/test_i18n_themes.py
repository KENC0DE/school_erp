"""P0-13 and P0-14: translation layers, ETag and the active theme."""

from __future__ import annotations

from sqlalchemy import text


async def test_english_and_amharic_bundles(client):
    en = await client.get("/api/v1/i18n/en/core")
    assert en.status_code == 200
    assert en.json()["messages"]["app.name"] == "School ERP"
    am = await client.get("/api/v1/i18n/am/core")
    assert am.status_code == 200
    assert am.json()["messages"]["app.name"] == "የትምህርት ቤት ኢአርፒ"


async def test_school_layer_override_wins(app, client):
    async with app.state.db.session() as session:
        await session.execute(
            text(
                "INSERT INTO translation_entries (id, namespace, key, locale, value, status, source, layer, created_at, updated_at) "
                "VALUES ('11111111-1111-1111-1111-111111111111', 'core', 'app.name', 'en', 'Demo Academy ERP', 'approved', 'human', 'school', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        await session.commit()
    response = await client.get("/api/v1/i18n/en/core")
    assert response.json()["messages"]["app.name"] == "Demo Academy ERP"


async def test_etag_gives_304(client):
    first = await client.get("/api/v1/i18n/en/core")
    etag = first.headers["etag"]
    second = await client.get("/api/v1/i18n/en/core", headers={"If-None-Match": etag})
    assert second.status_code == 304


async def test_module_namespace_is_available(client):
    response = await client.get("/api/v1/i18n/am/sample")
    assert response.status_code == 200
    assert response.json()["messages"]["title"] == "ናሙና ሞጁል"


async def test_active_theme_has_both_modes(client):
    response = await client.get("/api/v1/themes/active")
    assert response.status_code == 200
    theme = response.json()
    assert "light" in theme["tokens"]
    assert "dark" in theme["tokens"]
    for required in ("background", "foreground", "primary", "chart-1", "sidebar"):
        assert theme["tokens"]["light"][required]
        assert theme["tokens"]["dark"][required]
