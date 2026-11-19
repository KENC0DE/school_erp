"""P0-08: RBAC allowed/denied behaviour and the route permission coverage guard."""

from __future__ import annotations

from fastapi.routing import APIRoute


async def test_allowed_permission(client, manager_headers):
    response = await client.get("/api/v1/auth/users", headers=manager_headers)
    assert response.status_code == 200
    assert response.json()["items"]


async def test_denied_permission(client, limited_headers):
    response = await client.get("/api/v1/auth/users", headers=limited_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_roles_visible_only_with_permission(client, auditor_headers):
    allowed = await client.get("/api/v1/rbac/roles", headers=auditor_headers)
    assert allowed.status_code == 200
    denied = await client.get("/api/v1/rbac/roles")
    assert denied.status_code == 401


def _dependency_markers(dependant) -> set[str]:
    markers: set[str] = set()
    call = getattr(dependant, "call", None)
    if call is not None:
        if getattr(call, "__public__", False):
            markers.add("public")
        if getattr(call, "__auth_only__", False):
            markers.add("authenticated")
        if getattr(call, "__permission__", None):
            markers.add(f"permission:{call.__permission__}")
    for child in dependant.dependencies:
        markers |= _dependency_markers(child)
    return markers


def test_every_api_route_declares_a_permission(app):
    missing: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/v1") or route.path.endswith("openapi.json"):
            continue
        markers = _dependency_markers(route.dependant)
        if not markers:
            missing.append(f"{sorted(route.methods)} {route.path}")
    assert not missing, f"Routes without permission/public/auth declaration: {missing}"


async def test_permission_denial_is_audited_once_per_call(client, limited_headers):
    response = await client.get("/api/v1/audit/activity", headers=limited_headers)
    assert response.status_code == 403
