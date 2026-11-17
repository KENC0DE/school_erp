"""P1-08: module management exposes the three gates and dependency warnings."""

from __future__ import annotations

from core.modules.manifest import ModuleManifest
from core.modules.registry import ModuleRegistry


def _with_dependency_pair(app) -> None:
    """Add two in-memory manifests so dependency rules can be exercised."""
    manifests = dict(app.state.registry.manifests)
    manifests["base_module"] = ModuleManifest(
        key="base_module",
        name="Base module",
        version="1.0.0",
        description="Required by the child module.",
        default_enabled=False,
    )
    manifests["child_module"] = ModuleManifest(
        key="child_module",
        name="Child module",
        version="1.0.0",
        description="Depends on the base module.",
        depends_on=["base_module"],
        default_enabled=False,
    )
    app.state.registry = ModuleRegistry(manifests=manifests)


async def test_module_listing_requires_modules_view(client, limited_headers, auditor_headers):
    denied = await client.get("/api/v1/system/modules", headers=limited_headers)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

    allowed = await client.get("/api/v1/system/modules", headers=auditor_headers)
    assert allowed.status_code == 200


async def test_navigation_links_modules_only_for_viewers(client, limited_headers, auditor_headers):
    denied = await client.get("/api/v1/auth/me/navigation", headers=limited_headers)
    denied_paths = [item["path"] for item in denied.json()["items"]]
    assert "/settings/modules" not in denied_paths

    allowed = await client.get("/api/v1/auth/me/navigation", headers=auditor_headers)
    modules_item = next(item for item in allowed.json()["items"] if item["key"] == "modules")
    assert modules_item["path"] == "/settings/modules"
    assert modules_item["label_key"] == "nav.modules"


async def test_module_listing_shows_dependency_metadata(app, client, superadmin_headers):
    _with_dependency_pair(app)

    response = await client.get("/api/v1/system/modules", headers=superadmin_headers)
    assert response.status_code == 200, response.text
    items = {item["key"]: item for item in response.json()["items"]}

    child = items["child_module"]
    assert child["licensed"] is True
    assert child["enabled"] is False
    assert child["available"] is False
    assert child["permitted"] is True
    assert child["depends_on"] == ["base_module"]
    assert child["dependencies"] == [{"key": "base_module", "name": "Base module", "available": False}]
    assert child["blocked_by"] == ["base_module"]

    base = items["base_module"]
    assert base["dependants"] == [{"key": "child_module", "name": "Child module", "enabled": False}]


async def test_dependencies_block_enable_and_disable(app, client, superadmin_headers):
    _with_dependency_pair(app)
    url = "/api/v1/system/modules"

    too_early = await client.put(f"{url}/child_module", json={"enabled": True}, headers=superadmin_headers)
    assert too_early.status_code == 409
    error = too_early.json()["error"]
    assert error["code"] == "CONFLICT"
    assert error["message_key"] == "modules.dependency_disabled"
    assert error["details"] == {"dependency": "base_module"}

    enabled_base = await client.put(f"{url}/base_module", json={"enabled": True}, headers=superadmin_headers)
    assert enabled_base.status_code == 200, enabled_base.text
    enabled_child = await client.put(
        f"{url}/child_module", json={"enabled": True}, headers=superadmin_headers
    )
    assert enabled_child.status_code == 200, enabled_child.text

    too_early_off = await client.put(
        f"{url}/base_module", json={"enabled": False}, headers=superadmin_headers
    )
    assert too_early_off.status_code == 409
    error = too_early_off.json()["error"]
    assert error["message_key"] == "modules.dependants_enabled"
    assert error["details"] == {"dependants": ["child_module"]}

    off_child = await client.put(f"{url}/child_module", json={"enabled": False}, headers=superadmin_headers)
    assert off_child.status_code == 200, off_child.text
    off_base = await client.put(f"{url}/base_module", json={"enabled": False}, headers=superadmin_headers)
    assert off_base.status_code == 200, off_base.text
