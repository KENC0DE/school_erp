"""P0-09: the three gates (licensed, enabled, permitted)."""

from __future__ import annotations


async def test_disabling_module_hides_nav_and_blocks_api_instantly(
    client, superadmin_headers, limited_headers
):
    nav = await client.get("/api/v1/auth/me/navigation", headers=limited_headers)
    assert "sample" in [item["key"] for item in nav.json()["items"]]
    allowed = await client.get("/api/v1/sample/notes", headers=limited_headers)
    assert allowed.status_code == 200

    toggled = await client.put(
        "/api/v1/system/modules/sample", json={"enabled": False}, headers=superadmin_headers
    )
    assert toggled.status_code == 200

    nav = await client.get("/api/v1/auth/me/navigation", headers=limited_headers)
    assert "sample" not in [item["key"] for item in nav.json()["items"]]
    blocked = await client.get("/api/v1/sample/notes", headers=limited_headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "MODULE_DISABLED"

    again = await client.put(
        "/api/v1/system/modules/sample", json={"enabled": True}, headers=superadmin_headers
    )
    assert again.status_code == 200
    restored = await client.get("/api/v1/sample/notes", headers=limited_headers)
    assert restored.status_code == 200


async def test_toggle_requires_permission(client, limited_headers):
    response = await client.put(
        "/api/v1/system/modules/sample", json={"enabled": False}, headers=limited_headers
    )
    assert response.status_code == 403


async def test_toggle_is_audited(client, superadmin_headers):
    await client.put("/api/v1/system/modules/sample", json={"enabled": False}, headers=superadmin_headers)
    await client.put("/api/v1/system/modules/sample", json={"enabled": True}, headers=superadmin_headers)
    activity = await client.get("/api/v1/audit/activity", headers=superadmin_headers)
    actions = [item["action"] for item in activity.json()["items"]]
    assert "modules.toggle" in actions


async def test_disabling_core_module_is_rejected(client, superadmin_headers):
    response = await client.put(
        "/api/v1/system/modules/core", json={"enabled": False}, headers=superadmin_headers
    )
    assert response.status_code == 404
