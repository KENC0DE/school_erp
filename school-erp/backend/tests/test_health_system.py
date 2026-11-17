"""P0-04 and P0-04b: health, readiness, version info and capabilities."""

from __future__ import annotations


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"].startswith("req_")


async def test_ready(client):
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "up"


async def test_request_id_is_echoed(client):
    response = await client.get("/health", headers={"X-Request-ID": "req_custom_123"})
    assert response.headers["x-request-id"] == "req_custom_123"


async def test_system_info_is_public(client):
    response = await client.get("/api/v1/system/info")
    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v1"
    assert "app_version" in body
    assert "min_client_version" in body


async def test_capabilities_require_auth(client):
    response = await client.get("/api/v1/system/capabilities")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_capabilities_follow_enabled_modules(client, superadmin_headers):
    response = await client.get("/api/v1/system/capabilities", headers=superadmin_headers)
    assert response.status_code == 200
    keys = {feature["key"] for feature in response.json()["features"]}
    assert "sample" in keys

    toggle = await client.put(
        "/api/v1/system/modules/sample", json={"enabled": False}, headers=superadmin_headers
    )
    assert toggle.status_code == 200, toggle.text

    response = await client.get("/api/v1/system/capabilities", headers=superadmin_headers)
    keys = {feature["key"] for feature in response.json()["features"]}
    assert "sample" not in keys


async def test_modules_listing_shows_three_gates(client, superadmin_headers):
    response = await client.get("/api/v1/system/modules", headers=superadmin_headers)
    assert response.status_code == 200
    sample = next(item for item in response.json()["items"] if item["key"] == "sample")
    assert sample["licensed"] is True
    assert sample["enabled"] is True
    assert sample["available"] is True
