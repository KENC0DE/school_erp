"""P3-08: staff attendance, department scope and summaries."""

from __future__ import annotations

import uuid

from core.auth.models import User
from modules.staff.models import StaffAttendance
from sqlalchemy import func, select

from tests.conftest import create_role, create_user, login, unique_email

BASE = "/api/v1/staff"
ATTENDANCE = f"{BASE}/attendance"
ACTIVITY = "/api/v1/audit/activity"


def _person(given: str, **overrides) -> dict:
    values = {
        "given_name_en": given,
        "father_name_en": "Bekele",
        "grandfather_name_en": "Desta",
        "given_name_am": f"ሠራተኛ {given}",
        "father_name_am": "በቀለ",
        "grandfather_name_am": "ደስታ",
        "sex": "female",
        "date_of_birth": "1991-05-10",
    }
    values.update(overrides)
    return values


async def _department(client, headers, code: str, name: str) -> dict:
    response = await client.post(
        f"{BASE}/departments",
        headers=headers,
        json={"code": code, "name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _staff(
    client,
    headers,
    *,
    number: str,
    given: str,
    department_id: str | None = None,
) -> dict:
    response = await client.post(
        BASE,
        headers=headers,
        json={
            "person": _person(given),
            "staff_number": number,
            "department_id": department_id,
            "hire_date": "2026-09-01",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _activity(client, headers) -> set[str]:
    response = await client.get(ACTIVITY, headers=headers, params={"limit": 200})
    assert response.status_code == 200, response.text
    return {item["action"] for item in response.json()["items"]}


async def _rows(app, staff_id: str) -> int:
    async with app.state.db.session() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(StaffAttendance)
                    .where(StaffAttendance.staff_id == uuid.UUID(staff_id))
                )
            ).scalar_one()
        )


async def test_staff_day_roster_upsert_replay_summary_and_audit(
    client, app, superadmin_headers, seeded
) -> None:
    department = await _department(client, superadmin_headers, "science", "Science")
    one = await _staff(
        client,
        superadmin_headers,
        number="STF-SA-1",
        given="Selam",
        department_id=department["id"],
    )
    two = await _staff(client, superadmin_headers, number="STF-SA-2", given="Dawit")

    day = await client.get(ATTENDANCE, headers=superadmin_headers, params={"date": "2026-10-09"})
    assert day.status_code == 200, day.text
    assert day.json()["counts"] == {
        "total": 2,
        "recorded": 0,
        "present": 0,
        "absent": 0,
        "late": 0,
        "leave": 0,
        "unrecorded": 2,
    }
    assert {item["staff_id"] for item in day.json()["items"]} == {one["id"], two["id"]}
    assert all(item["status"] is None for item in day.json()["items"])

    payload = {
        "date": "2026-10-09",
        "items": [
            {"staff_id": one["id"], "status": "absent", "reason": "Sick"},
            {"staff_id": two["id"], "status": "present"},
        ],
    }
    saved = await client.post(ATTENDANCE, headers=superadmin_headers, json=payload)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["counts"]["recorded"] == 2
    assert body["counts"]["absent"] == 1
    assert body["counts"]["present"] == 1
    assert body["counts"]["unrecorded"] == 0
    by_staff = {item["staff_id"]: item for item in body["items"]}
    assert by_staff[one["id"]]["reason"] == "Sick"
    assert by_staff[one["id"]]["row_version"] == 1

    replay = await client.post(ATTENDANCE, headers=superadmin_headers, json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json()["counts"] == body["counts"]
    assert await _rows(app, one["id"]) == 1
    assert await _rows(app, two["id"]) == 1

    changed = await client.post(
        ATTENDANCE,
        headers=superadmin_headers,
        json={
            "date": "2026-10-09",
            "items": [{"staff_id": two["id"], "status": "leave", "note": "Approved leave"}],
        },
    )
    assert changed.status_code == 200, changed.text
    moved = {item["staff_id"]: item for item in changed.json()["items"]}[two["id"]]
    assert moved["status"] == "leave"
    assert moved["row_version"] == 2

    stale = await client.post(
        ATTENDANCE,
        headers=superadmin_headers,
        json={
            "date": "2026-10-09",
            "items": [{"staff_id": two["id"], "status": "present", "row_version": 1}],
        },
    )
    assert stale.status_code == 409

    filtered = await client.get(
        ATTENDANCE,
        headers=superadmin_headers,
        params={"date": "2026-10-09", "status": "leave"},
    )
    assert [item["staff_id"] for item in filtered.json()["items"]] == [two["id"]]

    summary = await client.get(
        f"{ATTENDANCE}/{one['id']}/summary",
        headers=superadmin_headers,
        params={"from_date": "2026-09-01", "to_date": "2026-10-31"},
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["total"] == 1
    assert summary.json()["absent"] == 1
    assert summary.json()["rate_percent"] == 0

    actions = await _activity(client, superadmin_headers)
    assert {"staff.attendance.create", "staff.attendance.update"} <= actions

    invalid = await client.get(
        f"{ATTENDANCE}/{one['id']}/summary",
        headers=superadmin_headers,
        params={"from_date": "2026-10-31", "to_date": "2026-09-01"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["message_key"] == "staff.error.attendance_range"


async def test_department_scope_limits_staff_attendance(client, app, superadmin_headers, seeded) -> None:
    science = await _department(client, superadmin_headers, "science", "Science")
    maths = await _department(client, superadmin_headers, "maths", "Mathematics")
    inside = await _staff(
        client,
        superadmin_headers,
        number="STF-SCOPE-1",
        given="Hana",
        department_id=science["id"],
    )
    outside = await _staff(
        client,
        superadmin_headers,
        number="STF-SCOPE-2",
        given="Kalkidan",
        department_id=maths["id"],
    )

    await create_role(
        app,
        "staff_attendance_lead",
        [
            ("staff.attendance.view", "department"),
            ("staff.attendance.record", "department"),
        ],
    )
    email = unique_email("attendance.lead")
    user = await create_user(app, email, roles=["staff_attendance_lead"])
    linked = await client.post(
        f"{BASE}/{inside['id']}/account",
        headers=superadmin_headers,
        json={"user_id": str(user.id)},
    )
    assert linked.status_code == 200, linked.text
    headers = await login(client, email)

    day = await client.get(ATTENDANCE, headers=headers, params={"date": "2026-10-12"})
    assert day.status_code == 200, day.text
    assert [item["staff_id"] for item in day.json()["items"]] == [inside["id"]]

    allowed = await client.post(
        ATTENDANCE,
        headers=headers,
        json={
            "date": "2026-10-12",
            "items": [{"staff_id": inside["id"], "status": "present"}],
        },
    )
    assert allowed.status_code == 200, allowed.text

    denied = await client.post(
        ATTENDANCE,
        headers=headers,
        json={
            "date": "2026-10-12",
            "items": [{"staff_id": outside["id"], "status": "present"}],
        },
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["message_key"] == "error.scope_denied"

    hidden = await client.get(
        f"{ATTENDANCE}/{outside['id']}/summary",
        headers=headers,
        params={"from_date": "2026-10-01", "to_date": "2026-10-31"},
    )
    assert hidden.status_code == 403

    async with app.state.db.session() as session:
        linked_user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        assert linked_user.id == user.id


async def test_staff_attendance_rejects_terminated_staff(client, superadmin_headers, seeded) -> None:
    staff = await _staff(client, superadmin_headers, number="STF-TERM-1", given="Meron")
    terminated = await client.patch(
        f"{BASE}/{staff['id']}",
        headers=superadmin_headers,
        json={"status": "terminated", "row_version": staff["row_version"]},
    )
    assert terminated.status_code == 200, terminated.text

    response = await client.post(
        ATTENDANCE,
        headers=superadmin_headers,
        json={
            "date": "2026-10-13",
            "items": [{"staff_id": staff["id"], "status": "present"}],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["message_key"] == "staff.error.attendance_not_employed"
