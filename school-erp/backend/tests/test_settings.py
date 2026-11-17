"""P1-03: typed layered settings, generated schema and audited changes."""

from __future__ import annotations

from core.audit.models import AuditLog
from core.settings.core_schema import CoreSettings
from core.settings.models import Setting
from core.settings.service import set_setting
from sqlalchemy import select

from tests.conftest import create_role, create_user, login

SETTINGS = "/api/v1/settings"


def _module(body: dict, key: str) -> dict:
    return next(item for item in body["items"] if item["module"] == key)


def _field(module: dict, key: str) -> dict:
    return next(item for item in module["fields"] if item["key"] == key)


async def test_schema_is_generated_from_the_module_models(client, superadmin_headers):
    response = await client.get(SETTINGS, headers=superadmin_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    core = _module(body, "core")
    assert core["label_key"] == "settings.module.core"
    name = _field(core, "school_profile.name")
    assert name["type"] == "string"
    assert name["value"] == "Demo Academy"
    assert name["source"] == "code"
    assert name["label_key"] == "settings.core.school_profile.name"

    calendar = _field(core, "school_profile.calendar")
    assert calendar["type"] == "enum"
    assert calendar["enum"] == ["ethiopian", "gregorian", "both"]

    first_level = _field(core, "academic_scope.first_level")
    assert first_level["type"] == "number"
    assert first_level["minimum"] == 0
    assert first_level["maximum"] == 12

    sample = _module(body, "sample")
    page_size = _field(sample, "page_size")
    assert page_size["type"] == "number"
    assert page_size["maximum"] == 100
    assert _field(sample, "allow_empty_notes")["type"] == "boolean"
    assert _field(sample, "default_author")["value"] == "Sample module"


async def test_code_central_instance_layering(client, app, superadmin_headers):
    key = "school_profile.default_language"
    initial = await client.get(SETTINGS, headers=superadmin_headers)
    assert _field(_module(initial.json(), "core"), key)["source"] == "code"
    assert _field(_module(initial.json(), "core"), key)["value"] == "en"

    async with app.state.db.session() as session:
        await set_setting(
            session,
            "core",
            CoreSettings,
            key,
            "am",
            layer="central",
        )
        await session.commit()

    central = await client.get(SETTINGS, headers=superadmin_headers)
    field = _field(_module(central.json(), "core"), key)
    assert field["value"] == "am"
    assert field["source"] == "central"

    instance = await client.put(f"{SETTINGS}/core/{key}", json={"value": "en"}, headers=superadmin_headers)
    assert instance.status_code == 200, instance.text
    assert instance.json()["value"] == "en"
    assert instance.json()["source"] == "instance"

    cleared = await client.delete(f"{SETTINGS}/core/{key}", headers=superadmin_headers)
    assert cleared.status_code == 200
    assert cleared.json()["value"] == "am"
    assert cleared.json()["source"] == "central"

    again = await client.delete(f"{SETTINGS}/core/{key}", headers=superadmin_headers)
    assert again.status_code == 200
    assert again.json()["source"] == "central"


async def test_values_are_validated_by_type(client, superadmin_headers):
    bad_enum = await client.put(
        f"{SETTINGS}/core/school_profile.calendar",
        json={"value": "lunar"},
        headers=superadmin_headers,
    )
    assert bad_enum.status_code == 422
    assert bad_enum.json()["error"]["message_key"] == "error.invalid_setting"
    assert bad_enum.json()["error"]["details"]["key"] == "school_profile.calendar"

    too_high = await client.put(
        f"{SETTINGS}/core/academic_scope.first_level",
        json={"value": 13},
        headers=superadmin_headers,
    )
    assert too_high.status_code == 422

    empty_name = await client.put(
        f"{SETTINGS}/core/school_profile.name",
        json={"value": ""},
        headers=superadmin_headers,
    )
    assert empty_name.status_code == 422

    sample = await client.put(f"{SETTINGS}/sample/page_size", json={"value": 0}, headers=superadmin_headers)
    assert sample.status_code == 422

    unknown_key = await client.put(
        f"{SETTINGS}/core/not.a.real.key",
        json={"value": "x"},
        headers=superadmin_headers,
    )
    assert unknown_key.status_code == 404

    unknown_module = await client.put(
        f"{SETTINGS}/nope/some.key", json={"value": "x"}, headers=superadmin_headers
    )
    assert unknown_module.status_code == 404


async def test_typed_values_round_trip(client, app, superadmin_headers):
    saved = await client.put(f"{SETTINGS}/sample/page_size", json={"value": 40}, headers=superadmin_headers)
    assert saved.status_code == 200
    assert saved.json()["value"] == 40

    flag = await client.put(
        f"{SETTINGS}/sample/allow_empty_notes",
        json={"value": True},
        headers=superadmin_headers,
    )
    assert flag.json()["value"] is True

    languages = await client.put(
        f"{SETTINGS}/core/school_profile.enabled_languages",
        json={"value": ["en", "am"]},
        headers=superadmin_headers,
    )
    assert languages.json()["value"] == ["en", "am"]

    async with app.state.db.session() as session:
        rows = (await session.execute(select(Setting))).scalars().all()
        stored = {row.key: row.value for row in rows}
    assert stored["page_size"] == 40
    assert stored["allow_empty_notes"] is True
    assert stored["school_profile.enabled_languages"] == ["en", "am"]


async def test_settings_changes_are_audited(client, app, superadmin_headers):
    await client.put(
        f"{SETTINGS}/core/branding.theme",
        json={"value": "ocean"},
        headers=superadmin_headers,
    )
    await client.delete(f"{SETTINGS}/core/branding.theme", headers=superadmin_headers)

    async with app.state.db.session() as session:
        entries = (
            (
                await session.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.entity_id == "core.branding.theme",
                        AuditLog.action.in_(["settings.update", "settings.clear"]),
                    )
                    .order_by(AuditLog.seq)
                )
            )
            .scalars()
            .all()
        )
    assert [entry.action for entry in entries] == ["settings.update", "settings.clear"]
    update, clear = entries
    assert update.actor_type == "user"
    assert update.before == {"value": "default", "source": "code"}
    assert update.after == {"value": "ocean", "source": "instance"}
    assert clear.before == {"value": "ocean", "source": "instance"}
    assert clear.after == {"value": "default", "source": "code"}


async def test_settings_permissions_and_navigation(client, app, seeded):
    await create_role(app, "settings_viewer", [("settings.view", "all"), ("ai.use", "all")])
    await create_user(app, "settings.viewer@demo.school", roles=["settings_viewer"])
    viewer = await login(client, "settings.viewer@demo.school")

    read = await client.get(SETTINGS, headers=viewer)
    assert read.status_code == 200
    write = await client.put(
        f"{SETTINGS}/core/school_profile.name",
        json={"value": "Renamed"},
        headers=viewer,
    )
    assert write.status_code == 403
    assert write.json()["error"]["code"] == "PERMISSION_DENIED"

    anonymous = await client.get(SETTINGS)
    assert anonymous.status_code == 401

    nav = await client.get("/api/v1/auth/me/navigation", headers=viewer)
    assert "settings" in {item["key"] for item in nav.json()["items"]}

    limited = await login(client, "limited@demo.school")
    nav = await client.get("/api/v1/auth/me/navigation", headers=limited)
    assert "settings" not in {item["key"] for item in nav.json()["items"]}
