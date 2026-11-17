"""P1-13: three-part names in both scripts, normalized search and duplicates."""

from __future__ import annotations

from core.people.models import Person, build_search_name, full_name, normalize_name, short_name


def make_person(**overrides) -> Person:
    values = {
        "given_name_en": "Abebe",
        "father_name_en": "Kebede",
        "grandfather_name_en": "Tessema",
        "given_name_am": "አበበ",
        "father_name_am": "ከበደ",
        "grandfather_name_am": "ተሰማ",
    }
    values.update(overrides)
    return Person(**values)


def test_full_and_short_names_follow_the_locale_with_fallback():
    person = make_person()
    assert full_name(person, "en") == "Abebe Kebede Tessema"
    assert full_name(person, "am") == "አበበ ከበደ ተሰማ"
    assert short_name(person, "en") == "Abebe Kebede"
    assert short_name(person, "am") == "አበበ ከበደ"

    latin_only = make_person(given_name_am=None, father_name_am=None, grandfather_name_am=None)
    assert full_name(latin_only, "am") == "Abebe Kebede Tessema"


def test_normalization_folds_geez_variants_and_latin_case():
    assert normalize_name("  ኃይሉ   ተስፋዬ ") == normalize_name("ሀይሉ ተስፋዬ")
    assert normalize_name("ABEBE-Kebede") == "abebe kebede"
    assert normalize_name("አበበ") == "አበበ"


def test_search_name_covers_both_scripts_and_contact_details():
    person = make_person(phone="+251 911 234 567")
    value = build_search_name(person)
    assert "abebe kebede tessema" in value
    assert "አበበ ከበደ ተሰማ" in value
    assert "0911234567" in value


async def test_searching_latin_finds_amharic_records_and_vice_versa(client, superadmin_headers):
    created = await client.post(
        "/api/v1/people",
        json={
            "given_name_en": "Abebe",
            "father_name_en": "Kebede",
            "grandfather_name_en": "Tessema",
            "given_name_am": "አበበ",
            "father_name_am": "ከበደ",
            "grandfather_name_am": "ተሰማ",
            "date_of_birth": "2012-05-01",
        },
        headers=superadmin_headers,
    )
    assert created.status_code == 200, created.text
    assert created.json()["duplicate_warnings"] == []

    latin = await client.get("/api/v1/people/search", params={"q": "Abebe Kebede"}, headers=superadmin_headers)
    assert latin.status_code == 200
    assert [item["given_name_am"] for item in latin.json()["items"]] == ["አበበ"]

    geez = await client.get("/api/v1/people/search", params={"q": "አበበ"}, headers=superadmin_headers)
    assert [item["given_name_en"] for item in geez.json()["items"]] == ["Abebe"]

    folded = await client.get("/api/v1/people/search", params={"q": "ሀበበ"}, headers=superadmin_headers)
    assert folded.json()["items"] == []


async def test_search_is_forgiving_of_small_typos(client, superadmin_headers):
    await client.post(
        "/api/v1/people",
        json={
            "given_name_en": "Meseret",
            "father_name_en": "Alemu",
            "grandfather_name_en": "Bekele",
            "date_of_birth": "2010-01-01",
        },
        headers=superadmin_headers,
    )
    response = await client.get(
        "/api/v1/people/search", params={"q": "Meserett Alemu"}, headers=superadmin_headers
    )
    assert response.status_code == 200
    assert response.json()["items"]


async def test_duplicate_detection_exact_and_similar_names_with_same_dob(client, superadmin_headers):
    base = {
        "given_name_en": "Hanna",
        "father_name_en": "Girma",
        "grandfather_name_en": "Wolde",
        "date_of_birth": "2011-09-09",
    }
    first = await client.post("/api/v1/people", json=base, headers=superadmin_headers)
    assert first.status_code == 200

    exact = await client.post("/api/v1/people", json=base, headers=superadmin_headers)
    warnings = exact.json()["duplicate_warnings"]
    assert warnings
    assert warnings[0]["reason"] == "same_names_and_dob"

    similar = await client.post(
        "/api/v1/people",
        json={**base, "father_name_en": "Girm"},
        headers=superadmin_headers,
    )

    assert any(
        item["reason"] == "similar_name_and_dob"
        for item in similar.json()["duplicate_warnings"]
    )

    different_dob = await client.post(
        "/api/v1/people", json={**base, "date_of_birth": "2012-01-01"}, headers=superadmin_headers
    )
    assert different_dob.json()["duplicate_warnings"] == []


async def test_partial_or_missing_names_are_rejected(client, superadmin_headers):
    missing = await client.post(
        "/api/v1/people", json={"given_name_en": "Only"}, headers=superadmin_headers
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["message_key"] == "error.invalid_name"

    partial_geez = await client.post(
        "/api/v1/people",
        json={"given_name_am": "አበበ", "father_name_am": "ከበደ"},
        headers=superadmin_headers,
    )
    assert partial_geez.status_code == 422


async def test_people_permissions_are_enforced(client, limited_headers):
    response = await client.get("/api/v1/people/search", params={"q": "abebe"}, headers=limited_headers)
    assert response.status_code == 403
