"""P3-02: teaching assignments and the scope resolvers they feed."""

from __future__ import annotations

from tests.conftest import create_user, login, unique_email

BASE = "/api/v1/staff"
ACADEMICS = "/api/v1/academics"
STUDENTS = "/api/v1/students"
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


async def _level(client, headers, code: str) -> dict:
    response = await client.get(f"{ACADEMICS}/levels", headers=headers)
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["code"] == code)


async def _section(
    client,
    headers,
    *,
    year_id: str,
    level_id: str,
    code: str = "A",
    homeroom_user_id: str | None = None,
) -> dict:
    response = await client.post(
        f"{ACADEMICS}/sections",
        headers=headers,
        json={
            "year_id": year_id,
            "level_id": level_id,
            "code": code,
            "homeroom_user_id": homeroom_user_id,
        },
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


async def _staff(client, headers, number: str, **overrides) -> dict:
    payload = {
        "person": _person(),
        "staff_number": number,
        "hire_date": "2026-09-01",
    }
    payload.update(overrides)
    response = await client.post(BASE, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _link(client, headers, staff_id: str, user_id: str) -> dict:
    response = await client.post(
        f"{BASE}/{staff_id}/account",
        headers=headers,
        json={"user_id": user_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _assignment(
    client,
    headers,
    staff_id: str,
    *,
    year_id: str,
    section_id: str,
    subject_id: str,
) -> dict:
    response = await client.post(
        f"{BASE}/{staff_id}/teaching-assignments",
        headers=headers,
        json={
            "year_id": year_id,
            "section_id": section_id,
            "subject_id": subject_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _student(
    client,
    headers,
    *,
    number: str,
    given_name: str,
    year_id: str,
    level_id: str,
    section_id: str,
) -> dict:
    response = await client.post(
        STUDENTS,
        headers=headers,
        json={
            "person": {
                "given_name_en": given_name,
                "father_name_en": "Bekele",
                "grandfather_name_en": "Desta",
                "sex": "male",
                "date_of_birth": "2015-01-10",
            },
            "student_number": number,
            "enrollment": {
                "year_id": year_id,
                "level_id": level_id,
                "section_id": section_id,
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _teacher_user(app, client, headers, staff_number: str, *, role: str) -> dict:
    email = unique_email("teacher")
    user = await create_user(app, email, roles=[role])
    staff = await _staff(
        client,
        headers,
        staff_number,
        person=_person(
            given_name_en=f"Teacher {staff_number[-1]}",
            given_name_am=f"መምህር {staff_number[-1]}",
        ),
    )
    await _link(client, headers, staff["id"], str(user.id))
    return {"user": user, "staff": staff, "headers": await login(client, email)}


async def test_teaching_assignments_are_validated_audited_and_restorable(
    client, superadmin_headers, seeded
) -> None:
    year = await _year(client, superadmin_headers)
    other_year = await _year(client, superadmin_headers, code="2027-2028")
    g5 = await _level(client, superadmin_headers, "g5")
    g6 = await _level(client, superadmin_headers, "g6")
    section = await _section(
        client,
        superadmin_headers,
        year_id=year["id"],
        level_id=g5["id"],
    )
    other_section = await _section(
        client,
        superadmin_headers,
        year_id=other_year["id"],
        level_id=g6["id"],
    )
    math = await _subject(client, superadmin_headers, "math", "Mathematics")
    staff = await _staff(client, superadmin_headers, "STF-9001")

    created = await _assignment(
        client,
        superadmin_headers,
        staff["id"],
        year_id=year["id"],
        section_id=section["id"],
        subject_id=math["id"],
    )
    assert created["staff_number"] == "STF-9001"
    assert created["year_code"] == "2026-2027"
    assert created["section_code"] == "A"
    assert created["level_code"] == "g5"
    assert created["subject_code"] == "math"

    duplicate = await client.post(
        f"{BASE}/{staff['id']}/teaching-assignments",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "section_id": section["id"],
            "subject_id": math["id"],
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "staff.error.assignment_exists"

    wrong_year = await client.post(
        f"{BASE}/{staff['id']}/teaching-assignments",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "section_id": other_section["id"],
            "subject_id": math["id"],
        },
    )
    assert wrong_year.status_code == 422
    assert wrong_year.json()["error"]["message_key"] == "staff.error.assignment_section_year"

    unknown_subject = await client.post(
        f"{BASE}/{staff['id']}/teaching-assignments",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "section_id": section["id"],
            "subject_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert unknown_subject.status_code == 404

    listed = await client.get(
        f"{BASE}/teaching-assignments",
        headers=superadmin_headers,
        params={"section_id": section["id"]},
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [created["id"]]
    by_staff = await client.get(
        f"{BASE}/{staff['id']}/teaching-assignments",
        headers=superadmin_headers,
    )
    assert by_staff.json()["total"] == 1

    updated = await client.patch(
        f"{BASE}/{staff['id']}/teaching-assignments/{created['id']}",
        headers=superadmin_headers,
        json={"notes": "Double period", "row_version": created["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["notes"] == "Double period"
    stale = await client.patch(
        f"{BASE}/{staff['id']}/teaching-assignments/{created['id']}",
        headers=superadmin_headers,
        json={"notes": "Stale", "row_version": created["row_version"]},
    )
    assert stale.status_code == 409

    removed = await client.delete(
        f"{BASE}/{staff['id']}/teaching-assignments/{created['id']}",
        headers=superadmin_headers,
        params={"reason": "Timetable changed"},
    )
    assert removed.status_code == 200, removed.text
    assert (
        await client.get(
            f"{BASE}/{staff['id']}/teaching-assignments",
            headers=superadmin_headers,
        )
    ).json()["total"] == 0

    restored = await client.post(
        f"{BASE}/{staff['id']}/teaching-assignments/{created['id']}/restore",
        headers=superadmin_headers,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["id"] == created["id"]

    activity = await client.get(ACTIVITY, headers=superadmin_headers, params={"limit": 200})
    actions = {item["action"] for item in activity.json()["items"]}
    assert {
        "staff.teaching.create",
        "staff.teaching.update",
        "staff.teaching.delete",
        "staff.teaching.restore",
    } <= actions


async def test_assigned_subjects_scope_isolates_teachers(client, app, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    g5 = await _level(client, superadmin_headers, "g5")
    g6 = await _level(client, superadmin_headers, "g6")
    five = await _section(client, superadmin_headers, year_id=year["id"], level_id=g5["id"])
    six = await _section(client, superadmin_headers, year_id=year["id"], level_id=g6["id"])
    math = await _subject(client, superadmin_headers, "math", "Mathematics")
    coding = await _subject(client, superadmin_headers, "coding", "Coding")

    student_five = await _student(
        client,
        superadmin_headers,
        number="S-3001",
        given_name="Abel",
        year_id=year["id"],
        level_id=g5["id"],
        section_id=five["id"],
    )
    student_six = await _student(
        client,
        superadmin_headers,
        number="S-3002",
        given_name="Selam",
        year_id=year["id"],
        level_id=g6["id"],
        section_id=six["id"],
    )

    first = await _teacher_user(app, client, superadmin_headers, "STF-9101", role="teacher")
    second = await _teacher_user(app, client, superadmin_headers, "STF-9102", role="teacher")
    await _assignment(
        client,
        superadmin_headers,
        first["staff"]["id"],
        year_id=year["id"],
        section_id=five["id"],
        subject_id=math["id"],
    )
    await _assignment(
        client,
        superadmin_headers,
        second["staff"]["id"],
        year_id=year["id"],
        section_id=six["id"],
        subject_id=coding["id"],
    )

    first_list = await client.get(STUDENTS, headers=first["headers"])
    assert first_list.status_code == 200, first_list.text
    assert [item["id"] for item in first_list.json()["items"]] == [student_five["id"]]

    second_list = await client.get(STUDENTS, headers=second["headers"])
    assert [item["id"] for item in second_list.json()["items"]] == [student_six["id"]]

    hidden = await client.get(f"{STUDENTS}/{student_six['id']}", headers=first["headers"])
    assert hidden.status_code == 403
    assert hidden.json()["error"]["message_key"] == "error.scope_denied"

    hidden_guardians = await client.get(
        f"{STUDENTS}/{student_six['id']}/guardians",
        headers=first["headers"],
    )
    assert hidden_guardians.status_code == 403

    visible = await client.get(f"{STUDENTS}/{student_five['id']}", headers=first["headers"])
    assert visible.status_code == 200, visible.text
    assert visible.json()["id"] == student_five["id"]

    filtered = await client.get(
        STUDENTS,
        headers=first["headers"],
        params={"section_id": six["id"]},
    )
    assert filtered.json()["total"] == 0


async def test_own_class_and_department_scopes(client, app, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    g5 = await _level(client, superadmin_headers, "g5")
    g6 = await _level(client, superadmin_headers, "g6")

    homeroom_email = unique_email("homeroom")
    homeroom_user = await create_user(app, homeroom_email, roles=["homeroom_teacher"])
    five = await _section(
        client,
        superadmin_headers,
        year_id=year["id"],
        level_id=g5["id"],
        homeroom_user_id=str(homeroom_user.id),
    )
    six = await _section(client, superadmin_headers, year_id=year["id"], level_id=g6["id"])
    student_five = await _student(
        client,
        superadmin_headers,
        number="S-3101",
        given_name="Hana",
        year_id=year["id"],
        level_id=g5["id"],
        section_id=five["id"],
    )
    student_six = await _student(
        client,
        superadmin_headers,
        number="S-3102",
        given_name="Dawit",
        year_id=year["id"],
        level_id=g6["id"],
        section_id=six["id"],
    )

    homeroom_headers = await login(client, homeroom_email)
    homeroom_list = await client.get(STUDENTS, headers=homeroom_headers)
    assert [item["id"] for item in homeroom_list.json()["items"]] == [student_five["id"]]
    denied = await client.get(f"{STUDENTS}/{student_six['id']}", headers=homeroom_headers)
    assert denied.status_code == 403

    science = await client.post(
        f"{BASE}/departments",
        headers=superadmin_headers,
        json={"code": "science", "name": "Science"},
    )
    languages = await client.post(
        f"{BASE}/departments",
        headers=superadmin_headers,
        json={"code": "languages", "name": "Languages"},
    )
    assert science.status_code == 201 and languages.status_code == 201

    head_email = unique_email("depthead")
    head_user = await create_user(app, head_email, roles=["department_head"])
    head_staff = await _staff(
        client,
        superadmin_headers,
        "STF-9201",
        department_id=science.json()["id"],
    )
    await _link(client, superadmin_headers, head_staff["id"], str(head_user.id))
    other_staff = await _staff(
        client,
        superadmin_headers,
        "STF-9202",
        department_id=languages.json()["id"],
        person=_person(given_name_en="Other", given_name_am="ሌላ", sex="male"),
    )

    head_headers = await login(client, head_email)
    visible = await client.get(BASE, headers=head_headers)
    assert visible.status_code == 200, visible.text
    assert [item["id"] for item in visible.json()["items"]] == [head_staff["id"]]

    outside = await client.get(f"{BASE}/{other_staff['id']}", headers=head_headers)
    assert outside.status_code == 403
    assert outside.json()["error"]["message_key"] == "error.scope_denied"
