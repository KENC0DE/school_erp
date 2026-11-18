"""P2-02: academic years, term systems, open/close workflow and EC/GC display."""

from __future__ import annotations

from datetime import date, timedelta

from tests.conftest import create_role, create_user, login, unique_email

BASE = "/api/v1/academics/academic-years"
SETTINGS = "/api/v1/settings"
ACTIVITY = "/api/v1/audit/activity"

SEMESTER_YEAR = {"start_date": "2026-09-11", "end_date": "2027-06-30"}


def _year_payload(code: str = "2026-2027", **overrides) -> dict:
    return {
        "code": code,
        "name": code.replace("-", "/"),
        "name_am": "የትምህርት ዓመት",
        **SEMESTER_YEAR,
        **overrides,
    }


async def _create(client, headers, **overrides) -> dict:
    response = await client.post(BASE, headers=headers, json=_year_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


async def test_semester_year_autosplits_terms_with_ec_display(client, superadmin_headers, seeded) -> None:
    year = await _create(client, superadmin_headers)

    assert year["code"] == "2026-2027"
    assert year["term_system"] == "semester"
    assert year["status"] == "draft"
    assert year["current_term_id"] is None
    assert [term["number"] for term in year["terms"]] == [1, 2]
    assert [term["name"] for term in year["terms"]] == ["Semester 1", "Semester 2"]
    assert year["terms"][0]["name_am"] == "ሴሚስተር 1"
    assert all(term["status"] == "pending" for term in year["terms"])

    # The auto split covers the whole year without gaps or overlaps.
    assert year["terms"][0]["start_date"] == "2026-09-11"
    assert year["terms"][-1]["end_date"] == "2027-06-30"
    for first, second in zip(year["terms"], year["terms"][1:], strict=False):
        assert date.fromisoformat(second["start_date"]) == date.fromisoformat(first["end_date"]) + timedelta(
            days=1
        )

    # GC storage plus the Ethiopian equivalent and a display label.
    assert year["start_date_ec"] == "2019-01-01"
    assert year["start_date_display"] == "Meskerem 1, 2019 (11 Sep 2026)"
    assert year["terms"][0]["start_date_ec"] == "2019-01-01"

    # The default calendar is configurable; Ethiopian-only hides the GC label.
    switched = await client.put(
        f"{SETTINGS}/core/school_profile.calendar",
        headers=superadmin_headers,
        json={"value": "ethiopian"},
    )
    assert switched.status_code == 200, switched.text
    fetched = await client.get(f"{BASE}/{year['id']}", headers=superadmin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["start_date_display"] == "Meskerem 1, 2019"

    listed = await client.get(BASE, headers=superadmin_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


async def test_quarter_setting_drives_new_years_and_is_snapshotted(
    client, superadmin_headers, seeded
) -> None:
    semester_year = await _create(client, superadmin_headers)

    settings = await client.get(SETTINGS, headers=superadmin_headers)
    core = next(item for item in settings.json()["items"] if item["module"] == "core")
    field = next(item for item in core["fields"] if item["key"] == "academic_scope.term_system")
    assert field["type"] == "enum"
    assert field["enum"] == ["semester", "quarter"]
    assert field["value"] == "semester"

    changed = await client.put(
        f"{SETTINGS}/core/academic_scope.term_system",
        headers=superadmin_headers,
        json={"value": "quarter"},
    )
    assert changed.status_code == 200, changed.text

    quarter_year = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_year_payload(code="2027-2028", start_date="2027-09-11", end_date="2028-06-30"),
    )
    assert quarter_year.status_code == 201, quarter_year.text
    body = quarter_year.json()
    assert body["term_system"] == "quarter"
    assert [term["number"] for term in body["terms"]] == [1, 2, 3, 4]
    assert body["terms"][3]["name"] == "Quarter 4"
    assert body["terms"][0]["start_date"] == "2027-09-11"
    assert body["terms"][-1]["end_date"] == "2028-06-30"

    # The earlier year keeps its snapshot.
    old = await client.get(f"{BASE}/{semester_year['id']}", headers=superadmin_headers)
    assert old.status_code == 200
    assert old.json()["term_system"] == "semester"
    assert len(old.json()["terms"]) == 2


async def test_term_dates_are_validated_and_editable(client, superadmin_headers, seeded) -> None:
    year = await _create(client, superadmin_headers)
    first, second = year["terms"]

    narrowed = await client.patch(
        f"{BASE}/{year['id']}/terms/{first['id']}",
        headers=superadmin_headers,
        json={"name": "First semester", "end_date": "2027-01-20", "row_version": first["row_version"]},
    )
    assert narrowed.status_code == 200, narrowed.text
    assert narrowed.json()["terms"][0]["name"] == "First semester"
    assert narrowed.json()["terms"][0]["end_date"] == "2027-01-20"

    stale = await client.patch(
        f"{BASE}/{year['id']}/terms/{first['id']}",
        headers=superadmin_headers,
        json={"name": "Stale", "row_version": first["row_version"]},
    )
    assert stale.status_code == 409

    overlap = await client.patch(
        f"{BASE}/{year['id']}/terms/{second['id']}",
        headers=superadmin_headers,
        json={"start_date": "2027-01-01", "row_version": second["row_version"]},
    )
    assert overlap.status_code == 422
    assert overlap.json()["error"]["message_key"] == "error.academics.term_overlap"

    outside = await client.patch(
        f"{BASE}/{year['id']}/terms/{second['id']}",
        headers=superadmin_headers,
        json={"end_date": "2027-07-30", "row_version": second["row_version"]},
    )
    assert outside.status_code == 422
    assert outside.json()["error"]["message_key"] == "error.academics.term_outside_year"

    reversed_dates = await client.patch(
        f"{BASE}/{year['id']}/terms/{second['id']}",
        headers=superadmin_headers,
        json={"start_date": "2027-06-20", "end_date": "2027-06-01", "row_version": second["row_version"]},
    )
    assert reversed_dates.status_code == 422
    assert reversed_dates.json()["error"]["message_key"] == "error.academics.term_dates"


async def test_year_and_term_input_validation(client, superadmin_headers, seeded) -> None:
    reversed_year = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_year_payload(start_date="2027-06-30", end_date="2027-06-30"),
    )
    assert reversed_year.status_code == 422
    assert reversed_year.json()["error"]["message_key"] == "error.academics.year_dates"

    created = await _create(client, superadmin_headers)
    duplicate = await client.post(BASE, headers=superadmin_headers, json=_year_payload())
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "error.academics.year_code_taken"

    wrong_count = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_year_payload(
            code="2028-2029",
            start_date="2028-09-11",
            end_date="2029-06-30",
            terms=[
                {"name": "One", "start_date": "2028-09-11", "end_date": "2028-12-31"},
                {"name": "Two", "start_date": "2029-01-01", "end_date": "2029-03-31"},
                {"name": "Three", "start_date": "2029-04-01", "end_date": "2029-06-30"},
            ],
        ),
    )
    assert wrong_count.status_code == 422
    assert wrong_count.json()["error"]["message_key"] == "error.academics.term_count"

    outside = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_year_payload(
            code="2029-2030",
            start_date="2029-09-11",
            end_date="2030-06-30",
            terms=[
                {"name": "One", "start_date": "2029-09-01", "end_date": "2030-01-20"},
                {"name": "Two", "start_date": "2030-01-21", "end_date": "2030-06-30"},
            ],
        ),
    )
    assert outside.status_code == 422
    assert outside.json()["error"]["message_key"] == "error.academics.term_outside_year"

    out_of_order = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_year_payload(
            code="2030-2031",
            start_date="2030-09-11",
            end_date="2031-06-30",
            terms=[
                {"name": "Two", "start_date": "2031-01-21", "end_date": "2031-06-30"},
                {"name": "One", "start_date": "2030-09-11", "end_date": "2031-01-20"},
            ],
        ),
    )
    assert out_of_order.status_code == 422
    assert out_of_order.json()["error"]["message_key"] == "error.academics.term_order"

    too_short = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_year_payload(code="short", start_date="2031-09-11", end_date="2031-09-11"),
    )
    assert too_short.status_code == 422
    assert too_short.json()["error"]["message_key"] == "error.academics.year_dates"

    # A quarter year must leave at least one day per quarter.
    await client.put(
        f"{SETTINGS}/core/academic_scope.term_system",
        headers=superadmin_headers,
        json={"value": "quarter"},
    )
    tiny = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_year_payload(code="tiny", start_date="2031-09-11", end_date="2031-09-13"),
    )
    assert tiny.status_code == 422
    assert tiny.json()["error"]["message_key"] == "error.academics.year_too_short"

    # Moving the year's end is allowed only while terms still fit inside it.
    shortened = await client.patch(
        f"{BASE}/{created['id']}",
        headers=superadmin_headers,
        json={"end_date": "2027-05-31", "row_version": created["row_version"]},
    )
    assert shortened.status_code == 422
    assert shortened.json()["error"]["message_key"] == "error.academics.term_outside_year"


async def test_open_close_workflow_and_audit(client, superadmin_headers, seeded) -> None:
    year = await _create(client, superadmin_headers)
    first, second = year["terms"]

    early_term = await client.post(
        f"{BASE}/{year['id']}/terms/{first['id']}/open", headers=superadmin_headers
    )
    assert early_term.status_code == 409
    assert early_term.json()["error"]["message_key"] == "error.academics.year_not_open"

    opened = await client.post(f"{BASE}/{year['id']}/open", headers=superadmin_headers)
    assert opened.status_code == 200, opened.text
    assert opened.json()["status"] == "open"

    renamed = await client.patch(
        f"{BASE}/{year['id']}/terms/{second['id']}",
        headers=superadmin_headers,
        json={"name": "Second semester", "row_version": second["row_version"]},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["terms"][1]["name"] == "Second semester"

    draft_year = await _create(client, superadmin_headers, code="2027-2028")
    second_open = await client.post(f"{BASE}/{draft_year['id']}/open", headers=superadmin_headers)
    assert second_open.status_code == 409
    assert second_open.json()["error"]["message_key"] == "error.academics.year_already_open"

    listed = await client.get(BASE, headers=superadmin_headers)
    assert listed.json()["current_year_id"] == year["id"]

    term_opened = await client.post(
        f"{BASE}/{year['id']}/terms/{first['id']}/open", headers=superadmin_headers
    )
    assert term_opened.status_code == 200, term_opened.text
    assert term_opened.json()["current_term_id"] == first["id"]
    assert term_opened.json()["terms"][0]["status"] == "open"

    competing = await client.post(
        f"{BASE}/{year['id']}/terms/{second['id']}/open", headers=superadmin_headers
    )
    assert competing.status_code == 409
    assert competing.json()["error"]["message_key"] == "error.academics.term_already_open"

    term_closed = await client.post(
        f"{BASE}/{year['id']}/terms/{first['id']}/close", headers=superadmin_headers
    )
    assert term_closed.status_code == 200
    assert term_closed.json()["terms"][0]["status"] == "closed"
    assert term_closed.json()["current_term_id"] is None

    # Reopening a closed term is explicit and audited.
    reopened = await client.post(
        f"{BASE}/{year['id']}/terms/{first['id']}/open",
        headers=superadmin_headers,
        params={"reason": "Correction window"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["terms"][0]["status"] == "open"

    closed = await client.post(
        f"{BASE}/{year['id']}/close", headers=superadmin_headers, params={"reason": "Year end"}
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    assert all(term["status"] == "closed" for term in closed.json()["terms"])
    assert closed.json()["current_term_id"] is None

    frozen = await client.patch(
        f"{BASE}/{year['id']}",
        headers=superadmin_headers,
        json={"name": "Renamed", "row_version": closed.json()["row_version"]},
    )
    assert frozen.status_code == 409
    assert frozen.json()["error"]["message_key"] == "error.academics.year_closed"

    frozen_term = await client.patch(
        f"{BASE}/{year['id']}/terms/{second['id']}",
        headers=superadmin_headers,
        json={"name": "Renamed", "row_version": second["row_version"]},
    )
    assert frozen_term.status_code == 409

    undeletable = await client.delete(f"{BASE}/{year['id']}", headers=superadmin_headers)
    assert undeletable.status_code == 409
    assert undeletable.json()["error"]["message_key"] == "error.academics.year_not_draft"

    draft_close = await client.post(f"{BASE}/{draft_year['id']}/close", headers=superadmin_headers)
    assert draft_close.status_code == 409
    assert draft_close.json()["error"]["message_key"] == "error.academics.year_not_open"

    activity = await client.get(ACTIVITY, headers=superadmin_headers, params={"limit": 100})
    actions = [item["action"] for item in activity.json()["items"]]
    assert "academics.years.create" in actions
    assert "academics.years.open" in actions
    assert "academics.years.close" in actions
    assert "academics.terms.open" in actions
    assert "academics.terms.close" in actions
    assert "academics.terms.update" in actions

    chain = await client.get("/api/v1/audit/verify", headers=superadmin_headers)
    assert chain.status_code == 200
    assert chain.json()["ok"] is True


async def test_draft_year_soft_delete_and_restore_keeps_terms(client, superadmin_headers, seeded) -> None:
    year = await _create(client, superadmin_headers)

    deleted = await client.delete(
        f"{BASE}/{year['id']}",
        headers=superadmin_headers,
        params={"row_version": year["row_version"], "reason": "Created by mistake"},
    )
    assert deleted.status_code == 200, deleted.text
    assert (await client.get(f"{BASE}/{year['id']}", headers=superadmin_headers)).status_code == 404
    assert (await client.get(BASE, headers=superadmin_headers)).json()["total"] == 0

    restored = await client.post(f"{BASE}/{year['id']}/restore", headers=superadmin_headers)
    assert restored.status_code == 200, restored.text
    assert [term["number"] for term in restored.json()["terms"]] == [1, 2]

    activity = await client.get(ACTIVITY, headers=superadmin_headers, params={"limit": 100})
    actions = [item["action"] for item in activity.json()["items"]]
    assert "academics.years.delete" in actions
    assert "academics.years.restore" in actions


async def test_academic_years_permissions_and_module_gate(client, app, seeded, superadmin_headers) -> None:
    created = await _create(client, superadmin_headers)

    viewer = await create_role(app, "years_viewer", [("academics.view", "all"), ("ai.use", "all")])
    viewer_email = unique_email("years-viewer")
    await create_user(app, viewer_email, roles=[viewer.key])
    headers = await login(client, viewer_email)

    listed = await client.get(BASE, headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    denied_create = await client.post(BASE, headers=headers, json=_year_payload(code="other"))
    assert denied_create.status_code == 403
    denied_patch = await client.patch(
        f"{BASE}/{created['id']}",
        headers=headers,
        json={"name": "Nope", "row_version": 1},
    )
    assert denied_patch.status_code == 403

    disabled = await client.put(
        "/api/v1/system/modules/academics",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    blocked = await client.get(BASE, headers=superadmin_headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "MODULE_DISABLED"
