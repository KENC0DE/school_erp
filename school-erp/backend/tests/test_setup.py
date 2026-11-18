"""P1-24: first-run instance setup wizard."""

from __future__ import annotations

import base64
import io
from urllib.parse import urlsplit

from core.auth.models import User
from core.themes.models import Theme
from core.themes.tokens import DEFAULT_THEME
from PIL import Image
from sqlalchemy import select

from tests.conftest import create_user, login, unique_email

SETUP = "/api/v1/setup"
STATUS = f"{SETUP}/status"


def _png_data_url(colour: str = "#336699") -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), colour).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def payload(**overrides) -> dict:
    body = {
        "school": {
            "name": "Alpha Academy",
            "timezone": "Africa/Addis_Ababa",
            "calendar": "both",
            "default_language": "am",
            "enabled_languages": ["en", "am"],
            "first_level": 1,
            "last_level": 12,
            "theme": "default",
            "logo": _png_data_url(),
        },
        "admin": {
            "email": "founder@alpha.school",
            "password": "FounderPass#2026",
            "display_name": "Alpha Founder",
            "phone": "+251911000000",
            "locale": "am",
        },
    }
    for section, values in overrides.items():
        body[section].update(values)
    return body


async def _count_users(app) -> int:
    async with app.state.db.session() as session:
        return len((await session.execute(select(User))).scalars().all())


async def _actions(client, headers) -> list[str]:
    response = await client.get("/api/v1/audit/activity", headers=headers)
    assert response.status_code == 200, response.text
    return [item["action"] for item in response.json()["items"]]


async def test_setup_status_is_public_and_reports_the_instance_is_empty(client):
    response = await client.get(STATUS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["required"] is True
    assert body["completed"] is False
    assert body["school"]["name"] == "Demo Academy"
    assert body["languages"] == ["en", "am"]
    assert body["calendars"] == ["ethiopian", "gregorian", "both"]
    assert {item["key"] for item in body["themes"]} >= {"default"}
    assert body["limits"]["logo_max_bytes"] > 0


async def test_setup_creates_the_first_super_admin_and_school_profile(client, app):
    created = await client.post(SETUP, json=payload())
    assert created.status_code == 200, created.text
    body = created.json()

    assert body["user"]["email"] == "founder@alpha.school"
    assert body["user"]["roles"] == ["super_admin"]
    assert "*" in body["user"]["permissions"]
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]
    assert body["school"]["school_profile.name"] == "Alpha Academy"
    assert body["school"]["school_profile.default_language"] == "am"
    assert body["school"]["school_profile.calendar"] == "both"
    assert body["school"]["academic_scope.first_level"] == 1
    assert body["school"]["academic_scope.last_level"] == 12
    assert body["theme"] == "default"
    assert body["logo_url"].startswith("http://testserver/api/v1/files/content/")

    headers = {"Authorization": f"Bearer {body['tokens']['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["roles"] == ["super_admin"]

    # The chosen password works directly; the setup admin is not forced to
    # change it on first sign-in.
    tokens = await login(client, "founder@alpha.school", "FounderPass#2026")
    assert tokens["Authorization"].startswith("Bearer ")

    settings = await client.get("/api/v1/settings", headers=headers)
    assert settings.status_code == 200, settings.text
    core = next(item for item in settings.json()["items"] if item["module"] == "core")
    fields = {item["key"]: item for item in core["fields"]}
    assert fields["school_profile.name"]["value"] == "Alpha Academy"
    assert fields["school_profile.logo_file_id"]["value"]
    assert fields["branding.theme"]["value"] == "default"

    # The logo is public and served by signing the stored object.
    logo = await client.get(body["logo_url"])
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/png"
    assert logo.content.startswith(b"\x89PNG")

    status = await client.get(STATUS)
    assert status.status_code == 200
    assert status.json()["required"] is False
    assert status.json()["completed"] is True
    # Signed URLs embed an expiry timestamp, so compare the stable file path.
    assert urlsplit(status.json()["school"]["logo_url"]).path == urlsplit(body["logo_url"]).path

    actions = await _actions(client, headers)
    assert "setup.complete" in actions
    assert "auth.user.created" in actions
    assert "file.upload" in actions
    assert "theme.default" in actions


async def test_second_setup_attempt_is_refused(client, app):
    first = await client.post(SETUP, json=payload())
    assert first.status_code == 200, first.text

    second = await client.post(SETUP, json=payload(admin={"email": unique_email("second")}))
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SETUP_COMPLETE"
    assert second.json()["error"]["message_key"] == "error.setup_complete"
    assert await _count_users(app) == 1
    assert (await client.get(STATUS)).json()["required"] is False


async def test_setup_refused_when_any_user_already_exists(client, app):
    await create_user(app, unique_email("existing"), roles=[])
    response = await client.post(SETUP, json=payload())
    assert response.status_code == 409
    assert response.json()["error"]["message_key"] == "error.setup_complete"


async def test_setup_validates_password_language_grade_theme_and_logo(client, app):
    weak = await client.post(SETUP, json=payload(admin={"password": "short"}))
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "WEAK_PASSWORD"

    language = await client.post(
        SETUP,
        json=payload(
            school={"default_language": "am", "enabled_languages": ["en"]},
        ),
    )
    assert language.status_code == 422
    assert language.json()["error"]["message_key"] == "error.setup_language"

    grades = await client.post(SETUP, json=payload(school={"first_level": 9, "last_level": 4}))
    assert grades.status_code == 422
    assert grades.json()["error"]["message_key"] == "error.setup_grade_scope"

    theme = await client.post(SETUP, json=payload(school={"theme": "missing"}))
    assert theme.status_code == 404
    assert theme.json()["error"]["message_key"] == "error.theme.not_found"

    logo = await client.post(SETUP, json=payload(school={"logo": "data:image/png;base64,bm90IGFuIGltYWdl"}))
    assert logo.status_code == 415
    assert logo.json()["error"]["message_key"] == "error.file.content_mismatch"

    bad_data = await client.post(SETUP, json=payload(school={"logo": "not-a-data-url"}))
    assert bad_data.status_code == 422
    assert bad_data.json()["error"]["message_key"] == "error.setup_logo"

    # Every failed attempt rolled back, so setup is still available.
    assert await _count_users(app) == 0
    assert (await client.get(STATUS)).json()["required"] is True

    ok = await client.post(SETUP, json=payload())
    assert ok.status_code == 200, ok.text


async def test_setup_can_choose_another_available_theme(client, app):
    async with app.state.db.session() as session:
        session.add(
            Theme(
                key="ocean",
                name="Ocean",
                description="A test theme.",
                tokens=DEFAULT_THEME["tokens"],
                is_default=False,
                is_active=True,
                is_builtin=False,
                source="import",
            )
        )
        await session.commit()

    created = await client.post(SETUP, json=payload(school={"theme": "ocean"}))
    assert created.status_code == 200, created.text
    assert created.json()["theme"] == "ocean"

    status = await client.get(STATUS)
    assert status.json()["school"]["theme"] == "ocean"

    active = await client.get("/api/v1/themes/active")
    assert active.status_code == 200
    assert active.json()["key"] == "ocean"

    headers = {"Authorization": f"Bearer {created.json()['tokens']['access_token']}"}
    settings = await client.get("/api/v1/settings", headers=headers)
    core = next(item for item in settings.json()["items"] if item["module"] == "core")
    fields = {item["key"]: item for item in core["fields"]}
    assert fields["branding.theme"]["value"] == "ocean"


async def test_setup_without_a_logo_keeps_the_profile_and_issues_tokens(client):
    created = await client.post(SETUP, json=payload(school={"logo": None}))
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["logo_url"] is None
    assert body["user"]["locale"] == "am"

    status = await client.get(STATUS)
    assert status.json()["school"]["logo_url"] is None
    assert status.json()["school"]["name"] == "Alpha Academy"


async def test_setup_is_public_even_with_a_stale_authorization_header(client):
    # ``public_access`` never parses the header, so an expired browser token
    # cannot block the wizard before the first account exists.
    response = await client.post(SETUP, json=payload(), headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 200, response.text
    assert response.json()["user"]["roles"] == ["super_admin"]
