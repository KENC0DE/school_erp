"""P0-16 and P0-17: real traffic between the instance and the control plane."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.main import create_app
from controller_api.keys import ensure_signing_keys
from controller_api.main import create_controller_app
from controller_api.models import CPUser, Heartbeat
from controller_api.security import hash_password
from controller_api.settings import ControllerSettings
from core.audit.models import AuditLog, AuditOutbox
from core.audit.service import unshipped
from core.bootstrap import bootstrap
from core.controller_link.service import ControllerLinkError, enroll, heartbeat, ship_audit
from core.modules.models import LicenseState
from erp_shared.license import sign_payload
from sqlalchemy import select

from tests.conftest import (
    create_role,
    create_user,
    login,
    make_settings,
)


@pytest.fixture
async def controller(tmp_path):
    settings = ControllerSettings(
        app_env="test",
        controller_database_url=f"sqlite+aiosqlite:///{tmp_path}/controller-link.db",
        auto_create_schema=True,
        controller_secret_key="controller-link-secret-0123456789",
        directory_rate_limit_per_minute=100,
    )
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


async def _owner_headers(client):
    response = await client.post(
        "/controller/v1/auth/login",
        json={"email": "owner@controller.local", "password": "DevPass#2026"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _create_school(client, modules):
    headers = await _owner_headers(client)
    response = await client.post(
        "/controller/v1/schools",
        json={
            "name": "Demo Academy",
            "school_code": "DEMO",
            "api_base_url": "http://localhost:8000",
            "modules": modules,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json(), headers


async def _instance(tmp_path, **overrides):
    settings = make_settings(tmp_path, **overrides)
    application = create_app(settings)
    await application.state.db.create_all()
    await bootstrap(application)
    transport = httpx.ASGITransport(app=application)
    client = httpx.AsyncClient(transport=transport, base_url="http://instance")
    return application, client, settings


async def _seed_instance(app):
    await create_role(app, "super_admin", [("*", "all")], system=True)
    await create_role(
        app, "manager", [("sample.notes.view", "all"), ("sample.notes.create", "all"), ("ai.use", "all")]
    )
    await create_user(app, "superadmin@demo.school", display_name="Super Admin", roles=["super_admin"])
    await create_user(app, "manager@demo.school", display_name="Manager", roles=["manager"])


async def test_enroll_heartbeat_module_toggle_and_audit_shipping(controller, tmp_path):
    capp, cclient = controller
    school, owner_headers = await _create_school(cclient, ["sample"])
    app, client, settings = await _instance(tmp_path)
    await _seed_instance(app)
    try:
        async with app.state.db.session() as session:
            data = await enroll(
                session, settings, enrollment_token=school["enrollment_token"], client=cclient
            )
        assert data["instance_id"] == school["id"]
        async with app.state.db.session() as session:
            state = await session.get(LicenseState, "current")
            assert state is not None
            assert "sample" in state.modules
            assert state.controller_public_key

        superadmin = await login(client, "superadmin@demo.school")
        manager = await login(client, "manager@demo.school")
        assert (await client.get("/api/v1/sample/notes", headers=superadmin)).status_code == 200

        created = await client.post(
            "/api/v1/sample/notes", json={"content": "shipped to the vault"}, headers=manager
        )
        assert created.status_code == 200, created.text

        # The heartbeat carries the real local chain head so the controller can
        # compare it with the last ingested sequence.
        async with app.state.db.session() as session:
            await heartbeat(session, settings, client=cclient)
        async with app.state.db.session() as session:
            head = (
                await session.execute(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1))
            ).scalar_one()
        async with capp.state.db.session() as session:
            beat = (
                await session.execute(
                    select(Heartbeat)
                    .where(Heartbeat.school_id == school["id"])
                    .order_by(Heartbeat.received_at.desc())
                    .limit(1)
                )
            ).scalar_one()
        assert beat.payload["audit_chain_head"] == head.hash
        assert beat.payload["audit_seq"] == head.seq

        # Ship the audit batch; the controller verifies and stores the chain.
        async with app.state.db.session() as session:
            shipped = await ship_audit(session, settings, client=cclient)
        assert shipped["accepted"] >= 1
        vault = await cclient.get(f"/controller/v1/vault?school_id={school['id']}", headers=owner_headers)
        assert vault.status_code == 200
        actions = [item["action"] for item in vault.json()["items"]]
        assert "sample.notes.create" in actions
        status = await cclient.get(
            f"/controller/v1/vault/status?school_id={school['id']}", headers=owner_headers
        )
        assert status.json()["ok"] is True

        # Toggle the module off in the controller; the next heartbeat applies it.
        toggle = await cclient.patch(
            f"/controller/v1/schools/{school['id']}/modules",
            json={"key": "sample", "enabled": False},
            headers=owner_headers,
        )
        assert toggle.status_code == 200, toggle.text
        async with app.state.db.session() as session:
            await heartbeat(session, settings, client=cclient)
        blocked = await client.get("/api/v1/sample/notes", headers=superadmin)
        assert blocked.status_code == 403
        assert blocked.json()["error"]["code"] == "MODULE_DISABLED"

        # Re-enable and heartbeat again.
        await cclient.patch(
            f"/controller/v1/schools/{school['id']}/modules",
            json={"key": "sample", "enabled": True},
            headers=owner_headers,
        )
        async with app.state.db.session() as session:
            await heartbeat(session, settings, client=cclient)
        assert (await client.get("/api/v1/sample/notes", headers=superadmin)).status_code == 200
    finally:
        await client.aclose()
        await app.state.db.dispose()


async def test_controller_session_audit_and_read_only(controller, tmp_path):
    capp, cclient = controller
    school, owner_headers = await _create_school(cclient, ["sample"])
    async with capp.state.db.session() as session:
        license_key, _ = await ensure_signing_keys(session, capp.state.settings)
    application, client, settings = await _instance(
        tmp_path, controller_public_key=license_key.public_pem, instance_id=school["id"]
    )
    await _seed_instance(application)
    try:
        session_response = await cclient.post(
            f"/controller/v1/schools/{school['id']}/support-session",
            json={"reason": "Investigating a support ticket", "read_only": False},
            headers=owner_headers,
        )
        token = session_response.json()["token"]
        accepted = await client.post("/api/v1/auth/controller-session", json={"token": token})
        assert accepted.status_code == 200, accepted.text
        controller_headers = {"Authorization": f"Bearer {accepted.json()['access_token']}"}

        created = await client.post(
            "/api/v1/sample/notes", json={"content": "controller change"}, headers=controller_headers
        )
        assert created.status_code == 200, created.text
        activity = await client.get("/api/v1/audit/activity", headers=controller_headers)
        entry = next(item for item in activity.json()["items"] if item["action"] == "sample.notes.create")
        assert entry["actor_type"] == "controller"
        assert entry["via"] == "controller"
        assert entry["reason"] is None or entry["via"] == "controller"

        read_only = await cclient.post(
            f"/controller/v1/schools/{school['id']}/support-session",
            json={"reason": "Just looking", "read_only": True},
            headers=owner_headers,
        )
        ro_token = read_only.json()["token"]
        ro_session = await client.post("/api/v1/auth/controller-session", json={"token": ro_token})
        ro_headers = {"Authorization": f"Bearer {ro_session.json()['access_token']}"}
        denied = await client.post(
            "/api/v1/sample/notes", json={"content": "not allowed"}, headers=ro_headers
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "READ_ONLY_SESSION"
        allowed_read = await client.get("/api/v1/audit/activity", headers=ro_headers)
        assert allowed_read.status_code == 200
    finally:
        await client.aclose()
        await application.state.db.dispose()


async def test_expired_and_tampered_controller_tokens_are_rejected(controller, tmp_path):
    capp, cclient = controller
    school, _ = await _create_school(cclient, ["sample"])
    async with capp.state.db.session() as session:
        license_key, _ = await ensure_signing_keys(session, capp.state.settings)
    application, client, settings = await _instance(
        tmp_path, controller_public_key=license_key.public_pem, instance_id=school["id"]
    )
    await _seed_instance(application)
    try:
        expired = sign_payload(
            license_key.private_pem,
            {
                "instance_id": school["id"],
                "cp_user_id": "cp-1",
                "reason": "expired",
                "exp": 1,
            },
            kid=license_key.kid,
        )
        response = await client.post("/api/v1/auth/controller-session", json={"token": expired})
        assert response.status_code == 401

        good = await cclient.post(
            f"/controller/v1/schools/{school['id']}/support-session",
            json={"reason": "valid", "read_only": False},
            headers=await _owner_headers(cclient),
        )
        tampered = good.json()["token"][:-4] + "AAAA"
        response = await client.post("/api/v1/auth/controller-session", json={"token": tampered})
        assert response.status_code == 401
    finally:
        await client.aclose()
        await application.state.db.dispose()


class _UnavailableController:
    """Stands in for an unreachable controller (transport stays healthy)."""

    async def post(self, *_args, **_kwargs):
        return httpx.Response(
            503,
            text="maintenance",
            request=httpx.Request("POST", "http://controller/controller/v1/audit/ingest"),
        )


async def test_shipping_failure_backs_off_then_succeeds(controller, tmp_path):
    capp, cclient = controller
    school, _ = await _create_school(cclient, ["sample"])
    app, client, settings = await _instance(tmp_path)
    await _seed_instance(app)
    try:
        async with app.state.db.session() as session:
            await enroll(session, settings, enrollment_token=school["enrollment_token"], client=cclient)

        manager = await login(client, "manager@demo.school")
        created = await client.post("/api/v1/sample/notes", json={"content": "retry me"}, headers=manager)
        assert created.status_code == 200, created.text

        async with app.state.db.session() as session:
            assert await unshipped(session, limit=1000)
            with pytest.raises(ControllerLinkError):
                await ship_audit(session, settings, client=_UnavailableController())

            # The failure is committed, scheduled with backoff and hidden from
            # the next shipping tick.
            assert await unshipped(session, limit=1000) == []
            pending = (
                (await session.execute(select(AuditOutbox).where(AuditOutbox.shipped_at.is_(None))))
                .scalars()
                .all()
            )
            assert pending
            for row in pending:
                assert row.attempts >= 1
                assert row.last_attempt_at is not None
                assert row.last_error and "503" in row.last_error
                assert row.available_at is not None
                assert row.available_at > datetime.now(UTC)
                row.available_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()

        async with app.state.db.session() as session:
            result = await ship_audit(session, settings, client=cclient)
        assert result["accepted"] >= 1

        async with app.state.db.session() as session:
            assert await unshipped(session, limit=1000) == []
            shipped = (await session.execute(select(AuditOutbox))).scalars().all()
            assert shipped
            assert all(row.shipped_at is not None for row in shipped)
            assert all(row.last_error is None for row in shipped)
            assert any(row.attempts >= 1 for row in shipped)
    finally:
        await client.aclose()
        await app.state.db.dispose()
