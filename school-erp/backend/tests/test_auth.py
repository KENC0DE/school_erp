"""P0-07: authentication, refresh rotation and /me."""

from __future__ import annotations

from tests.conftest import login


async def test_login_and_me(client, seeded):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "superadmin@demo.school", "password": "DevPass#2026"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == "superadmin@demo.school"
    headers = {"Authorization": f"Bearer {body['tokens']['access_token']}"}

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["roles"] == ["super_admin"]
    assert me.json()["permissions"] == ["*"]


async def test_bad_password_is_rejected(client, seeded):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "superadmin@demo.school", "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["message_key"] == "auth.invalid"


async def test_unknown_user_is_rejected(client, seeded):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@demo.school", "password": "DevPass#2026"}
    )
    assert response.status_code == 401


async def test_refresh_rotates_and_detects_reuse(client, seeded):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "limited@demo.school", "password": "DevPass#2026"}
    )
    tokens = response.json()["tokens"]

    first = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    rotated = first.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]

    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["message_key"] == "error.refresh_reuse"

    # The whole family is revoked, so the rotated token no longer works either.
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert after.status_code == 401


async def test_navigation_requires_auth_and_reflects_permissions(client, seeded):
    anonymous = await client.get("/api/v1/auth/me/navigation")
    assert anonymous.status_code == 401

    headers = await login(client, "limited@demo.school")
    response = await client.get("/api/v1/auth/me/navigation", headers=headers)
    assert response.status_code == 200
    keys = [item["key"] for item in response.json()["items"]]
    assert "dashboard" in keys
    assert "sample" in keys


async def test_logout_revokes_refresh_tokens(client, seeded):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "limited@demo.school", "password": "DevPass#2026"}
    )
    tokens = response.json()["tokens"]
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 200
    refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401
