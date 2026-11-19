"""P3-03: leave types, yearly balances, requests, approval and calendar."""

from __future__ import annotations

from tests.conftest import create_user, login, unique_email

BASE = "/api/v1/staff"
ACADEMICS = "/api/v1/academics"
ACTIVITY = "/api/v1/audit/activity"

PERSON = {
    "given_name_en": "Meron",
    "father_name_en": "Tesfaye",
    "grandfather_name_en": "Girma",
    "given_name_am": "መረን",
    "father_name_am": "ተስፋዬ",
    "grandfather_name_am": "ግርማ",
    "sex": "female",
    "date_of_birth": "1990-03-04",
}


def _person(**overrides) -> dict:
    values = dict(PERSON)
    values.update(overrides)
    return values


async def _year(client, headers, code: str = "2026-2027") -> dict:
    response = await client.post(
        f"{ACADEMICS}/academic-years",
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


async def _leave_type(
    client,
    headers,
    code: str,
    *,
    days: float = 10,
    requires_approval: bool = True,
    counts_against_balance: bool = True,
) -> dict:
    response = await client.post(
        f"{BASE}/leave-types",
        headers=headers,
        json={
            "code": code,
            "name": code.replace("_", " ").title(),
            "annual_entitlement_days": days,
            "requires_approval": requires_approval,
            "counts_against_balance": counts_against_balance,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _staff(
    client,
    headers,
    number: str,
    *,
    given_name: str = "Meron",
    department_id: str | None = None,
) -> dict:
    response = await client.post(
        BASE,
        headers=headers,
        json={
            "person": _person(given_name_en=given_name, given_name_am=f"መረን {given_name}"),
            "staff_number": number,
            "hire_date": "2026-09-01",
            "department_id": department_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _account(client, headers, staff_id: str, user_id: str) -> None:
    response = await client.post(
        f"{BASE}/{staff_id}/account",
        headers=headers,
        json={"user_id": user_id},
    )
    assert response.status_code == 200, response.text


async def _request(
    client,
    headers,
    *,
    staff_id: str,
    year_id: str,
    leave_type_id: str,
    start_date: str = "2026-10-05",
    end_date: str = "2026-10-07",
    is_half_day: bool = False,
    reason: str | None = "Family matter",
):
    return await client.post(
        f"{BASE}/leave-requests",
        headers=headers,
        json={
            "staff_id": staff_id,
            "year_id": year_id,
            "leave_type_id": leave_type_id,
            "start_date": start_date,
            "end_date": end_date,
            "is_half_day": is_half_day,
            "reason": reason,
        },
    )


async def test_leave_types_and_balances_are_managed_and_audited(client, superadmin_headers, seeded) -> None:
    create = await _leave_type(client, superadmin_headers, "annual", days=20)
    assert create["annual_entitlement_days"] == 20.0
    assert create["row_version"] == 1

    duplicate = await client.post(
        f"{BASE}/leave-types",
        headers=superadmin_headers,
        json={"code": "annual", "name": "Annual leave"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "staff.error.leave_type_code_taken"

    invalid_step = await client.post(
        f"{BASE}/leave-types",
        headers=superadmin_headers,
        json={"code": "odd", "name": "Odd", "annual_entitlement_days": 1.25},
    )
    assert invalid_step.status_code == 422

    updated = await client.patch(
        f"{BASE}/leave-types/{create['id']}",
        headers=superadmin_headers,
        json={"name": "Annual leave", "annual_entitlement_days": 22.5, "row_version": 1},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Annual leave"
    assert updated.json()["annual_entitlement_days"] == 22.5
    stale = await client.patch(
        f"{BASE}/leave-types/{create['id']}",
        headers=superadmin_headers,
        json={"name": "Stale", "row_version": 1},
    )
    assert stale.status_code == 409

    retired = await client.patch(
        f"{BASE}/leave-types/{create['id']}",
        headers=superadmin_headers,
        json={"is_active": False, "row_version": 2},
    )
    assert retired.status_code == 200
    listed = await client.get(f"{BASE}/leave-types", headers=superadmin_headers)
    assert listed.json()["total"] == 0
    all_types = await client.get(
        f"{BASE}/leave-types",
        headers=superadmin_headers,
        params={"include_inactive": True},
    )
    assert [item["code"] for item in all_types.json()["items"]] == ["annual"]

    year = await _year(client, superadmin_headers)
    staff = await _staff(client, superadmin_headers, "STF-8001")

    missing_version = await client.put(
        f"{BASE}/leave-balances",
        headers=superadmin_headers,
        json={
            "staff_id": staff["id"],
            "year_id": year["id"],
            "leave_type_id": create["id"],
            "entitled_days": 22.5,
        },
    )
    assert missing_version.status_code == 200, missing_version.text
    balance = missing_version.json()
    assert balance["entitled_days"] == 22.5
    assert balance["remaining_days"] == 22.5
    assert balance["staff_number"] == "STF-8001"

    without_version = await client.put(
        f"{BASE}/leave-balances",
        headers=superadmin_headers,
        json={
            "staff_id": staff["id"],
            "year_id": year["id"],
            "leave_type_id": create["id"],
            "entitled_days": 22.5,
        },
    )
    assert without_version.status_code == 422
    assert without_version.json()["error"]["code"] == "VERSION_REQUIRED"

    adjusted = await client.put(
        f"{BASE}/leave-balances",
        headers=superadmin_headers,
        json={
            "staff_id": staff["id"],
            "year_id": year["id"],
            "leave_type_id": create["id"],
            "entitled_days": 22.5,
            "carried_days": 2.5,
            "adjustment_days": -1,
            "row_version": balance["row_version"],
        },
    )
    assert adjusted.status_code == 200, adjusted.text
    assert adjusted.json()["carried_days"] == 2.5
    assert adjusted.json()["remaining_days"] == 24.0

    listed_balance = await client.get(
        f"{BASE}/leave-balances",
        headers=superadmin_headers,
        params={"staff_id": staff["id"], "year_id": year["id"]},
    )
    assert listed_balance.status_code == 200, listed_balance.text
    assert listed_balance.json()["items"][0]["leave_type_code"] == "annual"

    activity = await client.get(ACTIVITY, headers=superadmin_headers, params={"limit": 200})
    actions = {item["action"] for item in activity.json()["items"]}
    assert {
        "staff.leave_types.create",
        "staff.leave_types.update",
        "staff.leave_balances.create",
        "staff.leave_balances.update",
    } <= actions


async def test_leave_request_workflow_respects_balance_and_audits(
    client, app, superadmin_headers, seeded
) -> None:
    year = await _year(client, superadmin_headers)
    leave_type = await _leave_type(client, superadmin_headers, "annual", days=10)
    email = unique_email("leave.teacher")
    user = await create_user(app, email, roles=["teacher"])
    staff = await _staff(client, superadmin_headers, "STF-8101", given_name="Selam")
    await _account(client, superadmin_headers, staff["id"], str(user.id))
    headers = await login(client, email)

    created = await _request(
        client,
        headers,
        staff_id=staff["id"],
        year_id=year["id"],
        leave_type_id=leave_type["id"],
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    assert draft["status"] == "draft"
    assert draft["days"] == 3.0

    edited = await client.patch(
        f"{BASE}/leave-requests/{draft['id']}",
        headers=headers,
        json={"reason": "Updated reason", "row_version": draft["row_version"]},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["reason"] == "Updated reason"
    assert edited.json()["days"] == 3.0

    submitted = await client.post(f"{BASE}/leave-requests/{draft['id']}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"

    pending = await client.get(
        f"{BASE}/leave-balances",
        headers=headers,
        params={"staff_id": staff["id"], "year_id": year["id"]},
    )
    assert pending.json()["items"][0]["pending_days"] == 3.0
    assert pending.json()["items"][0]["remaining_days"] == 7.0

    approved = await client.post(
        f"{BASE}/leave-requests/{draft['id']}/approve",
        headers=superadmin_headers,
        json={"note": "Enjoy"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["decision_note"] == "Enjoy"
    assert approved.json()["decided_by_name"]

    used = await client.get(
        f"{BASE}/leave-balances",
        headers=headers,
        params={"staff_id": staff["id"], "year_id": year["id"]},
    )
    assert used.json()["items"][0]["used_days"] == 3.0
    assert used.json()["items"][0]["remaining_days"] == 7.0

    overlap = await _request(
        client,
        headers,
        staff_id=staff["id"],
        year_id=year["id"],
        leave_type_id=leave_type["id"],
        start_date="2026-10-06",
        end_date="2026-10-08",
    )
    assert overlap.status_code == 409
    assert overlap.json()["error"]["message_key"] == "staff.error.leave_overlap"

    bad_half = await _request(
        client,
        headers,
        staff_id=staff["id"],
        year_id=year["id"],
        leave_type_id=leave_type["id"],
        start_date="2026-10-13",
        end_date="2026-10-14",
        is_half_day=True,
    )
    assert bad_half.status_code == 422

    half = await _request(
        client,
        headers,
        staff_id=staff["id"],
        year_id=year["id"],
        leave_type_id=leave_type["id"],
        start_date="2026-10-12",
        end_date="2026-10-12",
        is_half_day=True,
    )
    assert half.status_code == 201, half.text
    assert half.json()["days"] == 0.5
    await client.post(f"{BASE}/leave-requests/{half.json()['id']}/submit", headers=headers)
    await client.post(f"{BASE}/leave-requests/{half.json()['id']}/approve", headers=superadmin_headers)

    too_long = await _request(
        client,
        headers,
        staff_id=staff["id"],
        year_id=year["id"],
        leave_type_id=leave_type["id"],
        start_date="2026-11-02",
        end_date="2026-11-13",
    )
    assert too_long.status_code == 201, too_long.text
    exceeded = await client.post(f"{BASE}/leave-requests/{too_long.json()['id']}/submit", headers=headers)
    assert exceeded.status_code == 422
    assert exceeded.json()["error"]["message_key"] == "staff.error.leave_balance_exceeded"

    rejected = await _request(
        client,
        headers,
        staff_id=staff["id"],
        year_id=year["id"],
        leave_type_id=leave_type["id"],
        start_date="2026-12-01",
        end_date="2026-12-02",
    )
    await client.post(f"{BASE}/leave-requests/{rejected.json()['id']}/submit", headers=headers)
    decided = await client.post(
        f"{BASE}/leave-requests/{rejected.json()['id']}/reject",
        headers=superadmin_headers,
        json={"note": "Coverage needed"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "rejected"
    assert decided.json()["decision_note"] == "Coverage needed"

    cancelling = await _request(
        client,
        headers,
        staff_id=staff["id"],
        year_id=year["id"],
        leave_type_id=leave_type["id"],
        start_date="2027-01-11",
        end_date="2027-01-11",
    )
    await client.post(f"{BASE}/leave-requests/{cancelling.json()['id']}/submit", headers=headers)
    await client.post(
        f"{BASE}/leave-requests/{cancelling.json()['id']}/approve",
        headers=superadmin_headers,
    )
    before_cancel = await client.get(
        f"{BASE}/leave-balances",
        headers=headers,
        params={"staff_id": staff["id"], "year_id": year["id"]},
    )
    assert before_cancel.json()["items"][0]["remaining_days"] == 5.5
    cancelled = await client.post(
        f"{BASE}/leave-requests/{cancelling.json()['id']}/cancel",
        headers=headers,
        params={"reason": "Plans changed"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    after_cancel = await client.get(
        f"{BASE}/leave-balances",
        headers=headers,
        params={"staff_id": staff["id"], "year_id": year["id"]},
    )
    assert after_cancel.json()["items"][0]["remaining_days"] == 6.5

    automatic = await _leave_type(
        client,
        superadmin_headers,
        "compassionate",
        days=0,
        requires_approval=False,
        counts_against_balance=False,
    )
    automatic_request = await _request(
        client,
        headers,
        staff_id=staff["id"],
        year_id=year["id"],
        leave_type_id=automatic["id"],
        start_date="2027-02-01",
        end_date="2027-02-03",
    )
    assert automatic_request.status_code == 201, automatic_request.text
    auto_submitted = await client.post(
        f"{BASE}/leave-requests/{automatic_request.json()['id']}/submit",
        headers=headers,
    )
    assert auto_submitted.status_code == 200, auto_submitted.text
    assert auto_submitted.json()["status"] == "approved"
    assert auto_submitted.json()["decided_at"] is not None

    activity = await client.get(ACTIVITY, headers=superadmin_headers, params={"limit": 200})
    actions = {item["action"] for item in activity.json()["items"]}
    assert {
        "staff.leave_requests.create",
        "staff.leave_requests.submit",
        "staff.leave_requests.approve",
        "staff.leave_requests.reject",
        "staff.leave_requests.cancel",
    } <= actions


async def test_leave_scopes_isolate_self_department_and_calendar(
    client, app, superadmin_headers, seeded
) -> None:
    year = await _year(client, superadmin_headers)
    leave_type = await _leave_type(client, superadmin_headers, "annual", days=10)
    first_dept = await client.post(
        f"{BASE}/departments",
        headers=superadmin_headers,
        json={"code": "science", "name": "Science"},
    )
    second_dept = await client.post(
        f"{BASE}/departments",
        headers=superadmin_headers,
        json={"code": "languages", "name": "Languages"},
    )
    assert first_dept.status_code == 201 and second_dept.status_code == 201

    first_staff = await _staff(
        client,
        superadmin_headers,
        "STF-8201",
        given_name="Selam",
        department_id=first_dept.json()["id"],
    )
    second_staff = await _staff(
        client,
        superadmin_headers,
        "STF-8202",
        given_name="Dawit",
        department_id=second_dept.json()["id"],
    )
    head_staff = await _staff(
        client,
        superadmin_headers,
        "STF-8203",
        given_name="Hana",
        department_id=first_dept.json()["id"],
    )

    first_email = unique_email("dept.teacher")
    second_email = unique_email("other.teacher")
    head_email = unique_email("head")
    first_user = await create_user(app, first_email, roles=["teacher"])
    second_user = await create_user(app, second_email, roles=["teacher"])
    head_user = await create_user(app, head_email, roles=["department_head"])
    await _account(client, superadmin_headers, first_staff["id"], str(first_user.id))
    await _account(client, superadmin_headers, second_staff["id"], str(second_user.id))
    await _account(client, superadmin_headers, head_staff["id"], str(head_user.id))
    first_headers = await login(client, first_email)
    second_headers = await login(client, second_email)
    head_headers = await login(client, head_email)

    first_request = await _request(
        client,
        superadmin_headers,
        staff_id=first_staff["id"],
        year_id=year["id"],
        leave_type_id=leave_type["id"],
        start_date="2026-10-05",
        end_date="2026-10-06",
    )
    second_request = await _request(
        client,
        superadmin_headers,
        staff_id=second_staff["id"],
        year_id=year["id"],
        leave_type_id=leave_type["id"],
        start_date="2026-10-12",
        end_date="2026-10-13",
    )
    assert first_request.status_code == 201 and second_request.status_code == 201
    for request in (first_request, second_request):
        submitted = await client.post(
            f"{BASE}/leave-requests/{request.json()['id']}/submit",
            headers=superadmin_headers,
        )
        assert submitted.status_code == 200, submitted.text

    own = await client.get(f"{BASE}/leave-requests", headers=first_headers)
    assert [item["id"] for item in own.json()["items"]] == [first_request.json()["id"]]

    head_view = await client.get(f"{BASE}/leave-requests", headers=head_headers)
    assert [item["id"] for item in head_view.json()["items"]] == [first_request.json()["id"]]

    denied = await client.get(f"{BASE}/leave-requests/{second_request.json()['id']}", headers=head_headers)
    assert denied.status_code == 403
    assert denied.json()["error"]["message_key"] == "error.scope_denied"

    approved = await client.post(
        f"{BASE}/leave-requests/{first_request.json()['id']}/approve",
        headers=head_headers,
    )
    assert approved.status_code == 200, approved.text
    outside = await client.post(
        f"{BASE}/leave-requests/{second_request.json()['id']}/approve",
        headers=head_headers,
    )
    assert outside.status_code == 403

    forbidden_request = await _request(
        client,
        first_headers,
        staff_id=second_staff["id"],
        year_id=year["id"],
        leave_type_id=leave_type["id"],
        start_date="2026-11-02",
        end_date="2026-11-03",
    )
    assert forbidden_request.status_code == 403

    first_balances = await client.get(f"{BASE}/leave-balances", headers=first_headers)
    assert first_balances.status_code == 200, first_balances.text
    assert {item["staff_id"] for item in first_balances.json()["items"]} == {first_staff["id"]}
    head_balances = await client.get(
        f"{BASE}/leave-balances",
        headers=head_headers,
        params={"staff_id": first_staff["id"]},
    )
    assert head_balances.status_code == 200, head_balances.text
    hidden_balance = await client.get(
        f"{BASE}/leave-balances",
        headers=head_headers,
        params={"staff_id": second_staff["id"]},
    )
    assert hidden_balance.status_code == 403

    calendar = await client.get(
        f"{BASE}/leave-calendar",
        headers=head_headers,
        params={"from_date": "2026-10-01", "to_date": "2026-10-31"},
    )
    assert calendar.status_code == 200, calendar.text
    assert [item["id"] for item in calendar.json()["items"]] == [first_request.json()["id"]]

    second_calendar = await client.get(
        f"{BASE}/leave-calendar",
        headers=second_headers,
        params={"from_date": "2026-10-01", "to_date": "2026-10-31"},
    )
    assert [item["id"] for item in second_calendar.json()["items"]] == [second_request.json()["id"]]
    reversed_range = await client.get(
        f"{BASE}/leave-calendar",
        headers=second_headers,
        params={"from_date": "2026-10-31", "to_date": "2026-10-01"},
    )
    assert reversed_range.status_code == 422
