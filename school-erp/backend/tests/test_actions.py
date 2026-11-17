"""P0-12: the action registry filters tools by permission and enabled modules."""

from __future__ import annotations


async def test_users_see_different_tool_lists(client, manager_headers, limited_headers, superadmin_headers):
    manager = await client.get("/api/v1/ai/tools", headers=manager_headers)
    assert manager.status_code == 200
    manager_keys = {tool["key"] for tool in manager.json()["items"]}
    assert "sample.notes.create" in manager_keys
    assert "sample.notes.list" in manager_keys

    limited = await client.get("/api/v1/ai/tools", headers=limited_headers)
    limited_keys = {tool["key"] for tool in limited.json()["items"]}
    assert "sample.notes.list" in limited_keys
    assert "sample.notes.create" not in limited_keys

    superadmin = await client.get("/api/v1/ai/tools", headers=superadmin_headers)
    superadmin_keys = {tool["key"] for tool in superadmin.json()["items"]}
    assert manager_keys <= superadmin_keys


async def test_disabled_module_removes_its_tools(client, superadmin_headers, manager_headers):
    await client.put("/api/v1/system/modules/sample", json={"enabled": False}, headers=superadmin_headers)
    response = await client.get("/api/v1/ai/tools", headers=manager_headers)
    keys = {tool["key"] for tool in response.json()["items"]}
    assert not any(key.startswith("sample.") for key in keys)


async def test_chat_echo_lists_tools(client, manager_headers):
    response = await client.post("/api/v1/ai/chat", json={"message": "hello"}, headers=manager_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Echo: hello"
    assert body["configured"] is False
    assert body["tools"]


async def test_action_preview_requires_permission(client, manager_headers, limited_headers):
    preview = await client.post(
        "/api/v1/ai/actions/sample.notes.create/preview",
        json={"content": "proposed"},
        headers=manager_headers,
    )
    assert preview.status_code == 200
    assert preview.json()["preview"]["count"] == 1
    assert preview.json()["requires_confirmation"] is True

    denied = await client.post(
        "/api/v1/ai/actions/sample.notes.create/preview",
        json={"content": "proposed"},
        headers=limited_headers,
    )
    assert denied.status_code == 403
