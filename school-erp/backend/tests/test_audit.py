"""P0-10: hash-chained audit, tamper detection, append-only guard."""

from __future__ import annotations

import pytest
from core.audit.service import verify_chain
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError


async def test_sample_mutation_writes_audit_entry(client, manager_headers, auditor_headers):
    created = await client.post(
        "/api/v1/sample/notes", json={"content": "Walking skeleton note"}, headers=manager_headers
    )
    assert created.status_code == 200, created.text
    note = created.json()
    assert note["content"] == "Walking skeleton note"

    activity = await client.get("/api/v1/audit/activity", headers=auditor_headers)
    assert activity.status_code == 200
    entry = next(item for item in activity.json()["items"] if item["action"] == "sample.notes.create")
    assert entry["module"] == "sample"
    assert entry["entity_id"] == note["id"]
    assert entry["after"]["content"] == "Walking skeleton note"
    assert entry["actor_type"] == "user"


async def test_chain_verifies_and_detects_inserted_tamper(app, client, manager_headers, auditor_headers):
    for index in range(3):
        response = await client.post(
            "/api/v1/sample/notes", json={"content": f"note {index}"}, headers=manager_headers
        )
        assert response.status_code == 200

    verify = await client.get("/api/v1/audit/verify", headers=auditor_headers)
    assert verify.status_code == 200
    assert verify.json()["ok"] is True
    assert verify.json()["entries"] >= 3

    # Simulate an attacker inserting a forged row directly into the table.
    async with app.state.db.session() as session:
        await session.execute(
            text(
                "INSERT INTO audit_log (ts, actor_type, via, action, prev_hash, hash) "
                "VALUES (CURRENT_TIMESTAMP, 'user', 'api', 'tamper.insert', 'deadbeef', 'not-the-right-hash')"
            )
        )
        await session.commit()
        result = await verify_chain(session)
    assert result["ok"] is False
    assert result["broken_seq"] is not None


async def test_audit_rows_cannot_be_updated_or_deleted(app, client, manager_headers):
    response = await client.post(
        "/api/v1/sample/notes", json={"content": "immutable"}, headers=manager_headers
    )
    assert response.status_code == 200

    async with app.state.db.session() as session:
        with pytest.raises((DBAPIError, IntegrityError)):
            await session.execute(text("UPDATE audit_log SET action = 'changed'"))
            await session.commit()
    async with app.state.db.session() as session:
        with pytest.raises((DBAPIError, IntegrityError)):
            await session.execute(text("DELETE FROM audit_log"))
            await session.commit()


async def test_outbox_receives_each_entry(app, client, manager_headers):
    await client.post("/api/v1/sample/notes", json={"content": "queued"}, headers=manager_headers)
    async with app.state.db.session() as session:
        rows = (await session.execute(text("SELECT COUNT(*) FROM audit_outbox"))).scalar_one()
        assert rows >= 1
