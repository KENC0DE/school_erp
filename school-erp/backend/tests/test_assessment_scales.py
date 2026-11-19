"""P4-11: grade scale CRUD, bands, assignments and the test tool."""

from __future__ import annotations

from core.audit.models import AuditLog
from sqlalchemy import select

BASE = "/api/v1/assessment"
MODULES = "/api/v1/system/modules"
ACADEMICS = "/api/v1/academics"


async def _enable(client, headers) -> None:
    response = await client.put(f"{MODULES}/assessment", headers=headers, json={"enabled": True})
    assert response.status_code == 200, response.text


async def _level(client, headers, code: str = "g5") -> dict:
    response = await client.get(f"{ACADEMICS}/levels", headers=headers, params={"scope": "all"})
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["code"] == code)


def _band(low: str, high: str, label: str, **overrides) -> dict:
    payload = {
        "min_value": low,
        "max_value": high,
        "label": label,
        "is_pass": label != "F",
        "gpa_points": "0" if label == "F" else "3",
    }
    payload.update(overrides)
    return payload


def _bands() -> list[dict]:
    return [
        _band("0", "50", "F"),
        _band("50", "75", "C"),
        _band("75", "85", "C+"),
        _band("85", "100", "A"),
    ]


async def _scale(client, headers, *, name: str, **overrides) -> dict:
    payload = {
        "name": name,
        "bands": _bands(),
        "is_default": False,
        **overrides,
    }
    response = await client.post(f"{BASE}/scales", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_scale_tests_boundaries_and_rejects_gaps(client, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    scale = await _scale(client, superadmin_headers, name="Lower primary scale")

    assert scale["version"] == 1
    assert scale["is_default"] is False
    assert [band["label"] for band in scale["bands"]] == ["F", "C", "C+", "A"]
    assert scale["bands"][2]["min_value"] == "75"
    assert scale["bands"][2]["max_value"] == "85"

    listed = await client.get(f"{BASE}/scales", headers=superadmin_headers)
    assert listed.status_code == 200
    assert "Lower primary scale" in {item["name"] for item in listed.json()["items"]}

    async def label(value: str) -> str:
        response = await client.post(
            f"{BASE}/scales/{scale['id']}/test",
            headers=superadmin_headers,
            json={"value": value},
        )
        assert response.status_code == 200, response.text
        return response.json()["label"]

    assert await label("0") == "F"
    assert await label("74.99") == "C"
    assert await label("75") == "C+"
    assert await label("84.999999") == "C+"
    assert await label("85") == "A"
    assert await label("100") == "A"

    outside = await client.post(
        f"{BASE}/scales/{scale['id']}/test",
        headers=superadmin_headers,
        json={"value": "100.01"},
    )
    assert outside.status_code == 422
    assert outside.json()["error"]["message_key"] == "assessment.error.value_out_of_range"

    gap = await client.post(
        f"{BASE}/scales",
        headers=superadmin_headers,
        json={
            "name": "Gap scale",
            "bands": [_band("0", "40", "F"), _band("50", "100", "A")],
        },
    )
    assert gap.status_code == 422
    assert gap.json()["error"]["message_key"] == "assessment.error.grade_bands"

    overlap = await client.post(
        f"{BASE}/scales",
        headers=superadmin_headers,
        json={
            "name": "Overlap scale",
            "bands": [_band("0", "60", "F"), _band("50", "100", "A")],
        },
    )
    assert overlap.status_code == 422
    assert overlap.json()["error"]["message_key"] == "assessment.error.grade_bands"


async def test_update_scale_bumps_version_and_guards_concurrency(client, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    scale = await _scale(client, superadmin_headers, name="Versioned scale")

    response = await client.patch(
        f"{BASE}/scales/{scale['id']}",
        headers=superadmin_headers,
        json={
            "row_version": scale["row_version"],
            "bands": [
                _band("0", "50", "F"),
                _band("50", "75", "C"),
                _band("75", "90", "C+"),
                _band("90", "100", "A"),
            ],
            "reason": "Widen the C+ band",
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["version"] == 2
    assert updated["row_version"] == scale["row_version"] + 1
    assert updated["bands"][2]["max_value"] == "90"

    stale = await client.patch(
        f"{BASE}/scales/{scale['id']}",
        headers=superadmin_headers,
        json={"row_version": scale["row_version"], "name": "Stale edit"},
    )
    assert stale.status_code == 409

    bad = await client.patch(
        f"{BASE}/scales/{scale['id']}",
        headers=superadmin_headers,
        json={
            "row_version": updated["row_version"],
            "bands": [_band("0", "60", "F"), _band("70", "100", "A")],
        },
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["message_key"] == "assessment.error.grade_bands"


async def test_default_scale_and_context_assignments(client, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    scale = await _scale(client, superadmin_headers, name="School default", is_default=True)

    listed = (await client.get(f"{BASE}/scales", headers=superadmin_headers)).json()["items"]
    defaults = [item for item in listed if item["is_default"]]
    assert [item["id"] for item in defaults] == [scale["id"]]

    assigned = await client.post(
        f"{BASE}/scale-assignments",
        headers=superadmin_headers,
        json={
            "scale_id": scale["id"],
            "context": "level",
            "level_id": level["id"],
            "notes": "Upper primary uses the school bands",
        },
    )
    assert assigned.status_code == 201, assigned.text
    assignment = assigned.json()
    assert assignment["scope_key"] == f"level:{level['id']}"
    assert assignment["level_name"] == level["name"]

    other = await _scale(client, superadmin_headers, name="Alternative scale")
    replaced = await client.post(
        f"{BASE}/scale-assignments",
        headers=superadmin_headers,
        json={"scale_id": other["id"], "context": "level", "level_id": level["id"]},
    )
    assert replaced.status_code == 201, replaced.text
    rows = (await client.get(f"{BASE}/scale-assignments", headers=superadmin_headers)).json()["items"]
    level_rows = [row for row in rows if row["context"] == "level"]
    assert len(level_rows) == 1
    assert level_rows[0]["scale_id"] == other["id"]

    in_use = await client.delete(f"{BASE}/scales/{other['id']}", headers=superadmin_headers)
    assert in_use.status_code == 409
    assert in_use.json()["error"]["message_key"] == "assessment.error.scale_in_use"

    removed = await client.delete(
        f"{BASE}/scale-assignments/{replaced.json()['id']}", headers=superadmin_headers
    )
    assert removed.status_code == 200

    as_default = await client.delete(f"{BASE}/scales/{scale['id']}", headers=superadmin_headers)
    assert as_default.status_code == 409
    assert as_default.json()["error"]["message_key"] == "assessment.error.scale_default"

    await client.patch(
        f"{BASE}/scales/{scale['id']}",
        headers=superadmin_headers,
        json={"row_version": scale["row_version"], "is_default": False},
    )
    deleted = await client.delete(f"{BASE}/scales/{scale['id']}", headers=superadmin_headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    remaining = {
        item["id"]
        for item in (await client.get(f"{BASE}/scales", headers=superadmin_headers)).json()["items"]
    }
    assert scale["id"] not in remaining


async def test_assignment_rejects_a_mismatched_target(client, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    scale = await _scale(client, superadmin_headers, name="Target validation")
    response = await client.post(
        f"{BASE}/scale-assignments",
        headers=superadmin_headers,
        json={
            "scale_id": scale["id"],
            "context": "level",
            "subject_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code == 422


async def test_scale_actions_are_audited(client, app, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    scale = await _scale(client, superadmin_headers, name="Audited scale")
    await client.patch(
        f"{BASE}/scales/{scale['id']}",
        headers=superadmin_headers,
        json={"row_version": scale["row_version"], "precision": 3},
    )

    async with app.state.db.session() as session:
        actions = (
            (
                await session.execute(
                    select(AuditLog.action).where(
                        AuditLog.action.in_(
                            [
                                "assessment.scale.create",
                                "assessment.scale.update",
                            ]
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
    assert "assessment.scale.create" in actions
    assert "assessment.scale.update" in actions
