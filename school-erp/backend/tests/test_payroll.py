"""P3-05: optional payroll sub-module over HTTP.

Rates used here are fixtures that stand in for an accountant's validated rule
set. The product ships no starter rates.
"""

from __future__ import annotations

from tests.conftest import create_role, create_user, login, unique_email

PAYROLL = "/api/v1/payroll"
STAFF = "/api/v1/staff"
ACTIVITY = "/api/v1/audit/activity"
MODULES = "/api/v1/system/modules"

PERSON = {
    "given_name_en": "Hanna",
    "father_name_en": "Desta",
    "grandfather_name_en": "Alemu",
    "given_name_am": "ሐና",
    "father_name_am": "ደስታ",
    "grandfather_name_am": "አለሙ",
    "sex": "female",
    "date_of_birth": "1990-02-18",
}


async def _enable(client, headers) -> None:
    response = await client.put(
        f"{MODULES}/payroll", headers=headers, json={"enabled": True}
    )
    assert response.status_code == 200, response.text


async def _staff(client, headers, number: str = "STF-9001", **overrides) -> dict:
    payload = {
        "person": PERSON,
        "staff_number": number,
        "hire_date": "2026-08-01",
    }
    payload.update(overrides)
    response = await client.post(STAFF, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _contract(client, headers, staff_id: str, salary_santim: int) -> dict:
    response = await client.post(
        f"{STAFF}/{staff_id}/contracts",
        headers=headers,
        json={
            "type": "permanent",
            "status": "active",
            "start_date": "2026-09-01",
            "salary_santim": salary_santim,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _component(client, headers, code: str = "housing", **overrides) -> dict:
    payload = {"code": code, "name": "Housing allowance", "kind": "earning"}
    payload.update(overrides)
    response = await client.post(f"{PAYROLL}/components", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _rule_set(
    client, headers, code: str = "2026-v1", *, effective_from: str = "2026-01-01"
) -> dict:
    response = await client.post(
        f"{PAYROLL}/rule-sets",
        headers=headers,
        json={
            "code": code,
            "name": "2026 statutory rules",
            "effective_from": effective_from,
            "verified_by_accountant": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _rule(client, headers, rule_set_id: str, key: str = "income_tax", **overrides) -> dict:
    payload = {
        "key": key,
        "name": key.replace("_", " ").title(),
        "kind": "income_tax",
        "payer": "employee",
        "method": "percent",
        "base": "taxable",
        "rate_basis_points": 1500,
    }
    payload.update(overrides)
    response = await client.post(
        f"{PAYROLL}/rule-sets/{rule_set_id}/rules", headers=headers, json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _seeded_rule_set(client, headers) -> dict:
    """A minimal accountant-style set: 15% tax, 7% employee and 11% employer pension."""
    rule_set = await _rule_set(client, headers)
    await _rule(client, headers, rule_set["id"], "income_tax")
    await _rule(
        client,
        headers,
        rule_set["id"],
        "pension",
        kind="pension",
        base="pensionable",
        rate_basis_points=700,
    )
    await _rule(
        client,
        headers,
        rule_set["id"],
        "employer_pension",
        kind="pension",
        payer="employer",
        base="pensionable",
        rate_basis_points=1100,
    )
    activated = await client.post(
        f"{PAYROLL}/rule-sets/{rule_set['id']}/activate", headers=headers
    )
    assert activated.status_code == 200, activated.text
    return activated.json()


async def _activity(client, headers) -> set[str]:
    response = await client.get(ACTIVITY, headers=headers, params={"limit": 200})
    assert response.status_code == 200, response.text
    return {item["action"] for item in response.json()["items"]}


# ------------------------------------------------------------ module gating


async def test_payroll_is_an_optional_module(client, superadmin_headers, seeded) -> None:
    staff = await _staff(client, superadmin_headers)

    disabled = await client.get(f"{PAYROLL}/components", headers=superadmin_headers)
    assert disabled.status_code == 403
    assert disabled.json()["error"]["code"] == "MODULE_DISABLED"

    await _enable(client, superadmin_headers)
    enabled = await client.get(f"{PAYROLL}/components", headers=superadmin_headers)
    assert enabled.status_code == 200, enabled.text
    # No starter rates or components are shipped.
    assert enabled.json() == {"items": [], "total": 0}

    # Staff records are independent of payroll being installed.
    detail = await client.get(f"{STAFF}/{staff['id']}", headers=superadmin_headers)
    assert detail.status_code == 200


# --------------------------------------------------------------- components


async def test_components_are_managed_audited_and_restorable(
    client, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    housing = await _component(client, superadmin_headers)
    assert housing["code"] == "housing"
    assert housing["kind"] == "earning"
    assert housing["is_taxable"] is True
    assert housing["row_version"] == 1

    duplicate = await client.post(
        f"{PAYROLL}/components",
        headers=superadmin_headers,
        json={"code": "housing", "name": "Duplicate"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "payroll.error.component_code_taken"

    updated = await client.patch(
        f"{PAYROLL}/components/{housing['id']}",
        headers=superadmin_headers,
        json={"name": "Housing", "is_taxable": False, "row_version": 1},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Housing"
    assert updated.json()["is_taxable"] is False
    assert updated.json()["row_version"] == 2

    stale = await client.patch(
        f"{PAYROLL}/components/{housing['id']}",
        headers=superadmin_headers,
        json={"name": "Stale", "row_version": 1},
    )
    assert stale.status_code == 409

    deleted = await client.delete(
        f"{PAYROLL}/components/{housing['id']}", headers=superadmin_headers
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert (
        await client.get(f"{PAYROLL}/components/{housing['id']}", headers=superadmin_headers)
    ).status_code == 404

    restored = await client.post(
        f"{PAYROLL}/components/{housing['id']}/restore", headers=superadmin_headers
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["code"] == "housing"

    actions = await _activity(client, superadmin_headers)
    assert {
        "payroll.components.create",
        "payroll.components.update",
        "payroll.components.delete",
        "payroll.components.restore",
    } <= actions


async def test_a_component_assigned_to_staff_cannot_be_deleted(
    client, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    staff = await _staff(client, superadmin_headers)
    component = await _component(client, superadmin_headers)
    assignment = await client.post(
        f"{PAYROLL}/staff/{staff['id']}/components",
        headers=superadmin_headers,
        json={
            "component_id": component["id"],
            "amount_santim": 1_000_00,
            "starts_on": "2026-09-01",
        },
    )
    assert assignment.status_code == 201, assignment.text

    blocked = await client.delete(
        f"{PAYROLL}/components/{component['id']}", headers=superadmin_headers
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["message_key"] == "payroll.error.component_in_use"

    removed = await client.delete(
        f"{PAYROLL}/staff/{staff['id']}/components/{assignment.json()['id']}",
        headers=superadmin_headers,
    )
    assert removed.status_code == 200, removed.text
    now_allowed = await client.delete(
        f"{PAYROLL}/components/{component['id']}", headers=superadmin_headers
    )
    assert now_allowed.status_code == 200, now_allowed.text


async def test_staff_components_require_one_amount_form_and_may_not_overlap(
    client, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    staff = await _staff(client, superadmin_headers)
    component = await _component(client, superadmin_headers)

    both = await client.post(
        f"{PAYROLL}/staff/{staff['id']}/components",
        headers=superadmin_headers,
        json={
            "component_id": component["id"],
            "amount_santim": 1_000,
            "rate_basis_points": 500,
            "starts_on": "2026-09-01",
        },
    )
    assert both.status_code == 422
    neither = await client.post(
        f"{PAYROLL}/staff/{staff['id']}/components",
        headers=superadmin_headers,
        json={"component_id": component["id"], "starts_on": "2026-09-01"},
    )
    assert neither.status_code == 422

    first = await client.post(
        f"{PAYROLL}/staff/{staff['id']}/components",
        headers=superadmin_headers,
        json={
            "component_id": component["id"],
            "rate_basis_points": 1000,
            "starts_on": "2026-09-01",
            "ends_on": "2026-12-31",
        },
    )
    assert first.status_code == 201, first.text
    assert first.json()["component_code"] == "housing"
    assert first.json()["rate_basis_points"] == 1000
    assert first.json()["amount_santim"] is None

    overlap = await client.post(
        f"{PAYROLL}/staff/{staff['id']}/components",
        headers=superadmin_headers,
        json={
            "component_id": component["id"],
            "amount_santim": 500_00,
            "starts_on": "2026-12-01",
        },
    )
    assert overlap.status_code == 409
    assert overlap.json()["error"]["message_key"] == "payroll.error.component_overlap"

    next_year = await client.post(
        f"{PAYROLL}/staff/{staff['id']}/components",
        headers=superadmin_headers,
        json={
            "component_id": component["id"],
            "amount_santim": 500_00,
            "starts_on": "2027-01-01",
        },
    )
    assert next_year.status_code == 201, next_year.text

    switched = await client.patch(
        f"{PAYROLL}/staff/{staff['id']}/components/{first.json()['id']}",
        headers=superadmin_headers,
        json={
            "amount_santim": 750_00,
            "rate_basis_points": None,
            "row_version": 1,
        },
    )
    assert switched.status_code == 200, switched.text
    assert switched.json()["amount_santim"] == 750_00
    assert switched.json()["rate_basis_points"] is None

    listed = await client.get(
        f"{PAYROLL}/staff/{staff['id']}/components", headers=superadmin_headers
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 2

    removed = await client.delete(
        f"{PAYROLL}/staff/{staff['id']}/components/{first.json()['id']}",
        headers=superadmin_headers,
    )
    assert removed.status_code == 200, removed.text
    restored = await client.post(
        f"{PAYROLL}/staff/{staff['id']}/components/{first.json()['id']}/restore",
        headers=superadmin_headers,
    )
    assert restored.status_code == 200, restored.text


# ----------------------------------------------------------------- rule sets


async def test_rule_sets_are_configurable_versioned_and_frozen_once_active(
    client, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    rule_set = await _rule_set(client, superadmin_headers)
    assert rule_set["status"] == "draft"
    assert rule_set["verified_by_accountant"] is True
    assert rule_set["accountant_notice"] == "payroll.rules.accountant_notice"
    assert rule_set["rules"] == []

    tax = await _rule(client, superadmin_headers, rule_set["id"])
    assert tax["method"] == "percent"
    assert tax["rate_basis_points"] == 1500

    progressive = await client.post(
        f"{PAYROLL}/rule-sets/{rule_set['id']}/rules",
        headers=superadmin_headers,
        json={
            "key": "banded_tax",
            "name": "Banded tax",
            "kind": "income_tax",
            "base": "taxable",
            "method": "brackets",
            "brackets": [
                {"lower_santim": 0, "upper_santim": 1_000_00, "rate_basis_points": 1000},
                {"lower_santim": 1_000_00, "upper_santim": None, "rate_basis_points": 2000},
            ],
        },
    )
    assert progressive.status_code == 201, progressive.text
    assert progressive.json()["brackets"][1]["upper_santim"] is None

    gap = await client.post(
        f"{PAYROLL}/rule-sets/{rule_set['id']}/rules",
        headers=superadmin_headers,
        json={
            "key": "broken",
            "name": "Broken",
            "method": "brackets",
            "brackets": [
                {"lower_santim": 0, "upper_santim": 100, "rate_basis_points": 1000},
                {"lower_santim": 200, "upper_santim": None, "rate_basis_points": 1000},
            ],
        },
    )
    assert gap.status_code == 422

    duplicate = await client.post(
        f"{PAYROLL}/rule-sets/{rule_set['id']}/rules",
        headers=superadmin_headers,
        json={"key": "income_tax", "name": "Duplicate", "rate_basis_points": 1000},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "payroll.error.rule_key_taken"

    edited = await client.patch(
        f"{PAYROLL}/rule-sets/{rule_set['id']}/rules/{tax['id']}",
        headers=superadmin_headers,
        json={"rate_basis_points": 1600, "row_version": 1},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["rate_basis_points"] == 1600

    activated = await client.post(
        f"{PAYROLL}/rule-sets/{rule_set['id']}/activate", headers=superadmin_headers
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"

    frozen = await client.patch(
        f"{PAYROLL}/rule-sets/{rule_set['id']}/rules/{tax['id']}",
        headers=superadmin_headers,
        json={"rate_basis_points": 1700, "row_version": 2},
    )
    assert frozen.status_code == 409
    assert frozen.json()["error"]["message_key"] == "payroll.error.rule_set_frozen"

    second = await _rule_set(client, superadmin_headers, "2027-v1", effective_from="2027-01-01")
    await _rule(client, superadmin_headers, second["id"])
    upgraded = await client.post(
        f"{PAYROLL}/rule-sets/{second['id']}/activate", headers=superadmin_headers
    )
    assert upgraded.status_code == 200, upgraded.text
    assert upgraded.json()["status"] == "active"

    current = await client.get(f"{PAYROLL}/rule-sets", headers=superadmin_headers)
    assert [item["code"] for item in current.json()["items"]] == ["2027-v1"]
    all_sets = await client.get(
        f"{PAYROLL}/rule-sets", headers=superadmin_headers, params={"include_archived": True}
    )
    assert {item["code"] for item in all_sets.json()["items"]} == {"2026-v1", "2027-v1"}

    active_delete = await client.delete(
        f"{PAYROLL}/rule-sets/{second['id']}", headers=superadmin_headers
    )
    assert active_delete.status_code == 409
    assert (
        active_delete.json()["error"]["message_key"] == "payroll.error.rule_set_active_delete"
    )
    archived = await client.post(
        f"{PAYROLL}/rule-sets/{second['id']}/archive", headers=superadmin_headers
    )
    assert archived.status_code == 200, archived.text
    deleted = await client.delete(
        f"{PAYROLL}/rule-sets/{second['id']}", headers=superadmin_headers
    )
    assert deleted.status_code == 200, deleted.text


async def test_activating_an_empty_rule_set_is_rejected(
    client, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    rule_set = await _rule_set(client, superadmin_headers, "empty")
    response = await client.post(
        f"{PAYROLL}/rule-sets/{rule_set['id']}/activate", headers=superadmin_headers
    )
    assert response.status_code == 422
    assert response.json()["error"]["message_key"] == "payroll.error.rule_set_empty"


# ------------------------------------------------------------------ runs


async def test_run_calculates_payslips_and_finalizes_with_audit(
    client, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    rule_set = await _seeded_rule_set(client, superadmin_headers)

    paid = await _staff(client, superadmin_headers, "STF-9101")
    await _contract(client, superadmin_headers, paid["id"], 10_000_00)
    unpayable = await _staff(
        client,
        superadmin_headers,
        "STF-9102",
        person={
            **PERSON,
            "given_name_en": "Bereket",
            "date_of_birth": "1991-03-09",
        },
    )

    housing = await _component(
        client,
        superadmin_headers,
        "housing",
        name="Housing allowance",
        is_taxable=True,
        is_pensionable=True,
    )
    assigned = await client.post(
        f"{PAYROLL}/staff/{paid['id']}/components",
        headers=superadmin_headers,
        json={
            "component_id": housing["id"],
            "rate_basis_points": 1000,
            "starts_on": "2026-09-01",
        },
    )
    assert assigned.status_code == 201, assigned.text

    loan = await _component(
        client,
        superadmin_headers,
        "loan",
        name="Staff loan",
        kind="deduction",
        is_taxable=False,
        is_pensionable=False,
    )
    await client.post(
        f"{PAYROLL}/staff/{paid['id']}/components",
        headers=superadmin_headers,
        json={
            "component_id": loan["id"],
            "amount_santim": 100_00,
            "starts_on": "2026-09-01",
        },
    )

    created = await client.post(
        f"{PAYROLL}/runs",
        headers=superadmin_headers,
        json={"period_year": 2026, "period_month": 9},
    )
    assert created.status_code == 201, created.text
    run = created.json()
    assert run["status"] == "draft"
    assert run["rule_set_code"] == rule_set["code"]

    duplicate = await client.post(
        f"{PAYROLL}/runs",
        headers=superadmin_headers,
        json={"period_year": 2026, "period_month": 9},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "payroll.error.run_exists"

    calculated = await client.post(
        f"{PAYROLL}/runs/{run['id']}/calculate", headers=superadmin_headers
    )
    assert calculated.status_code == 200, calculated.text
    summary = calculated.json()
    assert summary["status"] == "calculated"
    assert summary["payslip_count"] == 1
    assert summary["skipped_count"] == 1

    gross = 10_000_00 + 1_000_00
    tax = 1650_00
    pension = 770_00
    deductions = tax + pension + 100_00
    assert summary["gross_santim"] == gross
    assert summary["deductions_santim"] == deductions
    assert summary["net_santim"] == gross - deductions
    assert summary["employer_santim"] == 1210_00

    payslips = await client.get(
        f"{PAYROLL}/runs/{run['id']}/payslips", headers=superadmin_headers
    )
    assert payslips.status_code == 200, payslips.text
    assert payslips.json()["total"] == 1
    slip = payslips.json()["items"][0]
    assert slip["staff_id"] == paid["id"]
    assert slip["staff_number"] == "STF-9101"
    assert slip["base_salary_santim"] == 10_000_00
    assert slip["taxable_santim"] == gross
    assert slip["pensionable_santim"] == gross
    assert slip["net_santim"] == gross - deductions
    lines = {line["code"]: line for line in slip["lines"]}
    assert lines["basic"]["amount_santim"] == 10_000_00
    assert lines["housing"]["amount_santim"] == 1_000_00
    assert lines["income_tax"]["amount_santim"] == tax
    assert lines["pension"]["amount_santim"] == pension
    assert lines["employer_pension"]["kind"] == "employer_contribution"
    assert lines["loan"]["amount_santim"] == 100_00

    unfunded = await client.get(
        f"{PAYROLL}/runs/{run['id']}/staff/{unpayable['id']}/payslip",
        headers=superadmin_headers,
    )
    assert unfunded.status_code == 404

    by_staff = await client.get(
        f"{PAYROLL}/runs/{run['id']}/staff/{paid['id']}/payslip",
        headers=superadmin_headers,
    )
    assert by_staff.status_code == 200, by_staff.text
    assert by_staff.json()["id"] == slip["id"]

    one = await client.get(
        f"{PAYROLL}/runs/{run['id']}/payslips/{slip['id']}", headers=superadmin_headers
    )
    assert one.status_code == 200

    finalized = await client.post(
        f"{PAYROLL}/runs/{run['id']}/finalize", headers=superadmin_headers
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["status"] == "finalized"

    again = await client.post(
        f"{PAYROLL}/runs/{run['id']}/calculate", headers=superadmin_headers
    )
    assert again.status_code == 409
    assert again.json()["error"]["message_key"] == "payroll.error.run_finalized"
    delete_final = await client.delete(
        f"{PAYROLL}/runs/{run['id']}", headers=superadmin_headers
    )
    assert delete_final.status_code == 409

    labelled = await client.post(
        f"{PAYROLL}/runs",
        headers=superadmin_headers,
        json={
            "period_year": 2026,
            "period_month": 10,
            "rule_set_id": rule_set["id"],
        },
    )
    assert labelled.status_code == 201, labelled.text
    assert labelled.json()["rule_set_id"] == rule_set["id"]

    actions = await _activity(client, superadmin_headers)
    assert {
        "payroll.runs.create",
        "payroll.runs.calculate",
        "payroll.runs.finalize",
    } <= actions


async def test_recalculation_replaces_payslips_without_unique_conflicts(
    client, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    await _seeded_rule_set(client, superadmin_headers)
    staff = await _staff(client, superadmin_headers, "STF-9201")
    await _contract(client, superadmin_headers, staff["id"], 5_000_00)

    run = (
        await client.post(
            f"{PAYROLL}/runs",
            headers=superadmin_headers,
            json={"period_year": 2026, "period_month": 11},
        )
    ).json()

    first = await client.post(
        f"{PAYROLL}/runs/{run['id']}/calculate", headers=superadmin_headers
    )
    assert first.status_code == 200, first.text
    second = await client.post(
        f"{PAYROLL}/runs/{run['id']}/calculate", headers=superadmin_headers
    )
    assert second.status_code == 200, second.text
    assert second.json()["payslip_count"] == 1

    payslips = await client.get(
        f"{PAYROLL}/runs/{run['id']}/payslips", headers=superadmin_headers
    )
    assert payslips.json()["total"] == 1

    deleted = await client.delete(
        f"{PAYROLL}/runs/{run['id']}", headers=superadmin_headers
    )
    assert deleted.status_code == 200, deleted.text
    gone = await client.get(f"{PAYROLL}/runs/{run['id']}", headers=superadmin_headers)
    assert gone.status_code == 404


async def test_run_needs_an_active_rule_set(client, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    no_set = await client.post(
        f"{PAYROLL}/runs",
        headers=superadmin_headers,
        json={"period_year": 2026, "period_month": 9},
    )
    assert no_set.status_code == 422
    assert no_set.json()["error"]["message_key"] == "payroll.error.no_active_rule_set"

    draft = await _rule_set(client, superadmin_headers, "draft-only")
    with_draft = await client.post(
        f"{PAYROLL}/runs",
        headers=superadmin_headers,
        json={"period_year": 2026, "period_month": 9, "rule_set_id": draft["id"]},
    )
    assert with_draft.status_code == 422
    assert with_draft.json()["error"]["message_key"] == "payroll.error.rule_set_not_active_start"


# ------------------------------------------------------------- permissions


async def test_payroll_endpoints_require_payroll_permissions(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)

    await create_role(app, "payroll_reader", [("payroll.view", "all")])
    reader_email = unique_email("payroll.reader")
    await create_user(app, reader_email, roles=["payroll_reader"])
    reader = await login(client, reader_email)

    assert (await client.get(f"{PAYROLL}/components", headers=reader)).status_code == 200
    assert (
        await client.post(
            f"{PAYROLL}/components", headers=reader, json={"code": "x", "name": "X"}
        )
    ).status_code == 403
    assert (
        await client.post(
            f"{PAYROLL}/runs",
            headers=reader,
            json={"period_year": 2026, "period_month": 9},
        )
    ).status_code == 403

    await create_role(
        app, "payroll_manager", [("payroll.view", "all"), ("payroll.manage", "all")]
    )
    manager_email = unique_email("payroll.manager")
    await create_user(app, manager_email, roles=["payroll_manager"])
    manager = await login(client, manager_email)

    assert (
        await client.post(
            f"{PAYROLL}/components",
            headers=manager,
            json={"code": "manager_made", "name": "Manager made"},
        )
    ).status_code == 201
    assert (
        await client.post(
            f"{PAYROLL}/runs",
            headers=manager,
            json={"period_year": 2026, "period_month": 9},
        )
    ).status_code == 403

    await create_role(app, "payroll_runner", [("payroll.view", "all"), ("payroll.run", "all")])
    runner_email = unique_email("payroll.runner")
    await create_user(app, runner_email, roles=["payroll_runner"])
    runner = await login(client, runner_email)
    assert (
        await client.post(
            f"{PAYROLL}/components", headers=runner, json={"code": "no", "name": "No"}
        )
    ).status_code == 403
