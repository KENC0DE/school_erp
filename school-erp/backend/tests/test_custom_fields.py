"""P1-17: custom field definitions, role visibility and typed values."""

from __future__ import annotations

from tests.conftest import create_role, create_user, login


def definition(**overrides) -> dict:
    values = {
        "key": "blood_group",
        "label_key": "custom.person.blood_group",
        "field_type": "select",
        "options": ["A+", "A-", "O+", "O-"],
        "required": False,
        "order": 10,
    }
    values.update(overrides)
    return values


async def create_field(client, headers, entity_type="person", **overrides) -> dict:
    response = await client.post(
        f"/api/v1/custom-fields/{entity_type}",
        json=definition(**overrides),
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_definitions_are_created_updated_listed_and_soft_deleted(client, superadmin_headers):
    blood = await create_field(client, superadmin_headers)
    assert blood["entity_type"] == "person"
    assert blood["field_type"] == "select"
    assert blood["options"] == ["A+", "A-", "O+", "O-"]

    listed = await client.get(
        "/api/v1/custom-fields",
        params={"entity_type": "person"},
        headers=superadmin_headers,
    )
    assert listed.status_code == 200
    assert [item["key"] for item in listed.json()["items"]] == ["blood_group"]

    updated = await client.patch(
        f"/api/v1/custom-fields/{blood['id']}",
        json={"required": True, "order": 1},
        headers=superadmin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["required"] is True
    assert updated.json()["row_version"] == 2

    duplicate = await client.post(
        "/api/v1/custom-fields/person",
        json=definition(key="blood_group"),
        headers=superadmin_headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "error.custom_field.duplicate_key"

    deleted = await client.delete(
        f"/api/v1/custom-fields/{blood['id']}",
        params={"reason": "wrong field"},
        headers=superadmin_headers,
    )
    assert deleted.status_code == 200

    remaining = await client.get(
        "/api/v1/custom-fields",
        params={"entity_type": "person"},
        headers=superadmin_headers,
    )
    assert remaining.json()["items"] == []

    activity = await client.get(
        "/api/v1/audit/activity",
        params={"entity_type": "custom_field_def"},
        headers=superadmin_headers,
    )
    actions = {item["action"] for item in activity.json()["items"]}
    assert {"custom_fields.create", "custom_fields.update", "custom_fields.delete"} <= actions
    delete_entry = next(item for item in activity.json()["items"] if item["action"] == "custom_fields.delete")
    assert delete_entry["reason"] == "wrong field"
    assert delete_entry["revertible"] is False


async def test_definition_payloads_are_validated(client, superadmin_headers):
    bad_key = await client.post(
        "/api/v1/custom-fields/person",
        json=definition(key="Blood Group"),
        headers=superadmin_headers,
    )
    assert bad_key.status_code == 422

    bad_type = await client.post(
        "/api/v1/custom-fields/person",
        json=definition(field_type="geo"),
        headers=superadmin_headers,
    )
    assert bad_type.status_code == 422

    no_options = await client.post(
        "/api/v1/custom-fields/person",
        json=definition(options=[]),
        headers=superadmin_headers,
    )
    assert no_options.status_code == 422

    bad_bounds = await client.post(
        "/api/v1/custom-fields/person",
        json=definition(key="score", field_type="number", options=None, min_value="10", max_value="2"),
        headers=superadmin_headers,
    )
    assert bad_bounds.status_code == 422

    bad_pattern = await client.post(
        "/api/v1/custom-fields/person",
        json=definition(key="code", field_type="text", options=None, pattern="[unclosed"),
        headers=superadmin_headers,
    )
    assert bad_pattern.status_code == 422

    bad_entity = await client.post(
        "/api/v1/custom-fields/planet",
        json=definition(key="moons", field_type="integer", options=None),
        headers=superadmin_headers,
    )
    assert bad_entity.status_code == 422

    unknown_role = await client.post(
        "/api/v1/custom-fields/person",
        json=definition(visible_roles=["no_such_role"]),
        headers=superadmin_headers,
    )
    assert unknown_role.status_code == 422


async def test_values_are_validated_by_type(client, superadmin_headers):
    await create_field(client, superadmin_headers)
    for payload in (
        {
            "key": "nickname_code",
            "label_key": "custom.person.code",
            "field_type": "text",
            "max_length": 5,
            "pattern": "^[A-Z]+$",
        },
        {
            "key": "sibling_count",
            "label_key": "custom.person.siblings",
            "field_type": "integer",
            "min_value": 0,
            "max_value": 30,
        },
        {
            "key": "height",
            "label_key": "custom.person.height",
            "field_type": "number",
            "min_value": "0.5",
            "max_value": "3",
        },
        {"key": "is_boarding", "label_key": "custom.person.boarding", "field_type": "boolean"},
        {"key": "arrival_date", "label_key": "custom.person.arrival", "field_type": "date"},
        {
            "key": "clubs",
            "label_key": "custom.person.clubs",
            "field_type": "multiselect",
            "options": ["chess", "music", "sport"],
        },
    ):
        await create_field(client, superadmin_headers, **payload)

    good = await client.post(
        "/api/v1/custom-fields/person/validate",
        json={
            "values": {
                "blood_group": "O+",
                "nickname_code": "AB",
                "sibling_count": "3",
                "height": "1.75",
                "is_boarding": True,
                "arrival_date": "2026-09-01",
                "clubs": ["music", "music", "chess"],
            }
        },
        headers=superadmin_headers,
    )
    assert good.status_code == 200, good.text
    assert good.json()["values"] == {
        "blood_group": "O+",
        "nickname_code": "AB",
        "sibling_count": 3,
        "height": "1.75",
        "is_boarding": True,
        "arrival_date": "2026-09-01",
        "clubs": ["music", "chess"],
    }

    bad = await client.post(
        "/api/v1/custom-fields/person/validate",
        json={
            "values": {
                "blood_group": "Z",
                "nickname_code": "ab",
                "sibling_count": 3.5,
                "height": 1.5,
                "is_boarding": "yes",
                "arrival_date": "2026-02-30",
                "clubs": ["music", "football"],
                "mystery": 1,
            }
        },
        headers=superadmin_headers,
    )
    assert bad.status_code == 422
    errors = {item["field"]: item["code"] for item in bad.json()["error"]["details"]["errors"]}
    assert errors == {
        "blood_group": "OPTION",
        "nickname_code": "PATTERN",
        "sibling_count": "TYPE",
        "height": "TYPE",
        "is_boarding": "TYPE",
        "arrival_date": "TYPE",
        "clubs": "OPTION",
        "mystery": "UNKNOWN",
    }


async def test_required_and_bounds(client, superadmin_headers):
    await create_field(
        client,
        superadmin_headers,
        key="shoe_size",
        label_key="custom.person.shoe",
        field_type="integer",
        options=None,
        required=True,
        min_value=20,
        max_value=50,
    )
    missing = await client.post(
        "/api/v1/custom-fields/person/validate",
        json={"values": {}},
        headers=superadmin_headers,
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["details"]["errors"][0]["code"] == "REQUIRED"

    below = await client.post(
        "/api/v1/custom-fields/person/validate",
        json={"values": {"shoe_size": 10}},
        headers=superadmin_headers,
    )
    assert below.json()["error"]["details"]["errors"][0]["message_key"] == ("error.custom_field.min")

    partial = await client.post(
        "/api/v1/custom-fields/person/validate",
        json={"values": {}, "partial": True},
        headers=superadmin_headers,
    )
    assert partial.status_code == 200
    assert partial.json()["values"] == {}


async def test_field_visibility_follows_roles(app, client, superadmin_headers):
    public = await create_field(
        client, superadmin_headers, key="public_note", field_type="text", options=None
    )
    restricted = await create_field(
        client,
        superadmin_headers,
        key="senior_only",
        field_type="text",
        options=None,
        visible_roles=["super_admin"],
    )

    await create_role(
        app,
        "records_clerk",
        [("custom_fields.view", "all"), ("people.view", "all"), ("people.manage", "all")],
    )
    await create_user(app, "clerk@demo.school", display_name="Records Clerk", roles=["records_clerk"])
    clerk = await login(client, "clerk@demo.school")

    clerk_list = await client.get("/api/v1/custom-fields", params={"entity_type": "person"}, headers=clerk)
    assert [item["key"] for item in clerk_list.json()["items"]] == ["public_note"]

    admin_list = await client.get(
        "/api/v1/custom-fields", params={"entity_type": "person"}, headers=superadmin_headers
    )
    assert {item["key"] for item in admin_list.json()["items"]} == {
        "public_note",
        "senior_only",
    }

    # A user cannot reveal hidden definitions with a query flag.
    sneaky = await client.get(
        "/api/v1/custom-fields",
        params={"entity_type": "person", "include_hidden": True},
        headers=clerk,
    )
    assert [item["key"] for item in sneaky.json()["items"]] == ["public_note"]
    assert public["id"] != restricted["id"]


async def test_person_records_use_the_engine(client, superadmin_headers):
    await create_field(
        client,
        superadmin_headers,
        key="student_code",
        field_type="text",
        options=None,
        pattern="^[A-Z]{2}[0-9]{3}$",
        required=True,
    )
    await create_field(
        client,
        superadmin_headers,
        key="clubs",
        field_type="multiselect",
        options=["chess", "music"],
    )

    created = await client.post(
        "/api/v1/people",
        json={
            "given_name_en": "Liya",
            "father_name_en": "Tesfaye",
            "grandfather_name_en": "Bekele",
            "custom": {"student_code": "AA001", "clubs": ["chess"]},
        },
        headers=superadmin_headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["person"]["custom"] == {"student_code": "AA001", "clubs": ["chess"]}

    updated = await client.patch(
        f"/api/v1/people/{body['person']['id']}",
        json={"custom": {"clubs": ["music"], "student_code": "AA002"}},
        headers=superadmin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["custom"] == {"student_code": "AA002", "clubs": ["music"]}

    cleared = await client.patch(
        f"/api/v1/people/{body['person']['id']}",
        json={"custom": {"clubs": []}},
        headers=superadmin_headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["custom"] == {"student_code": "AA002"}

    invalid = await client.post(
        "/api/v1/people",
        json={
            "given_name_en": "Liya",
            "father_name_en": "Tesfaye",
            "grandfather_name_en": "Bekele",
            "custom": {"student_code": "bad"},
        },
        headers=superadmin_headers,
    )
    assert invalid.status_code == 422
    errors = invalid.json()["error"]["details"]["errors"]
    assert errors[0]["message_key"] == "error.custom_field.pattern"

    unknown = await client.post(
        "/api/v1/people",
        json={
            "given_name_en": "Liya",
            "father_name_en": "Tesfaye",
            "grandfather_name_en": "Bekele",
            "custom": {"student_code": "AA003", "mystery": "x"},
        },
        headers=superadmin_headers,
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["details"]["errors"][0]["code"] == "UNKNOWN"


async def test_view_and_manage_permissions_are_enforced(client, limited_headers, superadmin_headers):
    denied_list = await client.get(
        "/api/v1/custom-fields", params={"entity_type": "person"}, headers=limited_headers
    )
    assert denied_list.status_code == 403

    denied_create = await client.post(
        "/api/v1/custom-fields/person",
        json=definition(),
        headers=limited_headers,
    )
    assert denied_create.status_code == 403

    types = await client.get("/api/v1/custom-fields/entity-types", headers=superadmin_headers)
    assert types.status_code == 200
    assert {item["entity_type"] for item in types.json()["items"]} >= {
        "person",
        "student",
        "staff",
        "guardian",
        "admission_application",
    }
