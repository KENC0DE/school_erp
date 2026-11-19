"""P2-06: student records, enrollment, guardians, medical data and documents."""

from __future__ import annotations

import base64
from collections import defaultdict

from core.events.models import DomainEvent
from sqlalchemy import select

from tests.conftest import create_role, create_user, login, unique_email

BASE = "/api/v1/students"
ACADEMICS = "/api/v1/academics"
PEOPLE = "/api/v1/people"
ACTIVITY = "/api/v1/audit/activity"

PERSON = {
    "given_name_en": "Abebe",
    "father_name_en": "Kebede",
    "grandfather_name_en": "Tessema",
    "given_name_am": "አበበ",
    "father_name_am": "ከበደ",
    "grandfather_name_am": "ተሰማ",
    "sex": "male",
    "date_of_birth": "2014-05-02",
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
            "start_date": "2026-09-11" if code == "2026-2027" else "2027-09-11",
            "end_date": "2027-06-30" if code == "2026-2027" else "2028-06-30",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _level(client, headers, code: str = "g5") -> dict:
    response = await client.get(f"{ACADEMICS}/levels", headers=headers, params={"scope": "all"})
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["code"] == code)


async def _section(client, headers, year: dict, level: dict, code: str = "A") -> dict:
    response = await client.post(
        f"{ACADEMICS}/sections",
        headers=headers,
        json={"year_id": year["id"], "level_id": level["id"], "code": code},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _register(client, headers, number: str = "S-0001", **overrides) -> dict:
    payload = {
        "person": _person(),
        "student_number": number,
        "admission_date": "2026-09-15",
    }
    payload.update(overrides)
    response = await client.post(BASE, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _activity(client, headers, **params) -> list[dict]:
    response = await client.get(ACTIVITY, headers=headers, params={"limit": 200, **params})
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def _student_events(app) -> dict[str, list[dict]]:
    """Student domain events in insertion order, grouped by event type."""
    async with app.state.db.session() as session:
        rows = (
            (
                await session.execute(
                    select(DomainEvent)
                    .where(DomainEvent.event_type.like("student.%"))
                    .order_by(DomainEvent.occurred_at, DomainEvent.id)
                )
            )
            .scalars()
            .all()
        )
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row.event_type].append(row.payload)
    return grouped


async def test_register_student_with_enrollment_guardians_and_medical(
    client, superadmin_headers, seeded
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)

    parent = await client.post(
        f"{PEOPLE}",
        headers=superadmin_headers,
        json=_person(
            given_name_en="Kebede",
            father_name_en="Tessema",
            grandfather_name_en="Alemu",
            given_name_am="ከበደ",
            father_name_am="ተሰማ",
            grandfather_name_am="አለሙ",
            date_of_birth="1985-01-10",
        ),
    )
    assert parent.status_code == 200, parent.text
    parent_id = parent.json()["person"]["id"]

    payload = {
        "person": _person(),
        "student_number": "S-0001",
        "admission_date": "2026-09-15",
        "enrollment": {
            "year_id": year["id"],
            "level_id": level["id"],
            "section_id": section["id"],
            "roll_number": "12",
        },
        "guardians": [
            {"person_id": parent_id, "relationship": "father", "is_primary": True},
            {
                "person": _person(
                    given_name_en="Almaz",
                    father_name_en="Tesfaye",
                    grandfather_name_en="Bekele",
                    date_of_birth="1990-03-03",
                ),
                "relationship": "mother",
            },
        ],
        "medical": {
            "blood_type": "O+",
            "allergies": "Penicillin",
            "emergency_contact_name": "Kebede Tessema",
            "emergency_contact_phone": "0911000000",
            "consent_to_treat": True,
        },
    }

    preview = await client.post(f"{BASE}/register/preview", headers=superadmin_headers, json=payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()["full_name"] == "Abebe Kebede Tessema"
    assert preview.json()["guardian_count"] == 2
    assert preview.json()["has_enrollment"] is True
    assert preview.json()["has_medical"] is True

    registered = await client.post(BASE, headers=superadmin_headers, json=payload)
    assert registered.status_code == 201, registered.text
    student = registered.json()
    assert student["student_number"] == "S-0001"
    assert student["status"] == "active"
    assert student["person"]["full_name"] == "Abebe Kebede Tessema"
    assert student["enrollment"]["year_code"] == "2026-2027"
    assert student["enrollment"]["level_code"] == "g5"
    assert student["enrollment"]["section_code"] == "A"
    assert student["enrollment"]["roll_number"] == "12"
    assert [item["relationship"] for item in student["guardians"]] == ["father", "mother"]
    assert student["guardians"][0]["person"]["id"] == parent_id
    assert student["guardians"][1]["person"]["full_name"] == "Almaz Tesfaye Bekele"
    assert student["medical"]["allergies"] == "Penicillin"
    assert student["duplicate_warnings"] == []

    detail = await client.get(f"{BASE}/{student['id']}", headers=superadmin_headers)
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["enrollments"]) == 1

    # An exact name plus date of birth is surfaced as a warning, not a hard block.
    duplicate = await client.post(
        f"{BASE}/duplicate-check",
        headers=superadmin_headers,
        json={"person": _person()},
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["duplicate_warnings"][0]["reason"] == "same_names_and_dob"
    second = await _register(client, superadmin_headers, number="S-0002")
    assert second["student_number"] == "S-0002"
    assert second["status"] == "applicant"
    assert second["enrollment"] is None
    assert second["duplicate_warnings"][0]["person"]["id"] == student["person"]["id"]

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {
        "students.register",
        "students.enrollments.create",
        "students.guardians.add",
        "students.medical.create",
    } <= actions


async def test_registration_validation_conflicts_and_status_rules(client, superadmin_headers, seeded) -> None:
    first = await _register(client, superadmin_headers, number="S-0100")

    duplicate_number = await client.post(
        BASE,
        headers=superadmin_headers,
        json={"person": _person(given_name_en="Bekele"), "student_number": "S-0100"},
    )
    assert duplicate_number.status_code == 409
    assert duplicate_number.json()["error"]["message_key"] == "students.error.number_taken"

    missing_names = await client.post(
        BASE,
        headers=superadmin_headers,
        json={"person": {"given_name_en": "Dawit"}, "student_number": "S-0101"},
    )
    assert missing_names.status_code == 422
    assert missing_names.json()["error"]["message_key"] == "error.invalid_name"

    bad_status = await client.post(
        BASE,
        headers=superadmin_headers,
        json={
            "person": _person(given_name_en="Hana"),
            "student_number": "S-0102",
            "status": "dropped",
        },
    )
    assert bad_status.status_code == 422

    updated = await client.patch(
        f"{BASE}/{first['id']}",
        headers=superadmin_headers,
        json={"status": "graduated", "row_version": first["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "graduated"
    assert updated.json()["row_version"] == first["row_version"] + 1

    stale = await client.patch(
        f"{BASE}/{first['id']}",
        headers=superadmin_headers,
        json={"notes": "late", "row_version": first["row_version"]},
    )
    assert stale.status_code == 409

    # Student numbers become reusable once the record is soft-deleted.
    deleted = await client.delete(
        f"{BASE}/{first['id']}",
        headers=superadmin_headers,
        params={"row_version": updated.json()["row_version"], "reason": "left"},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert (await client.get(f"{BASE}/{first['id']}", headers=superadmin_headers)).status_code == 404
    listed = await client.get(BASE, headers=superadmin_headers)
    assert first["id"] not in [item["id"] for item in listed.json()["items"]]

    reused = await _register(
        client, superadmin_headers, number="S-0100", person=_person(given_name_en="Selam")
    )
    assert reused["student_number"] == "S-0100"

    restored = await client.post(f"{BASE}/{first['id']}/restore", headers=superadmin_headers)
    assert restored.status_code == 409
    assert restored.json()["error"]["message_key"] == "students.error.number_taken"


async def test_list_search_filters_and_cursor_pagination(client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    other_level = await _level(client, superadmin_headers, "g6")

    first = await _register(
        client,
        superadmin_headers,
        number="S-2001",
        person=_person(given_name_en="Abebe", father_name_en="Kebede"),
        enrollment={"year_id": year["id"], "level_id": level["id"], "section_id": section["id"]},
    )
    second = await _register(
        client,
        superadmin_headers,
        number="S-2002",
        person=_person(
            given_name_en="Marta",
            father_name_en="Girma",
            grandfather_name_en="Desta",
            given_name_am=None,
            father_name_am=None,
            grandfather_name_am=None,
            date_of_birth="2013-01-01",
        ),
        enrollment={"year_id": year["id"], "level_id": other_level["id"]},
    )
    third = await _register(
        client,
        superadmin_headers,
        number="S-2003",
        person=_person(
            given_name_en="Yonas",
            father_name_en="Tekle",
            grandfather_name_en="Haile",
            given_name_am=None,
            father_name_am=None,
            grandfather_name_am=None,
            date_of_birth="2012-02-02",
        ),
    )

    by_name = await client.get(BASE, headers=superadmin_headers, params={"q": "abebe"})
    assert by_name.status_code == 200, by_name.text
    assert [item["id"] for item in by_name.json()["items"]] == [first["id"]]

    by_amharic = await client.get(BASE, headers=superadmin_headers, params={"q": "አበበ"})
    assert [item["id"] for item in by_amharic.json()["items"]] == [first["id"]]

    by_number = await client.get(BASE, headers=superadmin_headers, params={"q": "2002"})
    assert [item["id"] for item in by_number.json()["items"]] == [second["id"]]

    by_status = await client.get(BASE, headers=superadmin_headers, params={"status": "applicant"})
    assert [item["id"] for item in by_status.json()["items"]] == [third["id"]]

    by_level = await client.get(BASE, headers=superadmin_headers, params={"level_id": other_level["id"]})
    assert [item["id"] for item in by_level.json()["items"]] == [second["id"]]

    paged = []
    cursor = None
    while True:
        params = {"limit": 2, "sort": "student_number", "order": "asc"}
        if cursor:
            params["cursor"] = cursor
        response = await client.get(BASE, headers=superadmin_headers, params=params)
        assert response.status_code == 200, response.text
        body = response.json()
        paged.extend(item["student_number"] for item in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert paged == ["S-2001", "S-2002", "S-2003"]

    unknown_sort = await client.get(BASE, headers=superadmin_headers, params={"sort": "name"})
    assert unknown_sort.status_code == 422
    assert unknown_sort.json()["error"]["code"] == "INVALID_SORT"


async def test_enrollment_lifecycle_conflicts_and_closed_year(client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    student = await _register(
        client,
        superadmin_headers,
        enrollment={"year_id": year["id"], "level_id": level["id"], "section_id": section["id"]},
    )
    enrollment = student["enrollment"]

    duplicate = await client.post(
        f"{BASE}/{student['id']}/enrollments",
        headers=superadmin_headers,
        json={"year_id": year["id"], "level_id": level["id"]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "students.error.enrollment_exists"

    next_year = await _year(client, superadmin_headers, code="2027-2028")
    mismatch = await client.post(
        f"{BASE}/{student['id']}/enrollments",
        headers=superadmin_headers,
        json={
            "year_id": next_year["id"],
            "level_id": level["id"],
            "section_id": section["id"],
        },
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["message_key"] == "students.error.section_mismatch"

    promoted = await client.post(
        f"{BASE}/{student['id']}/enrollments",
        headers=superadmin_headers,
        json={"year_id": next_year["id"], "level_id": level["id"], "status": "promoted"},
    )
    assert promoted.status_code == 201, promoted.text
    assert promoted.json()["year_code"] == "2027-2028"
    assert promoted.json()["status"] == "promoted"

    edited = await client.patch(
        f"{BASE}/{student['id']}/enrollments/{enrollment['id']}",
        headers=superadmin_headers,
        json={"roll_number": "7", "row_version": enrollment["row_version"]},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["roll_number"] == "7"

    stale = await client.patch(
        f"{BASE}/{student['id']}/enrollments/{enrollment['id']}",
        headers=superadmin_headers,
        json={"roll_number": "8", "row_version": enrollment["row_version"]},
    )
    assert stale.status_code == 409

    deleted = await client.delete(
        f"{BASE}/{student['id']}/enrollments/{enrollment['id']}",
        headers=superadmin_headers,
        params={"reason": "moved section"},
    )
    assert deleted.status_code == 200, deleted.text
    remaining = await client.get(f"{BASE}/{student['id']}/enrollments", headers=superadmin_headers)
    assert [item["id"] for item in remaining.json()] == [promoted.json()["id"]]

    restored = await client.post(
        f"{BASE}/{student['id']}/enrollments/{enrollment['id']}/restore",
        headers=superadmin_headers,
    )
    assert restored.status_code == 200, restored.text
    assert (
        len((await client.get(f"{BASE}/{student['id']}/enrollments", headers=superadmin_headers)).json()) == 2
    )

    # Closing the year blocks new placements without touching existing rows.
    await client.post(f"{ACADEMICS}/academic-years/{year['id']}/open", headers=superadmin_headers)
    closed = await client.post(f"{ACADEMICS}/academic-years/{year['id']}/close", headers=superadmin_headers)
    assert closed.status_code == 200, closed.text
    blocked = await client.post(
        f"{BASE}/{student['id']}/enrollments",
        headers=superadmin_headers,
        json={"year_id": year["id"], "level_id": level["id"]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["message_key"] == "students.error.year_closed"

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {
        "students.enrollments.create",
        "students.enrollments.update",
        "students.enrollments.delete",
        "students.enrollments.restore",
    } <= actions


async def test_guardians_are_shared_across_children_and_primary_is_unique(
    client, superadmin_headers, seeded
) -> None:
    parent = await client.post(
        f"{PEOPLE}",
        headers=superadmin_headers,
        json=_person(
            given_name_en="Kebede",
            father_name_en="Tessema",
            grandfather_name_en="Alemu",
            date_of_birth="1980-02-02",
        ),
    )
    parent_id = parent.json()["person"]["id"]

    first = await _register(client, superadmin_headers, number="S-3001")
    second = await _register(
        client,
        superadmin_headers,
        number="S-3002",
        person=_person(given_name_en="Selam", date_of_birth="2015-07-07"),
    )

    for student in (first, second):
        linked = await client.post(
            f"{BASE}/{student['id']}/guardians",
            headers=superadmin_headers,
            json={"person_id": parent_id, "relationship": "father", "is_primary": True},
        )
        assert linked.status_code == 201, linked.text
        assert linked.json()["person"]["id"] == parent_id

    duplicated = await client.post(
        f"{BASE}/{first['id']}/guardians",
        headers=superadmin_headers,
        json={"person_id": parent_id, "relationship": "father"},
    )
    assert duplicated.status_code == 409
    assert duplicated.json()["error"]["message_key"] == "students.error.guardian_exists"

    own_person = first["person"]["id"]
    self_guardian = await client.post(
        f"{BASE}/{first['id']}/guardians",
        headers=superadmin_headers,
        json={"person_id": own_person, "relationship": "self"},
    )
    assert self_guardian.status_code == 422
    assert self_guardian.json()["error"]["message_key"] == "students.error.guardian_is_student"

    mother = await client.post(
        f"{BASE}/{first['id']}/guardians",
        headers=superadmin_headers,
        json={
            "person": _person(
                given_name_en="Almaz",
                father_name_en="Tesfaye",
                date_of_birth="1984-04-04",
            ),
            "relationship": "mother",
            "is_primary": True,
        },
    )
    assert mother.status_code == 201, mother.text

    guardians = await client.get(f"{BASE}/{first['id']}/guardians", headers=superadmin_headers)
    assert guardians.status_code == 200, guardians.text
    rows = guardians.json()
    assert rows[0]["relationship"] == "mother"
    assert rows[0]["is_primary"] is True
    assert sum(1 for row in rows if row["is_primary"]) == 1

    removed = await client.delete(
        f"{BASE}/{first['id']}/guardians/{rows[0]['id']}",
        headers=superadmin_headers,
        params={"row_version": rows[0]["row_version"]},
    )
    assert removed.status_code == 200, removed.text
    restored = await client.post(
        f"{BASE}/{first['id']}/guardians/{rows[0]['id']}/restore",
        headers=superadmin_headers,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["relationship"] == "mother"


async def test_medical_records_need_dedicated_permissions(app, client, superadmin_headers, seeded) -> None:
    student = await _register(client, superadmin_headers, number="S-4001")
    url = f"{BASE}/{student['id']}/medical"

    written = await client.put(
        url,
        headers=superadmin_headers,
        json={"blood_type": "A-", "allergies": "Dust", "consent_to_treat": True},
    )
    assert written.status_code == 200, written.text
    assert written.json()["allergies"] == "Dust"
    assert written.json()["row_version"] == 1

    replaced = await client.put(
        url,
        headers=superadmin_headers,
        json={"blood_type": "A-", "allergies": "Dust and pollen", "consent_to_treat": True},
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["row_version"] == 2

    view_only = await create_role(
        app,
        "medical_reader",
        [("students.view", "all"), ("students.medical.view", "all"), ("academics.view", "all")],
    )
    reader_email = unique_email("medical-reader")
    await create_user(app, reader_email, roles=[view_only.key])
    reader_headers = await login(client, reader_email)

    readable = await client.get(url, headers=reader_headers)
    assert readable.status_code == 200, readable.text
    assert readable.json()["allergies"] == "Dust and pollen"
    denied_write = await client.put(url, headers=reader_headers, json={"blood_type": "B+"})
    assert denied_write.status_code == 403
    assert denied_write.json()["error"]["code"] == "PERMISSION_DENIED"

    plain = await create_role(app, "student_reader", [("students.view", "all")])
    plain_email = unique_email("student-reader")
    await create_user(app, plain_email, roles=[plain.key])
    plain_headers = await login(client, plain_email)

    hidden = await client.get(url, headers=plain_headers)
    assert hidden.status_code == 403
    detail = await client.get(f"{BASE}/{student['id']}", headers=plain_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["medical"] is None

    # Registration cannot be used as a side door into medical records.
    registrar = await create_role(
        app, "student_registrar", [("students.view", "all"), ("students.manage", "all")]
    )
    registrar_email = unique_email("student-registrar")
    await create_user(app, registrar_email, roles=[registrar.key])
    registrar_headers = await login(client, registrar_email)

    refused = await client.post(
        BASE,
        headers=registrar_headers,
        json={
            "person": _person(given_name_en="Hana", date_of_birth="2016-01-01"),
            "student_number": "S-4002",
            "medical": {"allergies": "Peanuts"},
        },
    )
    assert refused.status_code == 403
    assert refused.json()["error"]["details"] == {"permission": "students.medical.manage"}

    accepted = await client.post(
        BASE,
        headers=registrar_headers,
        json={
            "person": _person(given_name_en="Hana", date_of_birth="2016-01-01"),
            "student_number": "S-4002",
        },
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["medical"] is None


async def test_documents_are_scoped_to_the_student(client, superadmin_headers, seeded) -> None:
    first = await _register(client, superadmin_headers, number="S-5001")
    second = await _register(
        client,
        superadmin_headers,
        number="S-5002",
        person=_person(given_name_en="Selam", date_of_birth="2015-08-08"),
    )

    uploaded = await client.post(
        f"{BASE}/{first['id']}/documents",
        headers=superadmin_headers,
        files={"file": ("birth.txt", b"birth certificate", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document["name"] == "birth.txt"
    assert document["owner_entity_id"] == first["id"]

    listed = await client.get(f"{BASE}/{first['id']}/documents", headers=superadmin_headers)
    assert [item["id"] for item in listed.json()["items"]] == [document["id"]]

    hidden = await client.get(f"{BASE}/{second['id']}/documents", headers=superadmin_headers)
    assert hidden.json()["items"] == []

    refused = await client.delete(
        f"{BASE}/{second['id']}/documents/{document['id']}",
        headers=superadmin_headers,
    )
    assert refused.status_code == 404

    removed = await client.delete(
        f"{BASE}/{first['id']}/documents/{document['id']}",
        headers=superadmin_headers,
        params={"reason": "superseded"},
    )
    assert removed.status_code == 200, removed.text
    after = await client.get(f"{BASE}/{first['id']}/documents", headers=superadmin_headers)
    assert after.json()["items"] == []

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {"students.documents.upload", "students.documents.delete"} <= actions


async def test_photo_upload_is_scoped_and_visible_to_student_viewers(
    client, app, superadmin_headers, seeded
) -> None:
    first = await _register(client, superadmin_headers, number="S-5101")
    second = await _register(
        client,
        superadmin_headers,
        number="S-5102",
        person=_person(given_name_en="Selam", date_of_birth="2015-08-08"),
    )

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGM8ISfH"
        "wMDAxMDAwMDAAAANBAEIfXHKZgAAAABJRU5ErkJggg=="
    )
    uploaded = await client.post(
        f"{BASE}/photos",
        headers=superadmin_headers,
        files={"file": ("portrait.png", png, "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    photo = uploaded.json()
    assert photo["mime"] == "image/png"
    assert photo["url"]

    updated = await client.patch(
        f"{BASE}/{first['id']}",
        headers=superadmin_headers,
        json={"person": {"photo_file_id": photo["id"]}, "row_version": first["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["person"]["photo_file_id"] == photo["id"]

    fetched = await client.get(f"{BASE}/{first['id']}/photo", headers=superadmin_headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["file_id"] == photo["id"]
    assert fetched.json()["url"]

    # The photo endpoint follows students.view, so a student viewer without
    # files.view can still render the profile photo.
    viewer_role = await create_role(app, "student_viewer_photo", [("students.view", "all")])
    viewer_email = unique_email("student-photo-viewer")
    await create_user(app, viewer_email, roles=[viewer_role.key])
    viewer_headers = await login(client, viewer_email)
    visible = await client.get(f"{BASE}/{first['id']}/photo", headers=viewer_headers)
    assert visible.status_code == 200, visible.text

    missing = await client.get(f"{BASE}/{second['id']}/photo", headers=superadmin_headers)
    assert missing.status_code == 404

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert "students.photo.upload" in actions


async def test_student_custom_fields_are_validated(client, superadmin_headers, seeded) -> None:
    field = await client.post(
        "/api/v1/custom-fields/student",
        headers=superadmin_headers,
        json={
            "key": "previous_school",
            "label_key": "custom.student.previous_school",
            "field_type": "text",
            "required": False,
            "order": 1,
        },
    )
    assert field.status_code == 200, field.text

    student = await _register(
        client,
        superadmin_headers,
        number="S-6001",
        custom={"previous_school": "Sunrise Primary"},
    )
    assert student["custom"] == {"previous_school": "Sunrise Primary"}

    updated = await client.patch(
        f"{BASE}/{student['id']}",
        headers=superadmin_headers,
        json={"custom": {"previous_school": "Sunrise Academy"}, "row_version": student["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["custom"]["previous_school"] == "Sunrise Academy"

    unknown = await client.patch(
        f"{BASE}/{student['id']}",
        headers=superadmin_headers,
        json={"custom": {"not_a_field": "x"}, "row_version": updated.json()["row_version"]},
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["message_key"] == "error.custom_field.invalid"


async def test_students_permissions_module_gate_and_tools(app, client, superadmin_headers, seeded) -> None:
    reader = await create_role(app, "students_only_viewer", [("students.view", "all")])
    reader_email = unique_email("students-viewer")
    await create_user(app, reader_email, roles=[reader.key])
    reader_headers = await login(client, reader_email)

    student = await _register(client, superadmin_headers, number="S-7001")
    assert (await client.get(BASE, headers=reader_headers)).status_code == 200
    assert (await client.get(f"{BASE}/{student['id']}", headers=reader_headers)).status_code == 200
    denied_create = await client.post(
        BASE,
        headers=reader_headers,
        json={"person": _person(given_name_en="Hana"), "student_number": "S-7002"},
    )
    assert denied_create.status_code == 403

    limited = await login(client, "limited@demo.school")
    assert (await client.get(BASE, headers=limited)).status_code == 403

    tools = await client.get("/api/v1/ai/tools", headers=superadmin_headers)
    keys = {tool["key"] for tool in tools.json()["items"]}
    assert {
        "students.search",
        "students.register",
        "students.update",
        "students.enrollments.create",
        "students.guardians.add",
        "students.medical.update",
    } <= keys
    register = next(item for item in tools.json()["items"] if item["key"] == "students.register")
    assert register["risk"] == "write"
    assert register["requires_confirmation"] is True

    nav = await client.get("/api/v1/auth/me/navigation", headers=reader_headers)
    assert "students" in [item["key"] for item in nav.json()["items"]]

    disabled = await client.put(
        "/api/v1/system/modules/admissions",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    # Attendance also depends on students, so it must be switched off first.
    disabled = await client.put(
        "/api/v1/system/modules/attendance",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    # Assessment also depends on students, so it must be switched off first.
    disabled = await client.put(
        "/api/v1/system/modules/assessment",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    disabled = await client.put(
        "/api/v1/system/modules/students",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    blocked = await client.get(BASE, headers=superadmin_headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "MODULE_DISABLED"
    nav = await client.get("/api/v1/auth/me/navigation", headers=reader_headers)
    assert "students" not in [item["key"] for item in nav.json()["items"]]


async def test_registration_emits_admitted_and_enrolled_events(
    app, client, superadmin_headers, seeded
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    student = await _register(
        client,
        superadmin_headers,
        number="S-EVT-01",
        enrollment={"year_id": year["id"], "level_id": level["id"], "section_id": section["id"]},
    )

    events = await _student_events(app)
    assert len(events["student.admitted"]) == 1
    admitted = events["student.admitted"][0]
    assert admitted["student_id"] == student["id"]
    assert admitted["student_number"] == "S-EVT-01"
    assert admitted["status"] == "active"
    assert admitted["admission_date"] == "2026-09-15"

    assert len(events["student.enrolled"]) == 1
    enrolled = events["student.enrolled"][0]
    assert enrolled["student_id"] == student["id"]
    assert enrolled["enrollment_id"] == student["enrollment"]["id"]
    assert enrolled["year_id"] == year["id"]
    assert enrolled["level_id"] == level["id"]
    assert enrolled["section_id"] == section["id"]
    assert enrolled["status"] == "active"


async def test_enrollment_route_emits_enrolled_event(app, client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    student = await _register(client, superadmin_headers, number="S-EVT-02")
    before = await _student_events(app)
    assert "student.enrolled" not in before

    response = await client.post(
        f"{BASE}/{student['id']}/enrollments",
        headers=superadmin_headers,
        json={"year_id": year["id"], "level_id": level["id"]},
    )
    assert response.status_code == 201, response.text
    created = response.json()

    events = await _student_events(app)
    assert len(events["student.enrolled"]) == 1
    assert events["student.enrolled"][0]["enrollment_id"] == created["id"]
    assert events["student.enrolled"][0]["student_id"] == student["id"]
