"""P2-07: configurable student numbers with an atomic sequence."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from modules.students import numbering
from modules.students.number_formats import MAX_NUMBER_LENGTH, compile_format, render_number
from modules.students.settings import NumberingSettings
from pydantic import ValidationError

from tests.conftest import create_role, create_user, login, unique_email

BASE = "/api/v1/students"
ACADEMICS = "/api/v1/academics"
SETTINGS = "/api/v1/settings"
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


async def _year(
    client,
    headers,
    code: str = "2026-2027",
    *,
    start: str = "2026-09-11",
    end: str = "2027-06-30",
) -> dict:
    response = await client.post(
        f"{ACADEMICS}/academic-years",
        headers=headers,
        json={
            "code": code,
            "name": code.replace("-", "/"),
            "start_date": start,
            "end_date": end,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _level(client, headers, code: str = "g5") -> dict:
    response = await client.get(f"{ACADEMICS}/levels", headers=headers, params={"scope": "all"})
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["code"] == code)


async def _register(client, headers, **overrides) -> dict:
    payload = {"person": _person(), "admission_date": "2026-09-15"}
    payload.update(overrides)
    response = await client.post(BASE, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _set(client, headers, key: str, value) -> None:
    response = await client.put(
        f"{SETTINGS}/students/numbering.{key}",
        headers=headers,
        json={"value": value},
    )
    assert response.status_code == 200, response.text


def test_number_format_tokens_and_rendering() -> None:
    assert render_number("STU-{year}-{seq:04d}", year=2026, seq=7) == "STU-2026-0007"
    assert render_number("{year}/{seq:03d}", year=2027, seq=42) == "2027/042"
    assert render_number("{seq}", year=2026, seq=123456) == "123456"
    assert render_number("  {seq}-KG  ", year=2026, seq=1) == "1-KG"

    for bad in (
        "",
        "STU",
        "{seq}-{seq}",
        "{year}",
        "{dept}-{seq}",
        "{seq:d}",
        "{seq:4d}",
        "{seq:0d}",
        "{seq:040d}",
        "STU-{seq",
        "{seq}}",
    ):
        with pytest.raises(ValueError):
            compile_format(bad)

    with pytest.raises(ValueError):
        render_number("{seq}", year=2026, seq=int("9" * (MAX_NUMBER_LENGTH + 1)))


def test_year_scope_requires_a_year_token() -> None:
    with pytest.raises(ValidationError):
        NumberingSettings(scope="year", format="STU-{seq}")
    assert NumberingSettings(scope="year", format="STU-{year}-{seq}").scope == "year"
    assert NumberingSettings(scope="global", format="STU-{seq}").scope == "global"


async def test_settings_expose_numbering_defaults(client, superadmin_headers, seeded) -> None:
    response = await client.get(SETTINGS, headers=superadmin_headers)
    assert response.status_code == 200, response.text
    module = next(item for item in response.json()["items"] if item["module"] == "students")
    assert module["label_key"] == "settings.module.students"
    fields = {field["key"]: field for field in module["fields"]}

    assert fields["numbering.format"]["value"] == "STU-{year}-{seq:04d}"
    assert fields["numbering.format"]["label_key"] == "settings.students.numbering.format"
    assert fields["numbering.scope"]["type"] == "enum"
    assert fields["numbering.scope"]["enum"] == ["year", "global"]
    assert fields["numbering.scope"]["value"] == "year"
    assert fields["numbering.start"]["type"] == "number"
    assert fields["numbering.start"]["value"] == 1
    assert fields["numbering.start"]["minimum"] == 1


async def test_generated_numbers_follow_the_default_format(client, superadmin_headers, seeded) -> None:
    await _year(client, superadmin_headers)

    first = await _register(client, superadmin_headers)
    assert first["student_number"] == "STU-2026-0001"
    assert first["status"] == "applicant"

    preview = await client.get(f"{BASE}/number-preview", headers=superadmin_headers)
    assert preview.status_code == 200, preview.text
    assert preview.json()["student_number"] == "STU-2026-0002"
    assert preview.json()["scope"].startswith("year:")
    assert preview.json()["year"] == 2026

    # A preview never reserves the candidate.
    again = await client.get(f"{BASE}/number-preview", headers=superadmin_headers)
    assert again.json()["student_number"] == "STU-2026-0002"

    second = await _register(client, superadmin_headers, person=_person(given_name_en="Selam"))
    assert second["student_number"] == "STU-2026-0002"

    form_preview = await client.post(
        f"{BASE}/register/preview",
        headers=superadmin_headers,
        json={"person": _person(given_name_en="Hana", date_of_birth="2015-01-01")},
    )
    assert form_preview.status_code == 200, form_preview.text
    assert form_preview.json()["number_generated"] is True
    assert form_preview.json()["student_number"] == "STU-2026-0003"

    tools = await client.get("/api/v1/ai/tools", headers=superadmin_headers)
    preview_tool = next(item for item in tools.json()["items"] if item["key"] == "students.numbers.preview")
    assert preview_tool["risk"] == "read"

    actions = {item["action"] for item in (await _audit(client, superadmin_headers))}
    assert "students.register" in actions


async def _audit(client, headers) -> list[dict]:
    response = await client.get(ACTIVITY, headers=headers, params={"limit": 200})
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def test_custom_global_format_and_start(client, superadmin_headers, seeded) -> None:
    await _year(client, superadmin_headers)
    later = await _year(
        client,
        superadmin_headers,
        "2027-2028",
        start="2027-09-11",
        end="2028-06-30",
    )
    level = await _level(client, superadmin_headers)

    await _set(client, superadmin_headers, "scope", "global")
    await _set(client, superadmin_headers, "format", "ADM/{seq:03d}")
    await _set(client, superadmin_headers, "start", 100)

    first = await _register(client, superadmin_headers)
    assert first["student_number"] == "ADM/100"

    # A global counter ignores the enrollment year but still renders {seq}.
    enrolled = await _register(
        client,
        superadmin_headers,
        person=_person(given_name_en="Selam", date_of_birth="2015-02-02"),
        enrollment={"year_id": later["id"], "level_id": level["id"]},
    )
    assert enrolled["student_number"] == "ADM/101"
    assert enrolled["enrollment"]["year_code"] == "2027-2028"


async def test_year_scope_resets_per_enrolled_year(client, superadmin_headers, seeded) -> None:
    first_year = await _year(client, superadmin_headers)
    second_year = await _year(
        client,
        superadmin_headers,
        "2027-2028",
        start="2027-09-11",
        end="2028-06-30",
    )
    level = await _level(client, superadmin_headers)

    await _set(client, superadmin_headers, "format", "{year}/{seq:03d}")
    await _set(client, superadmin_headers, "start", 100)

    first = await _register(
        client,
        superadmin_headers,
        enrollment={"year_id": first_year["id"], "level_id": level["id"]},
    )
    assert first["student_number"] == "2026/100"

    second = await _register(
        client,
        superadmin_headers,
        person=_person(given_name_en="Selam", date_of_birth="2015-03-03"),
        enrollment={"year_id": second_year["id"], "level_id": level["id"]},
    )
    assert second["student_number"] == "2027/100"

    third = await _register(
        client,
        superadmin_headers,
        person=_person(given_name_en="Hana", date_of_birth="2015-04-04"),
    )
    # No enrollment: the latest year is preferred.
    assert third["student_number"] == "2027/101"

    preview_2026 = await client.get(
        f"{BASE}/number-preview",
        headers=superadmin_headers,
        params={"year_id": first_year["id"]},
    )
    assert preview_2026.status_code == 200, preview_2026.text
    assert preview_2026.json()["student_number"] == "2026/101"

    missing = await client.get(
        f"{BASE}/number-preview",
        headers=superadmin_headers,
        params={"year_id": str(uuid.uuid4())},
    )
    assert missing.status_code == 404


async def test_explicit_numbers_are_allowed_and_do_not_consume_the_sequence(
    client, superadmin_headers, seeded
) -> None:
    await _year(client, superadmin_headers)

    manual = await _register(client, superadmin_headers, student_number=" MANUAL-1 ")
    assert manual["student_number"] == "MANUAL-1"

    generated = await _register(client, superadmin_headers, person=_person(given_name_en="Selam"))
    assert generated["student_number"] == "STU-2026-0001"

    duplicate = await client.post(
        BASE,
        headers=superadmin_headers,
        json={"person": _person(given_name_en="Hana"), "student_number": "MANUAL-1"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "students.error.number_taken"

    # A blank field means "generate one" for the registration form.
    blank = await _register(
        client,
        superadmin_headers,
        student_number="   ",
        person=_person(given_name_en="Hana", date_of_birth="2015-05-05"),
    )
    assert blank["student_number"] == "STU-2026-0002"


async def test_invalid_numbering_settings_are_rejected(client, superadmin_headers, seeded) -> None:
    async def rejected(key: str, value) -> str:
        response = await client.put(
            f"{SETTINGS}/students/numbering.{key}",
            headers=superadmin_headers,
            json={"value": value},
        )
        assert response.status_code == 422, response.text
        return response.json()["error"]["message_key"]

    assert await rejected("format", "STU-{seq}-{seq}") == "error.invalid_setting"
    assert await rejected("format", "STU-{year}") == "error.invalid_setting"
    assert await rejected("format", "STU-{dept}-{seq}") == "error.invalid_setting"
    assert await rejected("format", "STU-{seq:4d}") == "error.invalid_setting"
    assert await rejected("format", "X" * 40 + "{seq}") == "error.invalid_setting"
    assert await rejected("start", 0) == "error.invalid_setting"

    # Year scope would collide across years without the {year} token.
    await _set(client, superadmin_headers, "scope", "global")
    await _set(client, superadmin_headers, "format", "STU-{seq}")
    assert await rejected("scope", "year") == "error.invalid_setting"


async def test_number_preview_requires_manage_permission(app, client, seeded) -> None:
    viewer = await create_role(app, "numbers_viewer", [("students.view", "all")])
    email = unique_email("numbers-viewer")
    await create_user(app, email, roles=[viewer.key])
    headers = await login(client, email)

    denied = await client.get(f"{BASE}/number-preview", headers=headers)
    assert denied.status_code == 403

    limited = await login(client, "limited@demo.school")
    assert (await client.get(f"{BASE}/number-preview", headers=limited)).status_code == 403


async def test_concurrent_allocation_never_duplicates(app, client, superadmin_headers, seeded) -> None:
    await _year(client, superadmin_headers)

    async def allocate() -> str:
        async with app.state.db.session() as session:
            allocation = await numbering.allocate_number(session)
            return allocation.student_number

    numbers = await asyncio.gather(*(allocate() for _ in range(8)))
    assert len(set(numbers)) == 8
    assert sorted(numbers) == [f"STU-2026-{value:04d}" for value in range(1, 9)]
