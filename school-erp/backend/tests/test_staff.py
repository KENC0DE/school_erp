"""P3-01: staff profiles, departments, positions, contracts and qualifications."""

from __future__ import annotations

from core.auth.models import User
from sqlalchemy import select

from tests.conftest import create_role, create_user, login, unique_email

BASE = "/api/v1/staff"
ACTIVITY = "/api/v1/audit/activity"

PERSON = {
    "given_name_en": "Solomon",
    "father_name_en": "Tesfaye",
    "grandfather_name_en": "Gebre",
    "given_name_am": "ሰለሞን",
    "father_name_am": "ተስፋዬ",
    "grandfather_name_am": "ገብሬ",
    "sex": "male",
    "date_of_birth": "1988-04-12",
}


def _person(**overrides) -> dict:
    values = dict(PERSON)
    values.update(overrides)
    return values


async def _department(client, headers, code: str = "science", name: str = "Science") -> dict:
    response = await client.post(
        f"{BASE}/departments",
        headers=headers,
        json={"code": code, "name": name, "name_am": "ሳይንስ"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _position(client, headers, department_id: str | None = None, code: str = "math_teacher") -> dict:
    response = await client.post(
        f"{BASE}/positions",
        headers=headers,
        json={
            "code": code,
            "name": "Mathematics Teacher",
            "name_am": "የሒሳብ መምህር",
            "department_id": department_id,
            "is_teaching": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _staff(client, headers, number: str = "STF-0001", **overrides) -> dict:
    payload = {
        "person": _person(),
        "staff_number": number,
        "hire_date": "2026-09-01",
    }
    payload.update(overrides)
    response = await client.post(BASE, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _activity(client, headers, **params) -> list[dict]:
    response = await client.get(ACTIVITY, headers=headers, params={"limit": 200, **params})
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def test_departments_and_positions_are_managed_and_audited(client, superadmin_headers, seeded) -> None:
    department = await _department(client, superadmin_headers)
    assert department["name"] == "Science"
    assert department["name_am"] == "ሳይንስ"
    assert department["is_active"] is True

    listed = await client.get(f"{BASE}/departments", headers=superadmin_headers)
    assert [item["code"] for item in listed.json()["items"]] == ["science"]

    duplicate = await client.post(
        f"{BASE}/departments",
        headers=superadmin_headers,
        json={"code": "science", "name": "Another science"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "staff.error.department_code_taken"

    updated = await client.patch(
        f"{BASE}/departments/{department['id']}",
        headers=superadmin_headers,
        json={"name": "Natural Sciences", "row_version": department["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Natural Sciences"
    assert updated.json()["row_version"] == department["row_version"] + 1

    stale = await client.patch(
        f"{BASE}/departments/{department['id']}",
        headers=superadmin_headers,
        json={"name": "Stale write", "row_version": department["row_version"]},
    )
    assert stale.status_code == 409

    position = await _position(client, superadmin_headers, department["id"])
    assert position["department_id"] == department["id"]
    assert position["department_code"] == "science"
    assert position["is_teaching"] is True

    filtered = await client.get(
        f"{BASE}/positions",
        headers=superadmin_headers,
        params={"department_id": department["id"]},
    )
    assert [item["code"] for item in filtered.json()["items"]] == ["math_teacher"]

    inactive = await client.patch(
        f"{BASE}/positions/{position['id']}",
        headers=superadmin_headers,
        json={"is_active": False, "row_version": position["row_version"]},
    )
    assert inactive.status_code == 200, inactive.text
    visible = await client.get(f"{BASE}/positions", headers=superadmin_headers)
    assert visible.json()["items"] == []
    with_inactive = await client.get(
        f"{BASE}/positions", headers=superadmin_headers, params={"include_inactive": True}
    )
    assert [item["code"] for item in with_inactive.json()["items"]] == ["math_teacher"]

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {
        "staff.departments.create",
        "staff.departments.update",
        "staff.positions.create",
        "staff.positions.update",
    } <= actions


async def test_staff_record_combines_person_placement_and_account(
    client, app, superadmin_headers, seeded
) -> None:
    department = await _department(client, superadmin_headers)
    position = await _position(client, superadmin_headers, department["id"])

    staff = await _staff(
        client,
        superadmin_headers,
        department_id=department["id"],
        position_id=position["id"],
        notes="Joined the science department",
    )
    assert staff["staff_number"] == "STF-0001"
    assert staff["person"]["full_name"] == "Solomon Tesfaye Gebre"
    assert staff["person"]["full_name"].split(" ")[0] == "Solomon"
    assert staff["department"]["code"] == "science"
    assert staff["position"]["code"] == "math_teacher"
    assert staff["user_id"] is None
    assert staff["contracts_restricted"] is False
    assert staff["contracts"] == []

    duplicate_person = await client.post(
        BASE,
        headers=superadmin_headers,
        json={"person": _person(), "staff_number": "STF-0002"},
    )
    assert duplicate_person.status_code == 409
    assert duplicate_person.json()["error"]["message_key"] == "staff.error.person_exists"

    duplicate_number = await client.post(
        BASE,
        headers=superadmin_headers,
        json={
            "person": _person(given_name_en="Hana", given_name_am="ሐና", sex="female"),
            "staff_number": "STF-0001",
        },
    )
    assert duplicate_number.status_code == 409
    assert duplicate_number.json()["error"]["message_key"] == "staff.error.number_taken"

    searched = await client.get(f"{BASE}", headers=superadmin_headers, params={"q": "STF-0001"})
    assert [item["staff_number"] for item in searched.json()["items"]] == ["STF-0001"]

    amharic = await client.get(f"{BASE}", headers=superadmin_headers, params={"q": "ሰለሞን"})
    assert amharic.json()["total"] == 1

    updated = await client.patch(
        f"{BASE}/{staff['id']}",
        headers=superadmin_headers,
        json={"status": "on_leave", "row_version": staff["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "on_leave"

    user = await create_user(app, unique_email("staff.account"))
    linked = await client.post(
        f"{BASE}/{staff['id']}/account",
        headers=superadmin_headers,
        json={"user_id": str(user.id)},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["user_id"] == str(user.id)

    unlinked = await client.delete(f"{BASE}/{staff['id']}/account", headers=superadmin_headers)
    assert unlinked.status_code == 200, unlinked.text
    assert unlinked.json()["user_id"] is None

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {"staff.create", "staff.update", "staff.account.link", "staff.account.unlink"} <= actions


async def test_staff_number_is_generated_and_user_links_are_unique(
    client, app, superadmin_headers, seeded
) -> None:
    first = await _staff(client, superadmin_headers, number=None)  # type: ignore[arg-type]
    assert first["staff_number"].startswith("STF-")
    assert first["staff_number"].endswith("-0001")

    second = await _staff(
        client,
        superadmin_headers,
        number=None,
        person=_person(given_name_en="Marta", given_name_am="ማርታ", sex="female"),
    )
    assert second["staff_number"].endswith("-0002")

    user = await create_user(app, unique_email("staff.unique"))
    first_link = await client.post(
        f"{BASE}/{first['id']}/account",
        headers=superadmin_headers,
        json={"user_id": str(user.id)},
    )
    assert first_link.status_code == 200, first_link.text

    conflict = await client.post(
        f"{BASE}/{second['id']}/account",
        headers=superadmin_headers,
        json={"user_id": str(user.id)},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["message_key"] == "staff.error.user_taken"

    missing = await client.post(
        f"{BASE}/{second['id']}/account",
        headers=superadmin_headers,
        json={"user_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert missing.status_code == 404

    async with app.state.db.session() as session:
        not_found = (await session.execute(select(User).where(User.id == user.id))).scalar_one_or_none()
    assert not_found is not None


async def test_contracts_are_salary_guarded_and_single_active(
    client, app, superadmin_headers, seeded
) -> None:
    staff = await _staff(client, superadmin_headers)

    contract = await client.post(
        f"{BASE}/{staff['id']}/contracts",
        headers=superadmin_headers,
        json={
            "type": "permanent",
            "status": "active",
            "start_date": "2026-09-01",
            "salary_santim": 1_250_000,
            "notes": "Annual gross",
        },
    )
    assert contract.status_code == 201, contract.text
    assert contract.json()["salary_santim"] == 1_250_000
    assert isinstance(contract.json()["salary_santim"], int)

    second_active = await client.post(
        f"{BASE}/{staff['id']}/contracts",
        headers=superadmin_headers,
        json={"status": "active", "start_date": "2027-09-01"},
    )
    assert second_active.status_code == 409
    assert second_active.json()["error"]["message_key"] == "staff.error.contract_active"

    ended = await client.post(
        f"{BASE}/{staff['id']}/contracts",
        headers=superadmin_headers,
        json={"status": "ended", "start_date": "2025-09-01", "end_date": "2026-08-31"},
    )
    assert ended.status_code == 201, ended.text

    detail = await client.get(f"{BASE}/{staff['id']}", headers=superadmin_headers)
    assert detail.json()["contracts_restricted"] is False
    assert {item["status"] for item in detail.json()["contracts"]} == {"active", "ended"}

    await create_role(app, "staff_reader", [("staff.view", "all")])
    reader_email = unique_email("staff.reader")
    await create_user(app, reader_email, roles=["staff_reader"])
    reader_headers = await login(client, reader_email)

    restricted = await client.get(f"{BASE}/{staff['id']}", headers=reader_headers)
    assert restricted.status_code == 200, restricted.text
    assert restricted.json()["contracts"] == []
    assert restricted.json()["contracts_restricted"] is True

    denied = await client.get(f"{BASE}/{staff['id']}/contracts", headers=reader_headers)
    assert denied.status_code == 403

    listed = await client.get(f"{BASE}/{staff['id']}/contracts", headers=superadmin_headers)
    assert listed.json()["total"] == 2

    updated = await client.patch(
        f"{BASE}/{staff['id']}/contracts/{contract.json()['id']}",
        headers=superadmin_headers,
        json={"status": "ended", "row_version": contract.json()["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    replacement = await client.post(
        f"{BASE}/{staff['id']}/contracts",
        headers=superadmin_headers,
        json={"status": "active", "start_date": "2027-09-01"},
    )
    assert replacement.status_code == 201, replacement.text

    removed = await client.delete(
        f"{BASE}/{staff['id']}/contracts/{replacement.json()['id']}",
        headers=superadmin_headers,
        params={"reason": "Replaced by an amendment"},
    )
    assert removed.status_code == 200, removed.text
    remaining = await client.get(f"{BASE}/{staff['id']}/contracts", headers=superadmin_headers)
    assert replacement.json()["id"] not in {item["id"] for item in remaining.json()["items"]}

    restored = await client.post(
        f"{BASE}/{staff['id']}/contracts/{replacement.json()['id']}/restore",
        headers=superadmin_headers,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "active"


async def test_qualifications_support_full_crud_and_restore(client, superadmin_headers, seeded) -> None:
    staff = await _staff(client, superadmin_headers)

    created = await client.post(
        f"{BASE}/{staff['id']}/qualifications",
        headers=superadmin_headers,
        json={
            "kind": "education",
            "title": "B.Ed in Mathematics",
            "institution": "Addis Ababa University",
            "field_of_study": "Mathematics",
            "start_date": "2006-09-01",
            "end_date": "2010-06-30",
            "result": "Very good",
        },
    )
    assert created.status_code == 201, created.text
    qualification = created.json()
    assert qualification["kind"] == "education"

    invalid = await client.post(
        f"{BASE}/{staff['id']}/qualifications",
        headers=superadmin_headers,
        json={
            "title": "Broken dates",
            "start_date": "2020-01-01",
            "end_date": "2019-01-01",
        },
    )
    assert invalid.status_code == 422

    listed = await client.get(f"{BASE}/{staff['id']}/qualifications", headers=superadmin_headers)
    assert listed.json()["total"] == 1

    updated = await client.patch(
        f"{BASE}/{staff['id']}/qualifications/{qualification['id']}",
        headers=superadmin_headers,
        json={"result": "Excellent", "row_version": qualification["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["result"] == "Excellent"

    deleted = await client.delete(
        f"{BASE}/{staff['id']}/qualifications/{qualification['id']}",
        headers=superadmin_headers,
    )
    assert deleted.status_code == 200, deleted.text

    restored = await client.post(
        f"{BASE}/{staff['id']}/qualifications/{qualification['id']}/restore",
        headers=superadmin_headers,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["result"] == "Excellent"

    detail = await client.get(f"{BASE}/{staff['id']}", headers=superadmin_headers)
    assert [item["id"] for item in detail.json()["qualifications"]] == [qualification["id"]]


async def test_staff_documents_are_scoped_to_the_staff_record(client, superadmin_headers, seeded) -> None:
    first = await _staff(client, superadmin_headers)
    second = await _staff(
        client,
        superadmin_headers,
        number="STF-0002",
        person=_person(given_name_en="Hana", given_name_am="ሐና", sex="female"),
    )

    uploaded = await client.post(
        f"{BASE}/{first['id']}/documents",
        headers=superadmin_headers,
        files={"file": ("contract.txt", b"employment contract", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document["owner_entity_id"] == first["id"]

    listed = await client.get(f"{BASE}/{first['id']}/documents", headers=superadmin_headers)
    assert [item["id"] for item in listed.json()["items"]] == [document["id"]]

    other = await client.get(f"{BASE}/{second['id']}/documents", headers=superadmin_headers)
    assert other.json()["items"] == []

    refused = await client.delete(
        f"{BASE}/{second['id']}/documents/{document['id']}",
        headers=superadmin_headers,
    )
    assert refused.status_code == 404

    removed = await client.delete(
        f"{BASE}/{first['id']}/documents/{document['id']}",
        headers=superadmin_headers,
        params={"reason": "Superseded"},
    )
    assert removed.status_code == 200, removed.text
    after = await client.get(f"{BASE}/{first['id']}/documents", headers=superadmin_headers)
    assert after.json()["items"] == []

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {"staff.documents.upload", "staff.documents.delete"} <= actions


async def test_staff_soft_delete_and_restore_respect_number_uniqueness(
    client, superadmin_headers, seeded
) -> None:
    first = await _staff(client, superadmin_headers, number="STF-1000")
    removed = await client.delete(f"{BASE}/{first['id']}", headers=superadmin_headers)
    assert removed.status_code == 200, removed.text
    assert removed.json()["deleted"] is True

    hidden = await client.get(f"{BASE}", headers=superadmin_headers)
    assert hidden.json()["total"] == 0

    replacement = await _staff(
        client,
        superadmin_headers,
        number="STF-1000",
        person=_person(given_name_en="Marta", given_name_am="ማርታ", sex="female"),
    )
    assert replacement["staff_number"] == "STF-1000"

    conflict = await client.post(f"{BASE}/{first['id']}/restore", headers=superadmin_headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["message_key"] == "staff.error.number_taken"

    await client.delete(f"{BASE}/{replacement['id']}", headers=superadmin_headers)
    restored = await client.post(f"{BASE}/{first['id']}/restore", headers=superadmin_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["staff_number"] == "STF-1000"

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {"staff.delete", "staff.restore"} <= actions


async def test_staff_endpoints_require_permission(client, limited_headers, seeded) -> None:
    listed = await client.get(f"{BASE}", headers=limited_headers)
    assert listed.status_code == 403

    created = await client.post(
        f"{BASE}/departments",
        headers=limited_headers,
        json={"code": "blocked", "name": "Blocked"},
    )
    assert created.status_code == 403
