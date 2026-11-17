from __future__ import annotations

import time

import httpx
import jwt
import pytest
from controller_api.keys import ensure_signing_keys
from controller_api.main import create_controller_app
from controller_api.models import CPUser
from controller_api.security import hash_password
from controller_api.settings import ControllerSettings
from erp_shared.license import LicenseError, verify_payload


def settings_for(tmp_path, **overrides) -> ControllerSettings:
    values = {
        "app_env": "test",
        "controller_database_url": f"sqlite+aiosqlite:///{tmp_path}/controller.db",
        "auto_create_schema": True,
        "controller_secret_key": "controller-test-secret-0123456789",
        "access_token_minutes": 60,
        "directory_rate_limit_per_minute": 30,
    }
    values.update(overrides)
    return ControllerSettings(**values)


@pytest.fixture
async def controller(tmp_path):
    settings = settings_for(tmp_path)
    application = create_controller_app(settings)
    await application.state.db.create_all()
    async with application.state.db.session() as session:
        await ensure_signing_keys(session, settings)
        session.add(
            CPUser(
                email="owner@controller.local",
                password_hash=hash_password("DevPass#2026"),
                display_name="Platform Owner",
                role="owner",
            )
        )
        await session.commit()
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://controller") as client:
        yield application, client
    await application.state.db.dispose()


async def owner_headers(client):
    response = await client.post(
        "/controller/v1/auth/login",
        json={"email": "owner@controller.local", "password": "DevPass#2026"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_school(controller, client, *, code="DEMO", status="active", modules=None):
    app, _ = controller
    headers = await owner_headers(client)
    response = await client.post(
        "/controller/v1/schools",
        json={
            "name": "Demo Academy",
            "school_code": code,
            "api_base_url": "http://localhost:8000",
            "modules": modules if modules is not None else ["sample"],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    if status != "active":
        await client.patch(f"/controller/v1/schools/{body['id']}", json={"status": status}, headers=headers)
    async with app.state.db.session() as session:
        license_key, directory_key = await ensure_signing_keys(session, app.state.settings)
    return body, headers, license_key, directory_key


async def test_login_and_me(controller):
    _, client = controller
    headers = await owner_headers(client)
    me = await client.get("/controller/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "owner"


async def test_bad_login(controller):
    _, client = controller
    response = await client.post(
        "/controller/v1/auth/login",
        json={"email": "owner@controller.local", "password": "nope"},
    )
    assert response.status_code == 401


async def test_directory_record_verifies_and_hides_unknown_codes(controller):
    _, client = controller
    _, _, _, directory_key = await create_school(controller, client)
    response = await client.get("/controller/v1/directory/resolve", params={"code": "DEMO"})
    assert response.status_code == 200
    record = response.json()
    assert record["kid"] == directory_key.kid
    assert record["status"] == "active"
    assert record["api_base_url"] == "http://localhost:8000"
    claims = verify_payload(record.pop("signature"), directory_key.public_pem)
    assert claims["name"] == "Demo Academy"
    assert claims["instance_id"] == record["instance_id"]

    tampered = {**record, "api_base_url": "https://evil.example"}
    from erp_shared.license import sign_payload

    tampered["signature"] = sign_payload(directory_key.private_pem, tampered, kid=directory_key.kid)
    # A token signed for different content must not validate against the original record.
    original = await client.get("/controller/v1/directory/resolve", params={"code": "DEMO"})
    with pytest.raises(LicenseError):
        verify_payload(original.json()["signature"], directory_key.public_pem, expected_kid="wrong")

    unknown = await client.get("/controller/v1/directory/resolve", params={"code": "NOPE"})
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "NOT_FOUND"


async def test_suspended_school_is_resolved_with_status(controller):
    _, client = controller
    await create_school(controller, client, code="SUSP", status="suspended")
    response = await client.get("/controller/v1/directory/resolve", params={"code": "SUSP"})
    assert response.status_code == 200
    assert response.json()["status"] == "suspended"


async def test_directory_rate_limit(tmp_path):
    settings = settings_for(tmp_path, directory_rate_limit_per_minute=2)
    application = create_controller_app(settings)
    await application.state.db.create_all()
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://controller") as client:
        for _ in range(2):
            await client.get("/controller/v1/directory/resolve", params={"code": "DEMO"})
        blocked = await client.get("/controller/v1/directory/resolve", params={"code": "DEMO"})
        assert blocked.status_code == 429
    await application.state.db.dispose()


async def test_key_rotation_by_kid(controller):
    app, client = controller
    _, _, _, directory_key = await create_school(controller, client)
    async with app.state.db.session() as session:
        from controller_api.models import SigningKey
        from erp_shared.license import generate_keypair

        pair = generate_keypair()
        session.add(
            SigningKey(
                key_type="directory",
                kid="k2",
                private_pem=pair.private_key,
                public_pem=pair.public_key,
                active=True,
            )
        )
        await session.commit()
    keys = await client.get("/controller/v1/directory/keys")
    records = keys.json()["items"]
    assert {item["kid"] for item in records} >= {"k1", "k2"}
    resolved = await client.get("/controller/v1/directory/resolve", params={"code": "DEMO"})
    kid = resolved.json()["kid"]
    public = next(item["public_key"] for item in records if item["kid"] == kid)
    verify_payload(resolved.json()["signature"], public, expected_kid=kid)


async def test_support_token_expiry_and_tamper(controller):
    app, client = controller
    school, headers, license_key, _ = await create_school(controller, client)
    good = await client.post(
        f"/controller/v1/schools/{school['id']}/support-session",
        json={"reason": "Helping the registrar", "read_only": True},
        headers=headers,
    )
    assert good.status_code == 200
    claims = verify_payload(good.json()["token"], license_key.public_pem)
    assert claims["read_only"] is True
    assert claims["reason"] == "Helping the registrar"

    expired = jwt.encode(
        {
            "instance_id": school["id"],
            "cp_user_id": "x",
            "reason": "expired",
            "exp": int(time.time()) - 60,
        },
        license_key.private_pem,
        algorithm="EdDSA",
        headers={"kid": license_key.kid},
    )
    with pytest.raises(LicenseError):
        verify_payload(expired, license_key.public_pem)
