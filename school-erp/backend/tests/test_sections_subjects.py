"""P2-03: subjects, level-subject assignment, subject groups and sections."""

from __future__ import annotations

from tests.conftest import create_role, create_user, login, unique_email

BASE = "/api/v1/academics"
SETTINGS = "/api/v1/settings"
ACTIVITY = "/api/v1/audit/activity"


async def _year(client, headers, code: str = "2026-2027") -> dict:
    response = await client.post(
        f"{BASE}/academic-years",
        headers=headers,
        json={
            "code": code,
            "name": code.replace("-", "/"),
            "start_date": "2026-09-11",
            "end_date": "2027-06-30",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _subject(client, headers, code: str, name: str, **overrides) -> dict:
    response = await client.post(
        f"{BASE}/subjects",
        headers=headers,
        json={"code": code, "name": name, "name_am": name, **overrides},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _level(client, headers, code: str) -> dict:
    response = await client.get(f"{BASE}/levels", headers=headers, params={"scope": "all"})
    assert response.status_code == 200
    return next(item for item in response.json()["items"] if item["code"] == code)


async def _activity(client, headers) -> list[str]:
    response = await client.get(ACTIVITY, headers=headers, params={"limit": 200})
    assert response.status_code == 200, response.text
    return [item["action"] for item in response.json()["items"]]


async def test_subject_crud_conflicts_soft_delete_and_restore(client, superadmin_headers, seeded) -> None:
    initial = await client.get(f"{BASE}/subjects", headers=superadmin_headers)
    assert initial.status_code == 200
    assert initial.json()["total"] == 0

    maths = await _subject(client, superadmin_headers, "maths", "Mathematics")
    english = await _subject(client, superadmin_headers, "english", "English", sort_order=1)
    assert maths["is_active"] is True
    assert maths["row_version"] == 1

    listed = await client.get(f"{BASE}/subjects", headers=superadmin_headers)
    assert [item["code"] for item in listed.json()["items"]] == ["maths", "english"]

    duplicate = await client.post(
        f"{BASE}/subjects",
        headers=superadmin_headers,
        json={"code": "maths", "name": "Another"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "error.academics.subject_code_taken"

    updated = await client.patch(
        f"{BASE}/subjects/{maths['id']}",
        headers=superadmin_headers,
        json={"name": "Maths", "name_am": "ሒሳብ", "row_version": maths["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name_am"] == "ሒሳብ"
    assert updated.json()["row_version"] == 2

    stale = await client.patch(
        f"{BASE}/subjects/{maths['id']}",
        headers=superadmin_headers,
        json={"name": "Stale", "row_version": 1},
    )
    assert stale.status_code == 409

    deleted = await client.delete(
        f"{BASE}/subjects/{english['id']}",
        headers=superadmin_headers,
        params={"row_version": english["row_version"], "reason": "Merged into English Language"},
    )
    assert deleted.status_code == 200, deleted.text
    assert (
        await client.get(f"{BASE}/subjects/{english['id']}", headers=superadmin_headers)
    ).status_code == 404
    assert (await client.get(f"{BASE}/subjects", headers=superadmin_headers)).json()["total"] == 1

    restored = await client.post(f"{BASE}/subjects/{english['id']}/restore", headers=superadmin_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["name"] == "English"

    actions = await _activity(client, superadmin_headers)
    assert "academics.subjects.create" in actions
    assert "academics.subjects.update" in actions
    assert "academics.subjects.delete" in actions
    assert "academics.subjects.restore" in actions


async def test_level_subject_assignment_respects_scope_and_active_rows(
    client, superadmin_headers, seeded
) -> None:
    maths = await _subject(client, superadmin_headers, "maths", "Mathematics")
    english = await _subject(client, superadmin_headers, "english", "English", sort_order=1)
    g5 = await _level(client, superadmin_headers, "g5")
    g6 = await _level(client, superadmin_headers, "g6")

    assigned = await client.put(
        f"{BASE}/levels/{g5['id']}/subjects",
        headers=superadmin_headers,
        json={
            "subjects": [
                {"subject_id": maths["id"], "credit": 5},
                {"subject_id": english["id"], "credit": 4},
            ]
        },
    )
    assert assigned.status_code == 200, assigned.text
    body = assigned.json()
    assert body["level_code"] == "g5"
    assert [(item["code"], item["credit"]) for item in body["items"]] == [
        ("maths", 5),
        ("english", 4),
    ]

    replaced = await client.put(
        f"{BASE}/levels/{g5['id']}/subjects",
        headers=superadmin_headers,
        json={"subjects": [{"subject_id": maths["id"], "credit": 6}]},
    )
    assert replaced.status_code == 200, replaced.text
    assert [item["code"] for item in replaced.json()["items"]] == ["maths"]
    assert replaced.json()["items"][0]["credit"] == 6

    missing = await client.put(
        f"{BASE}/levels/{g5['id']}/subjects",
        headers=superadmin_headers,
        json={"subjects": [{"subject_id": "00000000-0000-0000-0000-000000000000", "credit": 1}]},
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["message_key"] == "error.academics.subject_missing"

    deactivated = await client.patch(
        f"{BASE}/subjects/{english['id']}",
        headers=superadmin_headers,
        json={"is_active": False, "row_version": english["row_version"]},
    )
    assert deactivated.status_code == 200, deactivated.text
    inactive = await client.put(
        f"{BASE}/levels/{g5['id']}/subjects",
        headers=superadmin_headers,
        json={"subjects": [{"subject_id": english["id"], "credit": 1}]},
    )
    assert inactive.status_code == 422
    assert inactive.json()["error"]["message_key"] == "error.academics.subject_inactive"

    narrowed = await client.put(
        f"{BASE}/scope",
        headers=superadmin_headers,
        json={"first_level": 1, "last_level": 5},
    )
    assert narrowed.status_code == 200, narrowed.text
    out_of_scope = await client.get(f"{BASE}/levels/{g6['id']}/subjects", headers=superadmin_headers)
    assert out_of_scope.status_code == 404
    assert out_of_scope.json()["error"]["message_key"] == "error.academics.level_out_of_scope"

    # Scoped reads still work, but an inactive level cannot receive subjects.
    await client.put(
        f"{BASE}/scope",
        headers=superadmin_headers,
        json={"first_level": 0, "last_level": 12},
    )
    disabled_level = await client.patch(
        f"{BASE}/levels/{g5['id']}",
        headers=superadmin_headers,
        json={"is_active": False, "row_version": g5["row_version"]},
    )
    assert disabled_level.status_code == 200, disabled_level.text
    inactive_level = await client.put(
        f"{BASE}/levels/{g5['id']}/subjects",
        headers=superadmin_headers,
        json={"subjects": [{"subject_id": maths["id"], "credit": 1}]},
    )
    assert inactive_level.status_code == 422
    assert inactive_level.json()["error"]["message_key"] == "error.academics.level_inactive"

    actions = await _activity(client, superadmin_headers)
    assert "academics.subjects.assignments.replace" in actions


async def test_subject_groups_membership_and_restore(client, superadmin_headers, seeded) -> None:
    maths = await _subject(client, superadmin_headers, "maths", "Mathematics")
    english = await _subject(client, superadmin_headers, "english", "English", sort_order=1)

    created = await client.post(
        f"{BASE}/subject-groups",
        headers=superadmin_headers,
        json={
            "code": "sciences",
            "name": "Sciences",
            "name_am": "ሳይንሶች",
            "subject_ids": [maths["id"]],
        },
    )
    assert created.status_code == 201, created.text
    group = created.json()
    assert [item["code"] for item in group["subjects"]] == ["maths"]

    duplicate = await client.post(
        f"{BASE}/subject-groups",
        headers=superadmin_headers,
        json={"code": "sciences", "name": "Another"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "error.academics.subject_group_code_taken"

    missing = await client.post(
        f"{BASE}/subject-groups",
        headers=superadmin_headers,
        json={
            "code": "ghost",
            "name": "Ghost",
            "subject_ids": ["00000000-0000-0000-0000-000000000000"],
        },
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["message_key"] == "error.academics.subject_missing"

    updated = await client.patch(
        f"{BASE}/subject-groups/{group['id']}",
        headers=superadmin_headers,
        json={
            "name": "Science stream",
            "subject_ids": [english["id"]],
            "row_version": group["row_version"],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Science stream"
    assert [item["code"] for item in updated.json()["subjects"]] == ["english"]

    stale = await client.patch(
        f"{BASE}/subject-groups/{group['id']}",
        headers=superadmin_headers,
        json={"name": "Stale", "row_version": group["row_version"]},
    )
    assert stale.status_code == 409

    deleted = await client.delete(
        f"{BASE}/subject-groups/{group['id']}",
        headers=superadmin_headers,
        params={"row_version": updated.json()["row_version"]},
    )
    assert deleted.status_code == 200
    assert (await client.get(f"{BASE}/subject-groups", headers=superadmin_headers)).json()["total"] == 0

    restored = await client.post(f"{BASE}/subject-groups/{group['id']}/restore", headers=superadmin_headers)
    assert restored.status_code == 200, restored.text
    assert [item["code"] for item in restored.json()["subjects"]] == ["english"]


async def test_sections_crud_listing_and_homeroom_validation(client, app, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    g5 = await _level(client, superadmin_headers, "g5")
    g6 = await _level(client, superadmin_headers, "g6")
    teacher = await create_user(app, unique_email("homeroom"), display_name="Abebe Kebede")

    created = await client.post(
        f"{BASE}/sections",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "level_id": g5["id"],
            "code": "A",
            "name": "Grade 5 A",
            "name_am": "ክፍል 5 ሀ",
            "capacity": 45,
            "homeroom_user_id": str(teacher.id),
        },
    )
    assert created.status_code == 201, created.text
    section = created.json()
    assert section["year_code"] == "2026-2027"
    assert section["level_code"] == "g5"
    assert section["level_name"] == "Grade 5"
    assert section["homeroom_name"] == "Abebe Kebede"
    assert section["capacity"] == 45

    duplicate = await client.post(
        f"{BASE}/sections",
        headers=superadmin_headers,
        json={"year_id": year["id"], "level_id": g5["id"], "code": "A"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "error.academics.section_code_taken"

    other_level = await client.post(
        f"{BASE}/sections",
        headers=superadmin_headers,
        json={"year_id": year["id"], "level_id": g6["id"], "code": "A"},
    )
    assert other_level.status_code == 201, other_level.text

    invalid_homeroom = await client.post(
        f"{BASE}/sections",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "level_id": g5["id"],
            "code": "B",
            "homeroom_user_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert invalid_homeroom.status_code == 422
    assert invalid_homeroom.json()["error"]["message_key"] == "error.academics.homeroom_invalid"

    updated = await client.patch(
        f"{BASE}/sections/{section['id']}",
        headers=superadmin_headers,
        json={"code": "B", "capacity": 50, "row_version": section["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["code"] == "B"
    assert updated.json()["capacity"] == 50

    stale = await client.patch(
        f"{BASE}/sections/{section['id']}",
        headers=superadmin_headers,
        json={"capacity": 10, "row_version": section["row_version"]},
    )
    assert stale.status_code == 409

    by_year = await client.get(f"{BASE}/sections", headers=superadmin_headers, params={"year_id": year["id"]})
    assert by_year.status_code == 200
    assert by_year.json()["total"] == 2

    by_level = await client.get(
        f"{BASE}/sections",
        headers=superadmin_headers,
        params={"year_id": year["id"], "level_id": g5["id"]},
    )
    assert by_level.json()["total"] == 1
    assert by_level.json()["items"][0]["code"] == "B"

    deleted = await client.delete(
        f"{BASE}/sections/{section['id']}",
        headers=superadmin_headers,
        params={"row_version": updated.json()["row_version"]},
    )
    assert deleted.status_code == 200
    assert (
        await client.get(f"{BASE}/sections/{section['id']}", headers=superadmin_headers)
    ).status_code == 404

    restored = await client.post(f"{BASE}/sections/{section['id']}/restore", headers=superadmin_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["code"] == "B"

    actions = await _activity(client, superadmin_headers)
    assert "academics.sections.create" in actions
    assert "academics.sections.update" in actions
    assert "academics.sections.delete" in actions
    assert "academics.sections.restore" in actions


async def test_sections_respect_scope_and_closed_years(client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    g5 = await _level(client, superadmin_headers, "g5")
    g6 = await _level(client, superadmin_headers, "g6")

    for level, code in ((g5, "A"), (g6, "A")):
        response = await client.post(
            f"{BASE}/sections",
            headers=superadmin_headers,
            json={"year_id": year["id"], "level_id": level["id"], "code": code},
        )
        assert response.status_code == 201, response.text

    await client.put(
        f"{BASE}/scope",
        headers=superadmin_headers,
        json={"first_level": 1, "last_level": 5},
    )
    scoped = await client.get(f"{BASE}/sections", headers=superadmin_headers)
    assert scoped.status_code == 200
    assert [item["level_code"] for item in scoped.json()["items"]] == ["g5"]

    manager_view = await client.get(f"{BASE}/sections", headers=superadmin_headers, params={"scope": "all"})
    assert manager_view.json()["total"] == 2

    blocked_level = await client.post(
        f"{BASE}/sections",
        headers=superadmin_headers,
        json={"year_id": year["id"], "level_id": g6["id"], "code": "B"},
    )
    assert blocked_level.status_code == 404
    assert blocked_level.json()["error"]["message_key"] == "error.academics.level_out_of_scope"

    await client.put(
        f"{BASE}/scope",
        headers=superadmin_headers,
        json={"first_level": 0, "last_level": 12},
    )

    opened = await client.post(f"{BASE}/academic-years/{year['id']}/open", headers=superadmin_headers)
    assert opened.status_code == 200, opened.text
    closed = await client.post(f"{BASE}/academic-years/{year['id']}/close", headers=superadmin_headers)
    assert closed.status_code == 200, closed.text

    frozen = await client.post(
        f"{BASE}/sections",
        headers=superadmin_headers,
        json={"year_id": year["id"], "level_id": g5["id"], "code": "C"},
    )
    assert frozen.status_code == 409
    assert frozen.json()["error"]["message_key"] == "error.academics.year_closed"

    listed = await client.get(f"{BASE}/sections", headers=superadmin_headers)
    section = listed.json()["items"][0]
    frozen_update = await client.patch(
        f"{BASE}/sections/{section['id']}",
        headers=superadmin_headers,
        json={"capacity": 30, "row_version": section["row_version"]},
    )
    assert frozen_update.status_code == 409
    frozen_delete = await client.delete(f"{BASE}/sections/{section['id']}", headers=superadmin_headers)
    assert frozen_delete.status_code == 409


async def test_subject_and_section_permissions(client, app, seeded, superadmin_headers) -> None:
    year = await _year(client, superadmin_headers)
    g5 = await _level(client, superadmin_headers, "g5")
    section = await client.post(
        f"{BASE}/sections",
        headers=superadmin_headers,
        json={"year_id": year["id"], "level_id": g5["id"], "code": "A"},
    )
    assert section.status_code == 201, section.text

    viewer = await create_role(app, "academics_viewer_2", [("academics.view", "all"), ("ai.use", "all")])
    viewer_email = unique_email("academics-viewer")
    await create_user(app, viewer_email, roles=[viewer.key])
    headers = await login(client, viewer_email)

    assert (await client.get(f"{BASE}/subjects", headers=headers)).status_code == 200
    assert (await client.get(f"{BASE}/sections", headers=headers)).status_code == 200
    assert (await client.get(f"{BASE}/subject-groups", headers=headers)).status_code == 200

    assert (
        await client.post(f"{BASE}/subjects", headers=headers, json={"code": "art", "name": "Art"})
    ).status_code == 403
    assert (
        await client.put(
            f"{BASE}/levels/{g5['id']}/subjects",
            headers=headers,
            json={"subjects": []},
        )
    ).status_code == 403
    assert (
        await client.post(
            f"{BASE}/sections",
            headers=headers,
            json={"year_id": year["id"], "level_id": g5["id"], "code": "B"},
        )
    ).status_code == 403
    assert (
        await client.get(f"{BASE}/subjects", headers=headers, params={"include_inactive": True})
    ).status_code == 403
