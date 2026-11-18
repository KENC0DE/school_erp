"""P2-04: curriculum profiles, starter data, duplication and applying."""

from __future__ import annotations

from tests.conftest import create_role, create_user, login, unique_email

BASE = "/api/v1/academics"
ACTIVITY = "/api/v1/audit/activity"


async def _year(client, headers, code: str = "2026-2027", **overrides) -> dict:
    response = await client.post(
        f"{BASE}/academic-years",
        headers=headers,
        json={
            "code": code,
            "name": code.replace("-", "/"),
            "start_date": "2026-09-11",
            "end_date": "2027-06-30",
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _profiles(client, headers) -> dict[str, dict]:
    response = await client.get(f"{BASE}/curriculum-profiles", headers=headers)
    assert response.status_code == 200, response.text
    return {item["code"]: item for item in response.json()["items"]}


async def _level(client, headers, code: str) -> dict:
    response = await client.get(f"{BASE}/levels", headers=headers, params={"scope": "all"})
    assert response.status_code == 200
    return next(item for item in response.json()["items"] if item["code"] == code)


async def _subject(client, headers, code: str) -> dict:
    response = await client.get(f"{BASE}/subjects", headers=headers)
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["code"] == code)


async def _activity(client, headers) -> list[str]:
    response = await client.get(ACTIVITY, headers=headers, params={"limit": 200})
    assert response.status_code == 200, response.text
    return [item["action"] for item in response.json()["items"]]


async def test_starter_profiles_are_seeded_and_flagged_unverified(client, superadmin_headers, seeded) -> None:
    profiles = await _profiles(client, superadmin_headers)
    assert set(profiles) == {"ethiopian_national", "private_custom", "international_generic"}

    ethiopian = profiles["ethiopian_national"]
    assert ethiopian["is_starter"] is True
    assert ethiopian["is_verified"] is False
    assert ethiopian["in_use"] is False
    assert ethiopian["term_system"] == "semester"

    levels = {level["level_code"]: level for level in ethiopian["levels"]}
    assert "g1" in levels
    assert "kg1" not in levels
    g1_codes = {subject["code"] for subject in levels["g1"]["subjects"]}
    assert {"amharic", "english", "mathematics", "environmental_science"} <= g1_codes

    generic = {level["level_code"] for level in profiles["international_generic"]["levels"]}
    assert {"kg1", "kg2", "kg3", "g1", "g12"} <= generic

    subjects = await client.get(f"{BASE}/subjects", headers=superadmin_headers)
    assert {"amharic", "english", "mathematics", "foreign_language"} <= {
        item["code"] for item in subjects.json()["items"]
    }


async def test_duplicate_and_edit_profile_with_audit(client, superadmin_headers, seeded) -> None:
    source = (await _profiles(client, superadmin_headers))["ethiopian_national"]

    duplicated = await client.post(
        f"{BASE}/curriculum-profiles/{source['id']}/duplicate",
        headers=superadmin_headers,
        json={"code": "our_school", "name": "Our School Curriculum", "name_am": "የትምህርት ቤታችን"},
    )
    assert duplicated.status_code == 201, duplicated.text
    copy = duplicated.json()
    assert copy["is_starter"] is False
    assert copy["is_verified"] is True
    assert len(copy["levels"]) > 0
    source_levels = {level["level_code"]: level for level in source["levels"]}
    copy_levels = {level["level_code"]: level for level in copy["levels"]}
    assert [item["code"] for item in copy_levels["g1"]["subjects"]] == [
        item["code"] for item in source_levels["g1"]["subjects"]
    ]

    updated = await client.patch(
        f"{BASE}/curriculum-profiles/{copy['id']}",
        headers=superadmin_headers,
        json={
            "name": "Our Curriculum 2027",
            "description": "Edited by the academic committee",
            "term_system": "quarter",
            "row_version": copy["row_version"],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Our Curriculum 2027"
    assert updated.json()["term_system"] == "quarter"
    assert updated.json()["row_version"] == copy["row_version"] + 1

    g1 = await _level(client, superadmin_headers, "g1")
    english = await _subject(client, superadmin_headers, "english")
    maths = await _subject(client, superadmin_headers, "mathematics")
    replaced = await client.put(
        f"{BASE}/curriculum-profiles/{copy['id']}/levels/{g1['id']}/subjects",
        headers=superadmin_headers,
        json={
            "subjects": [
                {"subject_id": english["id"], "credit": 2},
                {"subject_id": maths["id"], "credit": 3},
            ],
            "reason": "School weighting",
        },
    )
    assert replaced.status_code == 200, replaced.text
    levels = {level["level_code"]: level for level in replaced.json()["levels"]}
    assert [(item["code"], item["credit"]) for item in levels["g1"]["subjects"]] == [
        ("english", 2),
        ("mathematics", 3),
    ]

    actions = await _activity(client, superadmin_headers)
    assert "academics.curriculum.duplicate" in actions
    assert "academics.curriculum.update" in actions
    assert "academics.curriculum.subjects.replace" in actions


async def test_custom_profile_crud_soft_delete_and_starter_protection(
    client, superadmin_headers, seeded
) -> None:
    starter = (await _profiles(client, superadmin_headers))["ethiopian_national"]
    blocked = await client.delete(
        f"{BASE}/curriculum-profiles/{starter['id']}",
        headers=superadmin_headers,
        params={"row_version": starter["row_version"]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["message_key"] == "error.academics.curriculum_starter_protected"

    created = await client.post(
        f"{BASE}/curriculum-profiles",
        headers=superadmin_headers,
        json={"code": "blank", "name": "Blank", "term_system": "quarter"},
    )
    assert created.status_code == 201, created.text
    profile = created.json()
    assert profile["levels"] == []
    assert profile["is_starter"] is False

    duplicate = await client.post(
        f"{BASE}/curriculum-profiles",
        headers=superadmin_headers,
        json={"code": "blank", "name": "Another"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "error.academics.curriculum_code_taken"

    deleted = await client.delete(
        f"{BASE}/curriculum-profiles/{profile['id']}",
        headers=superadmin_headers,
        params={"row_version": profile["row_version"], "reason": "No longer offered"},
    )
    assert deleted.status_code == 200, deleted.text
    assert (
        await client.get(f"{BASE}/curriculum-profiles/{profile['id']}", headers=superadmin_headers)
    ).status_code == 404
    assert "blank" not in await _profiles(client, superadmin_headers)

    restored = await client.post(
        f"{BASE}/curriculum-profiles/{profile['id']}/restore", headers=superadmin_headers
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["term_system"] == "quarter"

    inactive = await client.patch(
        f"{BASE}/curriculum-profiles/{profile['id']}",
        headers=superadmin_headers,
        json={"is_active": False, "row_version": restored.json()["row_version"]},
    )
    assert inactive.status_code == 200, inactive.text
    assert "blank" not in await _profiles(client, superadmin_headers)
    listed = await client.get(
        f"{BASE}/curriculum-profiles", headers=superadmin_headers, params={"include_inactive": True}
    )
    assert "blank" in {item["code"] for item in listed.json()["items"]}

    actions = await _activity(client, superadmin_headers)
    assert "academics.curriculum.delete" in actions
    assert "academics.curriculum.restore" in actions


async def test_apply_preview_then_apply_from_chosen_year(client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    g1 = await _level(client, superadmin_headers, "g1")
    maths = await _subject(client, superadmin_headers, "mathematics")
    music = await _subject(client, superadmin_headers, "music")

    assigned = await client.put(
        f"{BASE}/levels/{g1['id']}/subjects",
        headers=superadmin_headers,
        json={
            "subjects": [
                {"subject_id": maths["id"], "credit": 1},
                {"subject_id": music["id"], "credit": 1},
            ]
        },
    )
    assert assigned.status_code == 200, assigned.text

    ethiopian = (await _profiles(client, superadmin_headers))["ethiopian_national"]
    preview = await client.post(
        f"{BASE}/curriculum-profiles/{ethiopian['id']}/apply",
        headers=superadmin_headers,
        json={"year_id": year["id"], "confirm": False},
    )
    assert preview.status_code == 200, preview.text
    summary = preview.json()
    assert summary["applied"] is False
    assert summary["term_system_matches"] is True
    assert summary["assignments_added"] > 0
    assert summary["assignments_removed"] == 1
    assert "g1" in summary["changed_levels"]

    unchanged = await client.get(f"{BASE}/levels/{g1['id']}/subjects", headers=superadmin_headers)
    assert unchanged.json()["total"] == 2

    applied = await client.post(
        f"{BASE}/curriculum-profiles/{ethiopian['id']}/apply",
        headers=superadmin_headers,
        json={"year_id": year["id"], "confirm": True, "reason": "Setup wizard"},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["applied"] is True

    after = await client.get(f"{BASE}/levels/{g1['id']}/subjects", headers=superadmin_headers)
    codes = {item["code"] for item in after.json()["items"]}
    assert "music" not in codes
    assert {"amharic", "english", "mathematics", "environmental_science"} <= codes

    year_detail = await client.get(f"{BASE}/academic-years/{year['id']}", headers=superadmin_headers)
    assert year_detail.json()["curriculum_profile_id"] == ethiopian["id"]
    assert year_detail.json()["curriculum_profile_code"] == "ethiopian_national"

    second = await client.post(
        f"{BASE}/curriculum-profiles/{ethiopian['id']}/apply",
        headers=superadmin_headers,
        json={"year_id": year["id"], "confirm": False},
    )
    assert second.json()["levels_changed"] == 0
    assert second.json()["assignments_added"] == 0
    assert second.json()["assignments_removed"] == 0
    assert second.json()["credits_changed"] == 0

    profile = await client.get(f"{BASE}/curriculum-profiles/{ethiopian['id']}", headers=superadmin_headers)
    assert profile.json()["in_use"] is True
    assert "academics.curriculum.apply" in await _activity(client, superadmin_headers)


async def test_apply_guards_term_system_closed_year_and_inactive_profile(
    client, superadmin_headers, seeded
) -> None:
    year = await _year(client, superadmin_headers)
    g1 = await _level(client, superadmin_headers, "g1")
    english = await _subject(client, superadmin_headers, "english")

    quarter = (
        await client.post(
            f"{BASE}/curriculum-profiles",
            headers=superadmin_headers,
            json={"code": "quarters", "name": "Quarters", "term_system": "quarter"},
        )
    ).json()
    await client.put(
        f"{BASE}/curriculum-profiles/{quarter['id']}/levels/{g1['id']}/subjects",
        headers=superadmin_headers,
        json={"subjects": [{"subject_id": english["id"], "credit": 1}]},
    )

    mismatch = await client.post(
        f"{BASE}/curriculum-profiles/{quarter['id']}/apply",
        headers=superadmin_headers,
        json={"year_id": year["id"], "confirm": True},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["message_key"] == "error.academics.curriculum_term_mismatch"
    assert mismatch.json()["error"]["details"]["year_term_system"] == "semester"

    # Creating the year with the profile adopts its term system and replaces
    # the global level-subject map instead of merging with the old bundle.
    music = await _subject(client, superadmin_headers, "music")
    await client.put(
        f"{BASE}/levels/{g1['id']}/subjects",
        headers=superadmin_headers,
        json={"subjects": [{"subject_id": music["id"], "credit": 1}]},
    )
    quarter_year = await _year(
        client,
        superadmin_headers,
        code="2027-2028",
        start_date="2027-09-10",
        end_date="2028-06-30",
        curriculum_profile_id=quarter["id"],
    )
    assert quarter_year["term_system"] == "quarter"
    assert len(quarter_year["terms"]) == 4
    assert quarter_year["curriculum_profile_code"] == "quarters"
    seeded_subjects = await client.get(f"{BASE}/levels/{g1['id']}/subjects", headers=superadmin_headers)
    assert [item["code"] for item in seeded_subjects.json()["items"]] == ["english"]

    await client.patch(
        f"{BASE}/curriculum-profiles/{quarter['id']}",
        headers=superadmin_headers,
        json={"is_active": False, "row_version": quarter["row_version"]},
    )
    inactive = await client.post(
        f"{BASE}/curriculum-profiles/{quarter['id']}/apply",
        headers=superadmin_headers,
        json={"year_id": year["id"], "confirm": False},
    )
    assert inactive.status_code == 409
    assert inactive.json()["error"]["message_key"] == "error.academics.curriculum_inactive"

    opened = await client.post(f"{BASE}/academic-years/{year['id']}/open", headers=superadmin_headers)
    assert opened.status_code == 200, opened.text
    closed = await client.post(f"{BASE}/academic-years/{year['id']}/close", headers=superadmin_headers)
    assert closed.status_code == 200, closed.text
    ethiopian = (await _profiles(client, superadmin_headers))["ethiopian_national"]
    frozen = await client.post(
        f"{BASE}/curriculum-profiles/{ethiopian['id']}/apply",
        headers=superadmin_headers,
        json={"year_id": year["id"], "confirm": False},
    )
    assert frozen.status_code == 409
    assert frozen.json()["error"]["message_key"] == "error.academics.year_closed"


async def test_profile_in_use_cannot_be_deleted(client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    profile = (
        await client.post(
            f"{BASE}/curriculum-profiles",
            headers=superadmin_headers,
            json={"code": "temporary", "name": "Temporary"},
        )
    ).json()
    applied = await client.post(
        f"{BASE}/curriculum-profiles/{profile['id']}/apply",
        headers=superadmin_headers,
        json={"year_id": year["id"], "confirm": True},
    )
    assert applied.status_code == 200, applied.text

    blocked = await client.delete(f"{BASE}/curriculum-profiles/{profile['id']}", headers=superadmin_headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["message_key"] == "error.academics.curriculum_in_use"


async def test_curriculum_permissions(client, app, seeded, superadmin_headers) -> None:
    viewer = await create_role(app, "curriculum_viewer", [("academics.view", "all"), ("ai.use", "all")])
    email = unique_email("curriculum-viewer")
    await create_user(app, email, roles=[viewer.key])
    headers = await login(client, email)

    listed = await client.get(f"{BASE}/curriculum-profiles", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 3

    created = await client.post(
        f"{BASE}/curriculum-profiles",
        headers=headers,
        json={"code": "viewer_made", "name": "Nope"},
    )
    assert created.status_code == 403

    year = await _year(client, superadmin_headers)
    ethiopian = (await _profiles(client, superadmin_headers))["ethiopian_national"]
    applied = await client.post(
        f"{BASE}/curriculum-profiles/{ethiopian['id']}/apply",
        headers=headers,
        json={"year_id": year["id"], "confirm": False},
    )
    assert applied.status_code == 403

    hidden = await client.get(
        f"{BASE}/curriculum-profiles", headers=headers, params={"include_inactive": True}
    )
    assert hidden.status_code == 403
