"""P2-01: academic structure catalog, stages and school scope."""

from __future__ import annotations

from tests.conftest import create_role, create_user, login, unique_email

BASE = "/api/v1/academics"
SETTINGS = "/api/v1/settings"
ACTIVITY = "/api/v1/audit/activity"


async def _codes(client, headers, suffix: str = "/levels", **params) -> list[str]:
    response = await client.get(f"{BASE}{suffix}", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return [item["code"] for item in response.json()["items"]]


async def _level(client, headers, code: str, **params) -> dict:
    response = await client.get(f"{BASE}/levels", headers=headers, params={"scope": "all", **params})
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["code"] == code)


async def test_starter_catalog_nav_and_scope_defaults(client, app, superadmin_headers, seeded) -> None:
    response = await client.get(f"{BASE}/levels", headers=superadmin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["code"] for item in body["items"]] == [
        "kg1",
        "kg2",
        "kg3",
        "g1",
        "g2",
        "g3",
        "g4",
        "g5",
        "g6",
        "g7",
        "g8",
        "g9",
        "g10",
        "g11",
        "g12",
    ]
    assert body["total"] == 15
    assert all(item["is_starter"] and not item["is_verified"] for item in body["items"])
    assert body["scope"] == {
        "first_level": 0,
        "last_level": 12,
        "level_count": 15,
        "stage_count": 5,
        "scope_levels": list(range(13)),
    }

    stages = await client.get(f"{BASE}/stages", headers=superadmin_headers)
    assert stages.status_code == 200, stages.text
    stage_body = stages.json()
    assert [item["code"] for item in stage_body["items"]] == [
        "kindergarten",
        "primary_lower",
        "primary_upper",
        "secondary",
        "preparatory",
    ]
    kindergarten = stage_body["items"][0]
    assert [level["code"] for level in kindergarten["levels"]] == ["kg1", "kg2", "kg3"]
    assert kindergarten["in_scope"] is True
    assert all(item["is_starter"] for item in stage_body["items"])

    nav = await client.get("/api/v1/auth/me/navigation", headers=superadmin_headers)
    assert "academics" in [item["key"] for item in nav.json()["items"]]


async def test_scope_hides_levels_and_stages_from_every_listing(client, superadmin_headers, seeded) -> None:
    changed = await client.put(
        f"{BASE}/scope",
        headers=superadmin_headers,
        json={"first_level": 1, "last_level": 5, "reason": "Primary school only"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json() == {
        "first_level": 1,
        "last_level": 5,
        "level_count": 5,
        "stage_count": 2,
        "scope_levels": list(range(13)),
    }

    assert await _codes(client, superadmin_headers) == ["g1", "g2", "g3", "g4", "g5"]

    stages = await client.get(f"{BASE}/stages", headers=superadmin_headers)
    assert stages.status_code == 200
    stage_items = stages.json()["items"]
    assert [item["code"] for item in stage_items] == ["primary_lower", "primary_upper"]
    assert [level["code"] for level in stage_items[0]["levels"]] == ["g1", "g2", "g3", "g4"]
    # The upper-primary stage is clipped to the levels the school actually runs.
    assert [level["code"] for level in stage_items[1]["levels"]] == ["g5"]
    assert all(level["in_scope"] for item in stage_items for level in item["levels"])

    g6 = await _level(client, superadmin_headers, "g6")
    blocked = await client.get(f"{BASE}/levels/{g6['id']}", headers=superadmin_headers)
    assert blocked.status_code == 404
    assert blocked.json()["error"]["message_key"] == "error.academics.level_out_of_scope"

    # Management can still reach the full catalog to widen the scope again.
    all_levels = await client.get(f"{BASE}/levels", headers=superadmin_headers, params={"scope": "all"})
    assert all_levels.status_code == 200
    assert all_levels.json()["total"] == 15

    # Scope is persisted in the layered settings, not in a module-only table.
    settings = await client.get(SETTINGS, headers=superadmin_headers)
    core = next(item for item in settings.json()["items"] if item["module"] == "core")
    values = {field["key"]: field["value"] for field in core["fields"]}
    assert values["academic_scope.first_level"] == 1
    assert values["academic_scope.last_level"] == 5

    # A single-field settings edit cannot invert the range either.
    inverted = await client.put(
        f"{SETTINGS}/core/academic_scope.first_level",
        headers=superadmin_headers,
        json={"value": 8},
    )
    assert inverted.status_code == 422
    assert inverted.json()["error"]["message_key"] == "error.invalid_setting"


async def test_scope_validation_audit_and_noop(client, app, superadmin_headers, seeded) -> None:
    empty = await client.put(
        f"{BASE}/scope",
        headers=superadmin_headers,
        json={"first_level": 6, "last_level": 4},
    )
    assert empty.status_code == 422
    assert empty.json()["error"]["message_key"] == "error.academics.scope_order"

    # Removing every level in a range makes that range invalid.
    for code in ("g11", "g12"):
        level = await _level(client, superadmin_headers, code)
        deleted = await client.delete(f"{BASE}/levels/{level['id']}", headers=superadmin_headers)
        assert deleted.status_code == 200, deleted.text
    missing = await client.put(
        f"{BASE}/scope",
        headers=superadmin_headers,
        json={"first_level": 11, "last_level": 12},
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["message_key"] == "error.academics.scope_empty"

    changed = await client.put(
        f"{BASE}/scope",
        headers=superadmin_headers,
        json={"first_level": 1, "last_level": 12},
    )
    assert changed.status_code == 200, changed.text

    activity = await client.get(ACTIVITY, headers=superadmin_headers, params={"limit": 100})
    assert activity.status_code == 200
    scope_entries = [item for item in activity.json()["items"] if item["action"] == "academics.scope.update"]
    assert len(scope_entries) == 1
    assert scope_entries[0]["after"] == {"first_level": 1, "last_level": 12}
    assert scope_entries[0]["before"] == {"first_level": 0, "last_level": 12}

    chain = await client.get("/api/v1/audit/verify", headers=superadmin_headers)
    assert chain.status_code == 200
    assert chain.json()["ok"] is True

    # Repeating the same scope is a no-op and adds no audit entry.
    again = await client.put(
        f"{BASE}/scope",
        headers=superadmin_headers,
        json={"first_level": 1, "last_level": 12},
    )
    assert again.status_code == 200
    activity = await client.get(ACTIVITY, headers=superadmin_headers, params={"limit": 100})
    assert len([item for item in activity.json()["items"] if item["action"] == "academics.scope.update"]) == 1


async def test_level_crud_conflicts_soft_delete_restore_and_audit(client, superadmin_headers, seeded) -> None:
    created = await client.post(
        f"{BASE}/levels",
        headers=superadmin_headers,
        json={
            "code": "transition",
            "name": "Transition",
            "name_am": "ሽግግር",
            "scope_level": 12,
            "sort_order": 20,
        },
    )
    assert created.status_code == 201, created.text
    level = created.json()
    assert level["is_starter"] is False
    assert level["is_verified"] is True
    assert level["in_scope"] is True
    assert level["row_version"] == 1

    duplicate = await client.post(
        f"{BASE}/levels",
        headers=superadmin_headers,
        json={"code": "transition", "name": "Another", "scope_level": 12},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "error.academics.level_code_taken"

    invalid = await client.post(
        f"{BASE}/levels",
        headers=superadmin_headers,
        json={"code": "beyond", "name": "Beyond", "scope_level": 13},
    )
    assert invalid.status_code == 422

    updated = await client.patch(
        f"{BASE}/levels/{level['id']}",
        headers=superadmin_headers,
        json={"name": "Transition year", "sort_order": 21, "row_version": level["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Transition year"
    assert updated.json()["row_version"] == 2

    stale = await client.patch(
        f"{BASE}/levels/{level['id']}",
        headers=superadmin_headers,
        json={"name": "Stale", "row_version": 1},
    )
    assert stale.status_code == 409

    deleted = await client.delete(
        f"{BASE}/levels/{level['id']}",
        headers=superadmin_headers,
        params={"row_version": updated.json()["row_version"], "reason": "Not offered next year"},
    )
    assert deleted.status_code == 200, deleted.text
    assert (await client.get(f"{BASE}/levels/{level['id']}", headers=superadmin_headers)).status_code == 404

    listed = await client.get(f"{BASE}/levels", headers=superadmin_headers, params={"scope": "all"})
    assert "transition" not in [item["code"] for item in listed.json()["items"]]

    restored = await client.post(f"{BASE}/levels/{level['id']}/restore", headers=superadmin_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["name"] == "Transition year"

    activity = await client.get(ACTIVITY, headers=superadmin_headers, params={"limit": 100})
    actions = {item["action"] for item in activity.json()["items"]}
    assert {
        "academics.levels.create",
        "academics.levels.update",
        "academics.levels.delete",
        "academics.levels.restore",
    } <= actions
    assert all(
        item["module"] == "academics"
        for item in activity.json()["items"]
        if item["action"].startswith("academics.")
    )


async def test_stage_crud_keeps_membership_across_restore(client, superadmin_headers, seeded) -> None:
    g9 = await _level(client, superadmin_headers, "g9")
    g10 = await _level(client, superadmin_headers, "g10")
    created = await client.post(
        f"{BASE}/stages",
        headers=superadmin_headers,
        json={
            "code": "senior",
            "name": "Senior school",
            "name_am": "የከፍተኛ ደረጃ",
            "level_ids": [g9["id"], g10["id"]],
        },
    )
    assert created.status_code == 201, created.text
    stage = created.json()
    assert [item["code"] for item in stage["levels"]] == ["g9", "g10"]
    assert stage["in_scope"] is True

    duplicate = await client.post(
        f"{BASE}/stages",
        headers=superadmin_headers,
        json={"code": "senior", "name": "Another", "level_ids": [g9["id"]]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "error.academics.stage_code_taken"

    missing = await client.post(
        f"{BASE}/stages",
        headers=superadmin_headers,
        json={
            "code": "ghost",
            "name": "Ghost",
            "level_ids": ["00000000-0000-0000-0000-000000000000"],
        },
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["message_key"] == "error.academics.level_missing"

    updated = await client.patch(
        f"{BASE}/stages/{stage['id']}",
        headers=superadmin_headers,
        json={"name": "Senior secondary", "level_ids": [g9["id"]], "row_version": stage["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    assert [item["code"] for item in updated.json()["levels"]] == ["g9"]

    deleted = await client.delete(
        f"{BASE}/stages/{stage['id']}",
        headers=superadmin_headers,
        params={"row_version": updated.json()["row_version"]},
    )
    assert deleted.status_code == 200
    # Membership survives the soft delete, so a restore brings the stage back intact.
    assert [item["code"] for item in deleted.json()["levels"]] == ["g9"]
    assert (await client.get(f"{BASE}/stages/{stage['id']}", headers=superadmin_headers)).status_code == 404

    restored = await client.post(f"{BASE}/stages/{stage['id']}/restore", headers=superadmin_headers)
    assert restored.status_code == 200, restored.text
    assert [item["code"] for item in restored.json()["levels"]] == ["g9"]


async def test_academics_permissions_and_module_gate(client, app, seeded, superadmin_headers) -> None:
    viewer = await create_role(
        app,
        "academics_viewer",
        [("academics.view", "all"), ("ai.use", "all")],
    )
    viewer_email = unique_email("academics-viewer")
    await create_user(app, viewer_email, roles=[viewer.key])
    headers = await login(client, viewer_email)

    assert (await client.get(f"{BASE}/levels", headers=headers)).status_code == 200
    assert (await client.get(f"{BASE}/scope", headers=headers)).status_code == 200

    for path, method in (
        (f"{BASE}/levels?scope=all", "get"),
        (f"{BASE}/stages?scope=all", "get"),
        (f"{BASE}/levels", "post"),
        (f"{BASE}/scope", "put"),
    ):
        kwargs = {"headers": headers}
        if method in ("post", "put"):
            kwargs["json"] = {}
        response = await getattr(client, method)(path, **kwargs)
        assert response.status_code == 403, (method, path, response.text)

    # Students depends on academics, so its dependants block the toggle first.
    guarded = await client.put(
        "/api/v1/system/modules/academics",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert guarded.status_code == 409, guarded.text
    assert guarded.json()["error"]["message_key"] == "modules.dependants_enabled"
    assert {"students", "attendance", "assessment"} <= set(guarded.json()["error"]["details"]["dependants"])

    off_admissions = await client.put(
        "/api/v1/system/modules/admissions",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert off_admissions.status_code == 200, off_admissions.text
    # Attendance also depends on students, so it must be switched off first.
    off_attendance = await client.put(
        "/api/v1/system/modules/attendance",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert off_attendance.status_code == 200, off_attendance.text
    # Assessment also depends on students, so it must be switched off first.
    off_assessment = await client.put(
        "/api/v1/system/modules/assessment",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert off_assessment.status_code == 200, off_assessment.text
    off_students = await client.put(
        "/api/v1/system/modules/students",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert off_students.status_code == 200, off_students.text

    disabled = await client.put(
        "/api/v1/system/modules/academics",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    blocked = await client.get(f"{BASE}/levels", headers=superadmin_headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "MODULE_DISABLED"
