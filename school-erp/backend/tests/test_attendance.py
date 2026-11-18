"""P3-06: attendance sessions, fast entry, statuses and scoped access."""

from __future__ import annotations

from tests.conftest import create_role, create_user, login, unique_email

BASE = "/api/v1/attendance"
ACADEMICS = "/api/v1/academics"
STUDENTS = "/api/v1/students"
STAFF = "/api/v1/staff"
ACTIVITY = "/api/v1/audit/activity"
SETTINGS = "/api/v1/settings"


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


async def _level(client, headers, code: str) -> dict:
    response = await client.get(f"{ACADEMICS}/levels", headers=headers, params={"scope": "all"})
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["code"] == code)


async def _section(client, headers, year: dict, level: dict, code: str = "A", **extra) -> dict:
    response = await client.post(
        f"{ACADEMICS}/sections",
        headers=headers,
        json={"year_id": year["id"], "level_id": level["id"], "code": code, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _subject(client, headers, code: str, name: str) -> dict:
    response = await client.post(
        f"{ACADEMICS}/subjects",
        headers=headers,
        json={"code": code, "name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _student(
    client,
    headers,
    *,
    number: str,
    given_name: str,
    year: dict,
    level: dict,
    section: dict,
    roll_number: str | None = None,
) -> dict:
    response = await client.post(
        STUDENTS,
        headers=headers,
        json={
            "person": {
                "given_name_en": given_name,
                "father_name_en": "Bekele",
                "grandfather_name_en": "Desta",
                "given_name_am": f"ተማሪ {number}",
                "father_name_am": "በቀለ",
                "grandfather_name_am": "ደስታ",
                "sex": "male",
                "date_of_birth": "2015-01-10",
            },
            "student_number": number,
            "enrollment": {
                "year_id": year["id"],
                "level_id": level["id"],
                "section_id": section["id"],
                "roll_number": roll_number,
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _setup_section(
    client, headers, *, code: str = "A", level_code: str = "g5", year_code: str = "2026-2027"
):
    year = await _year(client, headers, code=year_code)
    level = await _level(client, headers, level_code)
    section = await _section(client, headers, year, level, code=code)
    return year, level, section


async def _open_session(client, headers, year: dict, section: dict, **overrides) -> dict:
    payload = {"year_id": year["id"], "section_id": section["id"], "date": "2026-10-01"}
    payload.update(overrides)
    response = await client.post(BASE, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _activity(client, headers, **params) -> list[dict]:
    response = await client.get(ACTIVITY, headers=headers, params={"limit": 200, **params})
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def _teacher(client, app, headers, *, year: dict, section: dict, subject: dict) -> dict:
    await create_role(
        app,
        "attendance_teacher",
        [
            ("attendance.view", "assigned_subjects"),
            ("attendance.record", "assigned_subjects"),
            ("ai.use", "all"),
        ],
    )
    email = unique_email("attendance.teacher")
    user = await create_user(app, email, roles=["attendance_teacher"])
    staff = await client.post(
        STAFF,
        headers=headers,
        json={
            "person": {
                "given_name_en": "Attendance Teacher",
                "father_name_en": "Bekele",
                "grandfather_name_en": "Desta",
                "sex": "female",
                "date_of_birth": "1990-02-03",
            },
            "staff_number": "STF-ATT-1",
            "hire_date": "2026-09-01",
        },
    )
    assert staff.status_code == 201, staff.text
    staff_id = staff.json()["id"]
    linked = await client.post(
        f"{STAFF}/{staff_id}/account",
        headers=headers,
        json={"user_id": str(user.id)},
    )
    assert linked.status_code == 200, linked.text
    assigned = await client.post(
        f"{STAFF}/{staff_id}/teaching-assignments",
        headers=headers,
        json={"year_id": year["id"], "section_id": section["id"], "subject_id": subject["id"]},
    )
    assert assigned.status_code == 201, assigned.text
    return {"user": user, "headers": await login(client, email)}


async def test_open_session_seeds_present_roster_and_is_audited(client, superadmin_headers, seeded) -> None:
    year, level, section = await _setup_section(client, superadmin_headers)
    for index, name in enumerate(("Abebe", "Hana", "Dawit"), start=1):
        await _student(
            client,
            superadmin_headers,
            number=f"S-ATT-{index}",
            given_name=name,
            year=year,
            level=level,
            section=section,
            roll_number=str(index),
        )

    opened = await _open_session(client, superadmin_headers, year, section)
    assert opened["mode"] == "daily"
    assert opened["status"] == "open"
    assert opened["period"] is None
    assert opened["counts"] == {"total": 3, "present": 3, "absent": 0, "late": 0, "excused": 0}
    assert len(opened["roster"]) == 3
    assert [item["roll_number"] for item in opened["roster"]] == ["1", "2", "3"]
    assert all(record["status"] == "present" for record in opened["records"])

    detail = await client.get(f"{BASE}/{opened['id']}", headers=superadmin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["counts"]["total"] == 3

    duplicate = await client.post(
        BASE,
        headers=superadmin_headers,
        json={"year_id": year["id"], "section_id": section["id"], "date": "2026-10-01"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "attendance.error.session_exists"

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert "attendance.session.create" in actions


async def test_fast_entry_upserts_idempotently_and_validates(client, superadmin_headers, seeded) -> None:
    year, level, section = await _setup_section(client, superadmin_headers)
    other_year, other_level, other_section = await _setup_section(
        client, superadmin_headers, code="B", level_code="g6", year_code="2027-2028"
    )
    students = []
    for index, name in enumerate(("Abebe", "Hana", "Dawit"), start=1):
        students.append(
            await _student(
                client,
                superadmin_headers,
                number=f"S-ENTRY-{index}",
                given_name=name,
                year=year,
                level=level,
                section=section,
            )
        )
    outsider = await _student(
        client,
        superadmin_headers,
        number="S-ENTRY-9",
        given_name="Outsider",
        year=other_year,
        level=other_level,
        section=other_section,
    )
    opened = await _open_session(client, superadmin_headers, year, section)
    missing_reason = await client.post(
        f"{BASE}/{opened['id']}/records",
        headers=superadmin_headers,
        json={"items": [{"student_id": students[1]["id"], "status": "excused"}]},
    )
    assert missing_reason.status_code == 422
    assert missing_reason.json()["error"]["message_key"] == "attendance.error.reason_required"

    not_enrolled = await client.post(
        f"{BASE}/{opened['id']}/records",
        headers=superadmin_headers,
        json={"items": [{"student_id": outsider["id"], "status": "present"}]},
    )
    assert not_enrolled.status_code == 422
    assert not_enrolled.json()["error"]["message_key"] == "attendance.error.student_not_enrolled"

    duplicate_student = await client.post(
        f"{BASE}/{opened['id']}/records",
        headers=superadmin_headers,
        json={
            "items": [
                {"student_id": students[0]["id"], "status": "present"},
                {"student_id": students[0]["id"], "status": "absent"},
            ]
        },
    )
    assert duplicate_student.status_code == 422

    payload = {
        "items": [
            {"student_id": students[0]["id"], "status": "absent", "reason": "Sick"},
            {"student_id": students[1]["id"], "status": "late", "late_minutes": 12},
            {"student_id": students[2]["id"], "status": "present"},
        ]
    }
    first = await client.post(
        f"{BASE}/{opened['id']}/records",
        headers=superadmin_headers,
        json=payload,
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["counts"] == {"total": 3, "present": 1, "absent": 1, "late": 1, "excused": 0}
    assert len(body["records"]) == 3
    by_student = {item["student_id"]: item for item in body["records"]}
    assert by_student[students[1]["id"]]["late_minutes"] == 12
    assert by_student[students[0]["id"]]["reason"] == "Sick"

    replay = await client.post(
        f"{BASE}/{opened['id']}/records",
        headers=superadmin_headers,
        json=payload,
    )
    assert replay.status_code == 200, replay.text
    assert len(replay.json()["records"]) == 3
    assert replay.json()["counts"] == body["counts"]

    default_present = await client.post(
        f"{BASE}/{opened['id']}/records",
        headers=superadmin_headers,
        json={"items": [{"student_id": students[0]["id"]}]},
    )
    assert default_present.status_code == 200, default_present.text
    corrected = {item["student_id"]: item for item in default_present.json()["records"]}
    assert corrected[students[0]["id"]]["status"] == "present"
    assert corrected[students[0]["id"]]["reason"] is None

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {"attendance.record.update", "attendance.session.create"} <= actions


async def test_workflow_lock_reopen_and_row_version(client, superadmin_headers, seeded) -> None:
    year, level, section = await _setup_section(client, superadmin_headers)
    student = await _student(
        client,
        superadmin_headers,
        number="S-FLOW-1",
        given_name="Meron",
        year=year,
        level=level,
        section=section,
    )
    opened = await _open_session(client, superadmin_headers, year, section)
    record = opened["records"][0]
    assert record["row_version"] == 1

    corrected = await client.patch(
        f"{BASE}/{opened['id']}/records/{record['id']}",
        headers=superadmin_headers,
        json={"status": "absent", "reason": "Family matter", "row_version": 1},
    )
    assert corrected.status_code == 200, corrected.text
    current = next(item for item in corrected.json()["records"] if item["id"] == record["id"])
    assert current["status"] == "absent"
    assert current["row_version"] == 2

    stale = await client.patch(
        f"{BASE}/{opened['id']}/records/{record['id']}",
        headers=superadmin_headers,
        json={"status": "present", "row_version": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CONFLICT"
    assert stale.json()["error"]["details"]["current"] == 2

    submitted = await client.post(f"{BASE}/{opened['id']}/submit", headers=superadmin_headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"
    blocked = await client.post(
        f"{BASE}/{opened['id']}/records",
        headers=superadmin_headers,
        json={"items": [{"student_id": student["id"], "status": "present"}]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["message_key"] == "attendance.error.session_closed"

    locked = await client.post(f"{BASE}/{opened['id']}/lock", headers=superadmin_headers)
    assert locked.status_code == 200, locked.text
    assert locked.json()["status"] == "locked"
    reopened = await client.post(f"{BASE}/{opened['id']}/reopen", headers=superadmin_headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "open"
    allowed = await client.post(
        f"{BASE}/{opened['id']}/records",
        headers=superadmin_headers,
        json={"items": [{"student_id": student["id"], "status": "present"}]},
    )
    assert allowed.status_code == 200, allowed.text

    removed = await client.delete(f"{BASE}/{opened['id']}", headers=superadmin_headers)
    assert removed.status_code == 200, removed.text
    gone = await client.get(f"{BASE}/{opened['id']}", headers=superadmin_headers)
    assert gone.status_code == 404

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {
        "attendance.session.submit",
        "attendance.session.lock",
        "attendance.session.reopen",
        "attendance.session.delete",
    } <= actions


async def test_teacher_scope_limits_sections(client, app, superadmin_headers, seeded) -> None:
    year, level, section = await _setup_section(client, superadmin_headers)
    g6 = await _level(client, superadmin_headers, "g6")
    other_section = await _section(client, superadmin_headers, year, g6, code="B")
    subject = await _subject(client, superadmin_headers, "math-att", "Mathematics")
    teacher = await _teacher(
        client,
        app,
        superadmin_headers,
        year=year,
        section=section,
        subject=subject,
    )
    student = await _student(
        client,
        superadmin_headers,
        number="S-SCOPE-1",
        given_name="Selam",
        year=year,
        level=level,
        section=section,
    )

    own = await client.post(
        BASE,
        headers=teacher["headers"],
        json={"year_id": year["id"], "section_id": section["id"], "date": "2026-10-05"},
    )
    assert own.status_code == 201, own.text
    recorded = await client.post(
        f"{BASE}/{own.json()['id']}/records",
        headers=teacher["headers"],
        json={"items": [{"student_id": student["id"], "status": "present"}]},
    )
    assert recorded.status_code == 200, recorded.text

    outside = await client.post(
        BASE,
        headers=teacher["headers"],
        json={"year_id": year["id"], "section_id": other_section["id"], "date": "2026-10-05"},
    )
    assert outside.status_code == 403
    assert outside.json()["error"]["message_key"] == "error.scope_denied"

    listed = await client.get(BASE, headers=teacher["headers"])
    assert listed.status_code == 200, listed.text
    assert [item["section_id"] for item in listed.json()["items"]] == [section["id"]]

    hidden = await client.get(f"{BASE}/{own.json()['id']}", headers=teacher["headers"])
    assert hidden.status_code == 200
    cannot_lock = await client.post(f"{BASE}/{own.json()['id']}/lock", headers=teacher["headers"])
    assert cannot_lock.status_code == 403


async def test_per_period_mode_follows_the_school_setting(client, superadmin_headers, seeded) -> None:
    year, _level_row, section = await _setup_section(client, superadmin_headers)
    switched = await client.put(
        f"{SETTINGS}/attendance/mode",
        headers=superadmin_headers,
        json={"value": "per_period"},
    )
    assert switched.status_code == 200, switched.text
    assert switched.json()["value"] == "per_period"

    missing_period = await client.post(
        BASE,
        headers=superadmin_headers,
        json={"year_id": year["id"], "section_id": section["id"], "date": "2026-10-06"},
    )
    assert missing_period.status_code == 422
    assert missing_period.json()["error"]["message_key"] == "attendance.error.period_required"

    daily_attempt = await client.post(
        BASE,
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "section_id": section["id"],
            "date": "2026-10-06",
            "mode": "daily",
        },
    )
    assert daily_attempt.status_code == 422
    assert daily_attempt.json()["error"]["message_key"] == "attendance.error.mode_mismatch"

    lesson = await client.post(
        BASE,
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "section_id": section["id"],
            "date": "2026-10-06",
            "period": 2,
        },
    )
    assert lesson.status_code == 201, lesson.text
    assert lesson.json()["mode"] == "per_period"
    assert lesson.json()["period"] == 2

    future = await client.post(
        BASE,
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "section_id": section["id"],
            "date": "2027-05-02",
            "period": 3,
        },
    )
    assert future.status_code == 422
    assert future.json()["error"]["message_key"] == "attendance.error.future_date"
