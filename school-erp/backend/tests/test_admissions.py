"""P2-09: admissions intake, entrance test, decisions, placement and conversion."""

from __future__ import annotations

import asyncio

from core.auth.models import User
from core.events.models import DomainEvent
from core.rbac.models import Role, UserRole
from sqlalchemy import select

from tests.conftest import create_role, create_user, login, unique_email

BASE = "/api/v1/admissions"
ACADEMICS = "/api/v1/academics"
PEOPLE = "/api/v1/people"
SETTINGS = "/api/v1/settings"
ACTIVITY = "/api/v1/audit/activity"
CUSTOM = "/api/v1/custom-fields/admission_application"

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


async def _person_row(client, headers, **overrides) -> dict:
    response = await client.post(f"{PEOPLE}", headers=headers, json=_person(**overrides))
    assert response.status_code in {200, 201}, response.text
    body = response.json()
    return body.get("person", body)


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


async def _section(
    client, headers, year: dict, level: dict, code: str = "A", capacity: int | None = None
) -> dict:
    payload = {"year_id": year["id"], "level_id": level["id"], "code": code}
    if capacity is not None:
        payload["capacity"] = capacity
    response = await client.post(f"{ACADEMICS}/sections", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _guardian(**overrides) -> dict:
    guardian = {
        "given_name_en": "Kebede",
        "father_name_en": "Tessema",
        "grandfather_name_en": "Alemu",
        "given_name_am": "ከበደ",
        "father_name_am": "ተሰማ",
        "grandfather_name_am": "አለሙ",
        "sex": "male",
        "date_of_birth": "1985-01-10",
    }
    guardian.update(overrides)
    return guardian


def _payload(year: dict, level: dict, **overrides) -> dict:
    payload = {
        "person": _person(),
        "year_id": year["id"],
        "level_id": level["id"],
        "guardians": [{"person": _guardian(), "relationship": "father", "is_primary": True}],
    }
    payload.update(overrides)
    return payload


async def _create(client, headers, year: dict, level: dict, **overrides) -> dict:
    response = await client.post(BASE, headers=headers, json=_payload(year, level, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


async def _decide(client, headers, application: dict, status: str, **extra) -> dict:
    response = await client.post(
        f"{BASE}/{application['id']}/decision",
        headers=headers,
        json={"status": status, "row_version": application["row_version"], **extra},
    )
    assert response.status_code == 200, response.text
    return response.json()["application"]


async def _accept(client, headers, application: dict) -> dict:
    reviewed = await _decide(client, headers, application, "reviewed")
    tested = await _decide(client, headers, reviewed, "test", entrance_test_score=80)
    offered = await _decide(client, headers, tested, "offered")
    return await _decide(client, headers, offered, "accepted")


async def _convert(client, headers, application: dict, **overrides) -> dict:
    payload = {"row_version": application["row_version"], **overrides}
    response = await client.post(f"{BASE}/{application['id']}/convert", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


async def _activity(client, headers, **params) -> list[dict]:
    response = await client.get(ACTIVITY, headers=headers, params={"limit": 200, **params})
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def _events(app) -> list[str]:
    async with app.state.db.session() as session:
        rows = (await session.execute(select(DomainEvent.event_type))).scalars().all()
        return list(rows)


# ------------------------------------------------------------------ form/settings


async def test_application_form_exposes_custom_fields_and_test_settings(
    client, superadmin_headers, seeded
) -> None:
    field = await client.post(
        CUSTOM,
        headers=superadmin_headers,
        json={
            "key": "previous_school",
            "label_key": "custom.admission.previous_school",
            "field_type": "text",
            "required": True,
            "order": 1,
        },
    )
    assert field.status_code == 200, field.text

    form = await client.get(f"{BASE}/form", headers=superadmin_headers)
    assert form.status_code == 200, form.text
    body = form.json()
    assert body["entity_type"] == "admission_application"
    assert "previous_school" in [item["key"] for item in body["fields"]]
    assert body["entrance_test_enabled"] is True
    assert body["entrance_test_max_score"] == 100
    assert body["entrance_test_pass_score"] == 50
    assert body["require_guardian"] is True
    assert body["public_form_enabled"] is False

    enabled = await client.put(
        f"{SETTINGS}/admissions/form.public_enabled",
        headers=superadmin_headers,
        json={"value": True},
    )
    assert enabled.status_code == 200, enabled.text
    refreshed = await client.get(f"{BASE}/form", headers=superadmin_headers)
    assert refreshed.json()["public_form_enabled"] is True

    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    # A required custom field is checked even when the payload omits it.
    missing = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_payload(year, level, custom=None),
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["message_key"] == "error.custom_field.invalid"


async def test_unknown_custom_fields_are_rejected(client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    response = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_payload(year, level, custom={"not_a_field": "x"}),
    )
    assert response.status_code == 422
    assert response.json()["error"]["message_key"] == "error.custom_field.invalid"


# ------------------------------------------------------------- intake and numbers


async def test_preview_and_create_application_with_guardians(app, client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)

    payload = _payload(year, level, section_id=section["id"])
    preview = await client.post(f"{BASE}/preview", headers=superadmin_headers, json=payload)
    assert preview.status_code == 200, preview.text
    assert preview.json()["application_number"] == "ADM-2026-0001"
    assert preview.json()["full_name"] == "Abebe Kebede Tessema"
    assert preview.json()["guardian_count"] == 1
    assert preview.json()["level_code"] == "g5"
    assert preview.json()["section_code"] == "A"

    created = await client.post(BASE, headers=superadmin_headers, json=payload)
    assert created.status_code == 201, created.text
    application = created.json()
    assert application["application_number"] == "ADM-2026-0001"
    assert application["status"] == "applied"
    assert application["person"]["full_name"] == "Abebe Kebede Tessema"
    assert application["guardians"][0]["person"]["full_name"] == "Kebede Tessema Alemu"
    assert application["guardians"][0]["is_primary"] is True
    assert application["section_code"] == "A"
    assert application["row_version"] == 1
    assert application["duplicate_warnings"] == []

    second = await _create(
        client,
        superadmin_headers,
        year,
        level,
        person=_person(given_name_en="Hana", date_of_birth="2015-02-02"),
    )
    assert second["application_number"] == "ADM-2026-0002"

    duplicate = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_payload(
            year,
            level,
            person=None,
            person_id=application["person"]["id"],
        ),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "admissions.error.application_exists"

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert "admissions.application.create" in actions
    assert "admission.application_created" in await _events(app)


async def test_existing_person_application_and_duplicate_guardian_rules(
    client, superadmin_headers, seeded
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    applicant = await _person_row(client, superadmin_headers)

    created = await _create(client, superadmin_headers, year, level, person=None, person_id=applicant["id"])
    assert created["person"]["id"] == applicant["id"]

    guardian = await _person_row(client, superadmin_headers, **_guardian())
    twice = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_payload(
            year,
            level,
            person=_person(given_name_en="Selam"),
            guardians=[
                {"person_id": guardian["id"], "relationship": "father"},
                {"person_id": guardian["id"], "relationship": "mother"},
            ],
        ),
    )
    assert twice.status_code == 422
    assert twice.json()["error"]["message_key"] == "admissions.error.guardian_duplicate"

    self_applicant = await _person_row(
        client, superadmin_headers, **_person(given_name_en="Dawit", date_of_birth="2013-01-01")
    )
    self_guardian = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_payload(
            year,
            level,
            person=None,
            person_id=self_applicant["id"],
            guardians=[{"person_id": self_applicant["id"], "relationship": "other"}],
        ),
    )
    assert self_guardian.status_code == 422
    assert self_guardian.json()["error"]["message_key"] == "admissions.error.guardian_is_applicant"

    without_guardian = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_payload(year, level, person=_person(given_name_en="Marta"), guardians=[]),
    )
    assert without_guardian.status_code == 422
    assert without_guardian.json()["error"]["message_key"] == "admissions.error.guardian_required"


async def test_duplicate_warning_preview_matches_an_existing_person(
    client, superadmin_headers, seeded
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    await _person_row(client, superadmin_headers)

    preview = await client.post(f"{BASE}/preview", headers=superadmin_headers, json=_payload(year, level))
    assert preview.status_code == 200, preview.text
    warnings = preview.json()["duplicate_warnings"]
    assert warnings and warnings[0]["reason"] in {"same_names_and_dob", "similar_name_and_dob"}


async def test_application_numbers_are_atomic_under_concurrency(
    app, client, superadmin_headers, seeded
) -> None:
    from modules.admissions import numbering

    await _year(client, superadmin_headers)

    async def allocate() -> str:
        async with app.state.db.session() as session:
            allocation = await numbering.allocate_number(session)
            return allocation.application_number

    numbers = await asyncio.gather(*(allocate() for _ in range(8)))
    assert len(set(numbers)) == 8
    assert sorted(numbers) == [f"ADM-2026-{value:04d}" for value in range(1, 9)]


# ------------------------------------------------------------------- workflow


async def test_decision_workflow_enforces_transitions_and_the_entrance_test(
    client, superadmin_headers, seeded
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    application = await _create(client, superadmin_headers, year, level)

    skipped = await client.post(
        f"{BASE}/{application['id']}/decision",
        headers=superadmin_headers,
        json={"status": "offered", "row_version": application["row_version"]},
    )
    assert skipped.status_code == 409
    assert skipped.json()["error"]["message_key"] == "admissions.error.transition"

    reviewed = await _decide(client, superadmin_headers, application, "reviewed")
    no_score = await client.post(
        f"{BASE}/{application['id']}/decision",
        headers=superadmin_headers,
        json={"status": "test", "row_version": reviewed["row_version"]},
    )
    assert no_score.status_code == 422
    assert no_score.json()["error"]["message_key"] == "admissions.error.test_required"

    low = await _decide(client, superadmin_headers, reviewed, "test", entrance_test_score=40)
    below = await client.post(
        f"{BASE}/{application['id']}/decision",
        headers=superadmin_headers,
        json={"status": "offered", "row_version": low["row_version"]},
    )
    assert below.status_code == 422
    assert below.json()["error"]["message_key"] == "admissions.error.test_below_pass"

    rescored = await client.patch(
        f"{BASE}/{application['id']}",
        headers=superadmin_headers,
        json={"entrance_test_score": 80, "row_version": low["row_version"]},
    )
    assert rescored.status_code == 200, rescored.text
    assert rescored.json()["test_passed"] is True

    stale = await client.post(
        f"{BASE}/{application['id']}/decision",
        headers=superadmin_headers,
        json={"status": "offered", "row_version": reviewed["row_version"], "entrance_test_score": 80},
    )
    assert stale.status_code == 409

    offered = await _decide(client, superadmin_headers, rescored.json(), "offered")
    assert offered["status"] == "offered"
    assert offered["test_passed"] is True
    accepted = await _decide(client, superadmin_headers, offered, "accepted")
    assert accepted["status"] == "accepted"
    assert accepted["decided_by"] == "Super Admin"

    direct_enrol = await client.post(
        f"{BASE}/{application['id']}/decision",
        headers=superadmin_headers,
        json={"status": "enrolled", "row_version": accepted["row_version"]},
    )
    assert direct_enrol.status_code == 422

    terminal = await client.post(
        f"{BASE}/{application['id']}/decision",
        headers=superadmin_headers,
        json={"status": "reviewed", "row_version": accepted["row_version"]},
    )
    assert terminal.status_code == 409

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert "admissions.application.decide" in actions


async def test_disabling_the_entrance_test_skips_the_score_rule(client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    application = await _create(client, superadmin_headers, year, level)

    off = await client.put(
        f"{SETTINGS}/admissions/entrance_test.enabled",
        headers=superadmin_headers,
        json={"value": False},
    )
    assert off.status_code == 200, off.text

    reviewed = await _decide(client, superadmin_headers, application, "reviewed")
    offered = await _decide(client, superadmin_headers, reviewed, "offered")
    assert offered["status"] == "offered"
    assert offered["test_passed"] is None

    disabled_score = await client.patch(
        f"{BASE}/{application['id']}",
        headers=superadmin_headers,
        json={"entrance_test_score": 10, "row_version": offered["row_version"]},
    )
    assert disabled_score.status_code == 422
    assert disabled_score.json()["error"]["message_key"] == "admissions.error.test_disabled"


# ------------------------------------------------------------------ placement


async def test_conversion_auto_assigns_sections_by_capacity(client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section_a = await _section(client, superadmin_headers, year, level, "A", capacity=1)
    section_b = await _section(client, superadmin_headers, year, level, "B", capacity=1)

    first = await _create(client, superadmin_headers, year, level, person=_person(given_name_en="Hana"))
    second = await _create(client, superadmin_headers, year, level, person=_person(given_name_en="Selam"))
    third = await _create(client, superadmin_headers, year, level, person=_person(given_name_en="Dawit"))

    first = await _accept(client, superadmin_headers, first)
    first_preview = await client.get(f"{BASE}/{first['id']}/conversion", headers=superadmin_headers)
    assert first_preview.status_code == 200, first_preview.text
    assert first_preview.json()["section_source"] == "auto"
    assert first_preview.json()["section_code"] in {"A", "B"}
    converted_first = await _convert(client, superadmin_headers, first)
    assert converted_first["application"]["section_code"] in {"A", "B"}

    second = await _accept(client, superadmin_headers, second)
    converted_second = await _convert(client, superadmin_headers, second)
    assert {
        converted_first["application"]["section_code"],
        converted_second["application"]["section_code"],
    } == {"A", "B"}

    third = await _accept(client, superadmin_headers, third)
    full = await client.get(f"{BASE}/{third['id']}/conversion", headers=superadmin_headers)
    assert full.status_code == 200, full.text
    assert full.json()["can_convert"] is True
    assert full.json()["section_code"] is None
    assert "no_section_capacity" in full.json()["warnings"]

    converted_third = await _convert(client, superadmin_headers, third)
    assert converted_third["application"]["section_id"] is None
    assert "no_section_capacity" in converted_third["warnings"]

    explicit = await _create(
        client,
        superadmin_headers,
        year,
        level,
        person=_person(given_name_en="Marta"),
        section_id=section_a["id"],
    )
    explicit = await _accept(client, superadmin_headers, explicit)
    explicit_preview = await client.get(f"{BASE}/{explicit['id']}/conversion", headers=superadmin_headers)
    assert explicit_preview.json()["section_source"] == "application"
    assert explicit_preview.json()["section_code"] == section_a["code"]
    assert explicit_preview.json()["section_code"] == "A"
    assert section_b["code"] == "B"


async def test_conversion_creates_student_enrollment_guardians_and_accounts(
    app, client, superadmin_headers, seeded
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    guardian_login = f"guardian.{unique_email('admit')}"
    with_email = await _person_row(client, superadmin_headers, **_guardian(email=guardian_login))
    without_email = await _person_row(
        client,
        superadmin_headers,
        **_guardian(
            given_name_en="Almaz",
            father_name_en="Tesfaye",
            grandfather_name_en="Bekele",
            given_name_am="አልማዝ",
            father_name_am="ተስፋዬ",
            grandfather_name_am="በቀለ",
            date_of_birth="1990-03-03",
            email=None,
        ),
    )

    application = await _create(
        client,
        superadmin_headers,
        year,
        level,
        guardians=[
            {
                "person_id": with_email["id"],
                "relationship": "father",
                "is_primary": True,
                "wants_account": True,
            },
            {"person_id": without_email["id"], "relationship": "mother"},
        ],
    )

    refused = await client.get(f"{BASE}/{application['id']}/conversion", headers=superadmin_headers)
    assert refused.status_code == 200
    assert refused.json()["can_convert"] is False
    assert refused.json()["reason"] == "status_applied"

    application = await _accept(client, superadmin_headers, application)
    preview = await client.get(f"{BASE}/{application['id']}/conversion", headers=superadmin_headers)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["can_convert"] is True
    assert body["student_number"].startswith("STU-2026-")
    assert body["guardian_count"] == 2
    assert [item["action"] for item in body["accounts"]] == ["create"]

    converted = await _convert(client, superadmin_headers, application)
    assert converted["student_number"].startswith("STU-2026-")
    assert converted["application"]["status"] == "enrolled"
    assert converted["application"]["student_id"] == converted["student_id"]
    assert converted["application"]["student_number"] == converted["student_number"]
    assert len(converted["guardian_ids"]) == 2
    assert converted["accounts"][0]["action"] == "create"

    again = await client.post(
        f"{BASE}/{application['id']}/convert",
        headers=superadmin_headers,
        json={"row_version": converted["application"]["row_version"]},
    )
    assert again.status_code == 409
    assert again.json()["error"]["message_key"] == "admissions.error.already_converted"

    async with app.state.db.session() as session:
        user = (await session.execute(select(User).where(User.email == guardian_login))).scalar_one()
        assert user.must_change_password is True
        role_ids = (
            (await session.execute(select(UserRole.role_id).where(UserRole.user_id == user.id)))
            .scalars()
            .all()
        )
        parent_role = (await session.execute(select(Role).where(Role.key == "parent"))).scalar_one()
        assert parent_role.id in role_ids

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {
        "students.profile.create",
        "students.enrollments.create",
        "students.guardians.add",
        "admissions.guardian_account.create",
        "admissions.convert",
    } <= actions
    event_types = await _events(app)
    assert {
        "admission.application_created",
        "admission.decision",
        "admission.converted",
        "student.admitted",
        "student.enrolled",
    } <= set(event_types)


async def test_conversion_can_skip_guardian_accounts(app, client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    email = unique_email("skip-account")
    guardian = await _person_row(client, superadmin_headers, **_guardian(email=email))
    application = await _create(
        client,
        superadmin_headers,
        year,
        level,
        guardians=[{"person_id": guardian["id"], "wants_account": True}],
    )
    application = await _accept(client, superadmin_headers, application)
    converted = await _convert(client, superadmin_headers, application, create_guardian_accounts=False)
    assert converted["accounts"] == []
    async with app.state.db.session() as session:
        assert (await session.execute(select(User).where(User.email == email))).scalar_one_or_none() is None


# -------------------------------------------------------------- update/delete


async def test_update_delete_restore_and_optimistic_concurrency(client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    application = await _create(client, superadmin_headers, year, level)

    updated = await client.patch(
        f"{BASE}/{application['id']}",
        headers=superadmin_headers,
        json={"notes": "Bring the birth certificate", "row_version": application["row_version"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["notes"] == "Bring the birth certificate"
    assert updated.json()["row_version"] == application["row_version"] + 1

    stale = await client.patch(
        f"{BASE}/{application['id']}",
        headers=superadmin_headers,
        json={"notes": "Stale", "row_version": application["row_version"]},
    )
    assert stale.status_code == 409

    deleted = await client.delete(
        f"{BASE}/{application['id']}",
        headers=superadmin_headers,
        params={"row_version": updated.json()["row_version"], "reason": "Duplicate intake"},
    )
    assert deleted.status_code == 200, deleted.text
    assert (await client.get(f"{BASE}/{application['id']}", headers=superadmin_headers)).status_code == 404

    restored = await client.post(f"{BASE}/{application['id']}/restore", headers=superadmin_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["notes"] == "Bring the birth certificate"

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {
        "admissions.application.update",
        "admissions.application.delete",
        "admissions.application.restore",
    } <= actions

    accepted = await _accept(client, superadmin_headers, restored.json())
    converted = await _convert(client, superadmin_headers, accepted)
    refused = await client.delete(
        f"{BASE}/{application['id']}",
        headers=superadmin_headers,
        params={"row_version": converted["application"]["row_version"]},
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["message_key"] == "admissions.error.converted_delete"


async def test_a_closed_year_takes_no_applications(client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)

    opened = await client.post(f"{ACADEMICS}/academic-years/{year['id']}/open", headers=superadmin_headers)
    assert opened.status_code == 200, opened.text
    closed = await client.post(
        f"{ACADEMICS}/academic-years/{year['id']}/close",
        headers=superadmin_headers,
        params={"reason": "Year end"},
    )
    assert closed.status_code == 200, closed.text

    explicit = await client.post(BASE, headers=superadmin_headers, json=_payload(year, level))
    assert explicit.status_code == 409
    assert explicit.json()["error"]["message_key"] == "admissions.error.year_closed"

    implicit = await client.post(
        BASE,
        headers=superadmin_headers,
        json=_payload(year, level, year_id=None, person=_person(given_name_en="Hana")),
    )
    assert implicit.status_code == 409
    assert implicit.json()["error"]["message_key"] == "admissions.error.year_closed"


# -------------------------------------------------------------- documents/perms


async def test_documents_are_scoped_to_the_application(client, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    first = await _create(client, superadmin_headers, year, level)
    second = await _create(client, superadmin_headers, year, level, person=_person(given_name_en="Hana"))

    uploaded = await client.post(
        f"{BASE}/{first['id']}/documents",
        headers=superadmin_headers,
        files={"file": ("report.txt", b"previous school report", "text/plain")},
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


async def test_permissions_module_gate_navigation_and_ai_tools(
    app, client, superadmin_headers, seeded
) -> None:
    reader = await create_role(app, "admissions_viewer", [("admissions.view", "all")])
    reader_email = unique_email("admissions-viewer")
    await create_user(app, reader_email, roles=[reader.key])
    reader_headers = await login(client, reader_email)

    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    application = await _create(client, superadmin_headers, year, level)

    assert (await client.get(BASE, headers=reader_headers)).status_code == 200
    assert (await client.get(f"{BASE}/{application['id']}", headers=reader_headers)).status_code == 200
    assert (await client.get(f"{BASE}/form", headers=reader_headers)).status_code == 200
    denied_create = await client.post(
        BASE,
        headers=reader_headers,
        json=_payload(year, level, person=_person(given_name_en="Hana"), guardians=[]),
    )
    assert denied_create.status_code == 403
    denied_decide = await client.post(
        f"{BASE}/{application['id']}/decision",
        headers=reader_headers,
        json={"status": "reviewed", "row_version": application["row_version"]},
    )
    assert denied_decide.status_code == 403

    limited = await login(client, "limited@demo.school")
    assert (await client.get(BASE, headers=limited)).status_code == 403

    tools = await client.get("/api/v1/ai/tools", headers=superadmin_headers)
    keys = {tool["key"] for tool in tools.json()["items"]}
    assert {
        "admissions.search",
        "admissions.create",
        "admissions.decide",
        "admissions.convert",
    } <= keys
    convert = next(item for item in tools.json()["items"] if item["key"] == "admissions.convert")
    assert convert["risk"] == "write"
    assert convert["requires_confirmation"] is True

    nav = await client.get("/api/v1/auth/me/navigation", headers=reader_headers)
    assert "admissions" in [item["key"] for item in nav.json()["items"]]

    disabled = await client.put(
        "/api/v1/system/modules/admissions",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    blocked = await client.get(BASE, headers=superadmin_headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "MODULE_DISABLED"
    nav = await client.get("/api/v1/auth/me/navigation", headers=reader_headers)
    assert "admissions" not in [item["key"] for item in nav.json()["items"]]


# ------------------------------------------------------------ public form


async def _enable_public(client, headers, **values) -> None:
    settings = {"enabled": True, "min_seconds": 0, "rate_limit": 5}
    settings.update(values)
    for key, value in (
        ("form.public_enabled", settings["enabled"]),
        ("form.public_min_seconds", settings["min_seconds"]),
        ("form.public_rate_limit", settings["rate_limit"]),
    ):
        response = await client.put(f"{SETTINGS}/admissions/{key}", headers=headers, json={"value": value})
        assert response.status_code == 200, response.text


def _public_payload(form: dict, year: dict, level: dict, **overrides) -> dict:
    payload = {
        "form_token": form["form_token"],
        "person": _person(),
        "year_id": year["id"],
        "level_id": level["id"],
        "guardians": [{"person": _guardian(), "relationship": "father", "is_primary": True}],
    }
    payload.update(overrides)
    return payload


async def test_public_page_is_closed_until_the_school_turns_it_on(client, superadmin_headers, seeded) -> None:
    from modules.admissions.public import public_limiter

    public_limiter.reset()
    closed = await client.get(f"{BASE}/public/form")
    assert closed.status_code == 200, closed.text
    assert closed.json()["enabled"] is False
    assert closed.json()["form_token"] is None

    refused = await client.post(
        f"{BASE}/public/applications",
        json={
            "form_token": "anything",
            "person": _person(),
            "level_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert refused.status_code == 403
    assert refused.json()["error"]["message_key"] == "admissions.error.public_disabled"

    await _enable_public(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    opened = await client.get(f"{BASE}/public/form")
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["enabled"] is True
    assert body["form_token"]
    assert body["school_name"]
    assert [item["id"] for item in body["years"]] == [year["id"]]
    assert level["id"] in [item["id"] for item in body["levels"]]


async def test_public_submission_rejects_bots_and_impatient_clients(
    client, superadmin_headers, seeded
) -> None:
    from modules.admissions.public import public_limiter

    public_limiter.reset()
    await _enable_public(client, superadmin_headers, min_seconds=60)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    form = (await client.get(f"{BASE}/public/form")).json()

    too_fast = await client.post(f"{BASE}/public/applications", json=_public_payload(form, year, level))
    assert too_fast.status_code == 422
    assert too_fast.json()["error"]["message_key"] == "admissions.error.too_fast"

    public_limiter.reset()
    await _enable_public(client, superadmin_headers, min_seconds=0)
    form = (await client.get(f"{BASE}/public/form")).json()
    honeypot = await client.post(
        f"{BASE}/public/applications",
        json=_public_payload(form, year, level, website="https://spam.example"),
    )
    assert honeypot.status_code == 422
    assert honeypot.json()["error"]["message_key"] == "admissions.error.spam"

    expired = await client.post(
        f"{BASE}/public/applications",
        json=_public_payload(form, year, level, form_token="not-a-token"),
    )
    assert expired.status_code == 422
    assert expired.json()["error"]["message_key"] == "admissions.error.form_expired"


async def test_public_application_is_created_with_a_number_and_system_audit(
    app, client, superadmin_headers, seeded
) -> None:
    from core.audit.models import AuditLog
    from modules.admissions.public import public_limiter

    public_limiter.reset()
    await _enable_public(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    form = (await client.get(f"{BASE}/public/form")).json()

    submitted = await client.post(f"{BASE}/public/applications", json=_public_payload(form, year, level))
    assert submitted.status_code == 201, submitted.text
    body = submitted.json()
    assert body["application_number"] == "ADM-2026-0001"
    assert body["status"] == "applied"
    assert body["full_name"] == "Abebe Kebede Tessema"
    assert body["year_code"] == "2026-2027"
    assert body["level_code"] == "g5"
    assert "guardians" not in body

    async with app.state.db.session() as session:
        entry = (
            await session.execute(select(AuditLog).where(AuditLog.action == "admissions.application.create"))
        ).scalar_one()
        assert entry.actor_type == "system"
        assert entry.actor_id == "public"
        assert entry.via == "web"

    # The office sees the public application like any other.
    listed = await client.get(BASE, headers=superadmin_headers)
    assert listed.json()["items"][0]["application_number"] == "ADM-2026-0001"
    assert listed.json()["items"][0]["source"] == "public"


async def test_public_submissions_are_rate_limited_per_address(client, superadmin_headers, seeded) -> None:
    from modules.admissions.public import public_limiter

    public_limiter.reset()
    await _enable_public(client, superadmin_headers, rate_limit=1)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    form = (await client.get(f"{BASE}/public/form")).json()

    accepted = await client.post(f"{BASE}/public/applications", json=_public_payload(form, year, level))
    assert accepted.status_code == 201, accepted.text

    blocked = await client.post(
        f"{BASE}/public/applications",
        json=_public_payload(
            form,
            year,
            level,
            person=_person(given_name_en="Hana", date_of_birth="2015-02-02"),
        ),
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["message_key"] == "error.rate_limited"
    assert blocked.json()["error"]["details"]["retry_after"] >= 1
