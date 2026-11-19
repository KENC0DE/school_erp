"""P1-12: vault search, chain status and suspicious-pattern alerts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from controller_api.keys import ensure_signing_keys
from controller_api.main import create_controller_app
from controller_api.models import CPUser, School, VaultChainHead, VaultEntry
from controller_api.security import hash_password
from controller_api.settings import ControllerSettings


def settings_for(tmp_path, **overrides):
    values = {
        "app_env": "test",
        "controller_database_url": f"sqlite+aiosqlite:///{tmp_path}/vault.db",
        "auto_create_schema": True,
        "controller_secret_key": "controller-vault-secret-0123456789",
        "vault_mass_delete_threshold": 3,
        "vault_mass_delete_window_minutes": 10,
        "vault_off_hours_threshold": 2,
    }
    values.update(overrides)
    return ControllerSettings(**values)


@pytest.fixture
async def controller(tmp_path):
    application = create_controller_app(settings_for(tmp_path))
    await application.state.db.create_all()
    async with application.state.db.session() as session:
        await ensure_signing_keys(session, application.state.settings)
        session.add(
            CPUser(
                email="owner@controller.local",
                password_hash=hash_password("DevPass#2026"),
                display_name="Platform Owner",
                role="owner",
            )
        )
        school = School(name="Demo Academy", school_code="DEMO", api_base_url="http://localhost:8000")
        session.add(school)
        await session.flush()
        for seq in (1, 3):  # deliberately missing seq 2 -> gap
            session.add(
                VaultEntry(
                    school_id=school.id,
                    seq=seq,
                    prev_hash=None,
                    hash=f"h{seq}",
                    entry={
                        "seq": seq,
                        "action": "sample.notes.create",
                        "module": "sample",
                        "actor_type": "user",
                        "actor_id": "u-1",
                        "entity_type": "sample_note",
                        "entity_id": f"note-{seq}",
                        "ts": "2026-01-02T03:04:05+00:00",
                    },
                    chain_ok=True,
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
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_vault_search_and_filters(controller):
    app, client = controller
    headers = await owner_headers(client)
    async with app.state.db.session() as session:
        school = (await session.execute(__import__("sqlalchemy").select(School))).scalar_one()
        session.add(
            VaultEntry(
                school_id=school.id,
                seq=4,
                prev_hash="h3",
                hash="h4",
                entry={
                    "action": "auth.login",
                    "module": "core",
                    "actor_id": "u-2",
                    "ts": "2026-01-02T04:00:00+00:00",
                },
                chain_ok=False,
            )
        )
        await session.commit()

    search = await client.get("/controller/v1/vault", params={"q": "note-3"}, headers=headers)
    assert search.status_code == 200
    assert [item["entity_id"] for item in search.json()["items"]] == ["note-3"]

    by_action = await client.get("/controller/v1/vault", params={"action": "auth.login"}, headers=headers)
    assert [item["action"] for item in by_action.json()["items"]] == ["auth.login"]

    broken = await client.get("/controller/v1/vault", params={"chain_ok": False}, headers=headers)
    assert [item["chain_ok"] for item in broken.json()["items"]] == [False]


async def test_chain_status_and_scan_reports_gap_and_chain_break(controller):
    app, client = controller
    headers = await owner_headers(client)
    async with app.state.db.session() as session:
        school = (await session.execute(__import__("sqlalchemy").select(School))).scalar_one()
        session.add(VaultChainHead(school_id=school.id, last_seq=3, last_hash="h3"))
        await session.commit()
        school_id = school.id

    status = await client.get("/controller/v1/vault/status", params={"school_id": school_id}, headers=headers)
    assert status.status_code == 200
    assert status.json()["last_seq"] == 3
    assert status.json()["broken_entries"] == 0

    scanned = await client.post("/controller/v1/vault/scan", params={"school_id": school_id}, headers=headers)
    assert scanned.status_code == 200, scanned.text
    kinds = {item["kind"] for item in scanned.json()["items"]}
    assert "AUDIT_GAP" in kinds

    alerts = await client.get("/controller/v1/vault/alerts", params={"school_id": school_id}, headers=headers)
    messages = " ".join(item["message"] for item in alerts.json()["items"])
    assert "Expected seq 2" in messages


async def test_mass_deletes_and_off_hours_grade_changes_raise_alerts(controller):
    app, client = controller
    headers = await owner_headers(client)
    async with app.state.db.session() as session:
        from sqlalchemy import select

        school = (await session.execute(select(School))).scalar_one()
        start = datetime(2026, 1, 5, 23, 0, tzinfo=UTC)
        for index in range(3):
            session.add(
                VaultEntry(
                    school_id=school.id,
                    seq=10 + index,
                    prev_hash=None,
                    hash=f"d{index}",
                    entry={
                        "action": "students.delete",
                        "module": "students",
                        "actor_id": "u-9",
                        "ts": (start + timedelta(minutes=index)).isoformat(),
                    },
                    chain_ok=True,
                )
            )
        for index in range(2):
            session.add(
                VaultEntry(
                    school_id=school.id,
                    seq=20 + index,
                    prev_hash=None,
                    hash=f"g{index}",
                    entry={
                        "action": "assessment.marks.update",
                        "module": "assessment",
                        "actor_id": "u-8",
                        "ts": (start + timedelta(minutes=index)).isoformat(),
                    },
                    chain_ok=True,
                )
            )
        await session.commit()
        school_id = school.id

    scanned = await client.post("/controller/v1/vault/scan", params={"school_id": school_id}, headers=headers)
    kinds = {item["kind"] for item in scanned.json()["items"]}
    assert "MASS_DELETE" in kinds
    assert "OFF_HOURS_GRADE_CHANGE" in kinds

    first = scanned.json()["items"][0]["id"]
    resolved = await client.post(f"/controller/v1/vault/alerts/{first}/resolve", headers=headers)
    assert resolved.status_code == 200
    remaining = await client.get(
        "/controller/v1/vault/alerts", params={"school_id": school_id}, headers=headers
    )
    assert first not in {item["id"] for item in remaining.json()["items"]}
