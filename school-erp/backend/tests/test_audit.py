"""P0-10 / P1-09: hash-chained audit, tamper detection, append-only guard,
read auditing, actor/channel vocabularies and shipping retries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from core.audit.constants import ACTOR_TYPES, VIA_CHANNELS
from core.audit.models import AuditLog, AuditOutbox
from core.audit.service import (
    chain_lock_statement,
    record,
    retry_delay,
    verify_chain,
)
from core.auth.principal import Principal
from sqlalchemy import select, text
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


async def test_entry_stores_actor_channel_and_on_behalf_of(app):
    actor = Principal(
        actor_id="assistant-1",
        actor_type="ai",
        via="ai",
        on_behalf_of="user-42",
        reason="Drafted from a teacher request",
    )
    async with app.state.db.session() as session:
        row = await record(
            session,
            action="students.notes.propose",
            module="students",
            entity_type="note",
            entity_id="note-1",
            after={"text": "Suggested remark"},
            actor=actor,
            ip="10.0.0.5",
            user_agent="erp-ai/1.0",
        )
        await session.commit()
        seq = row.seq

    async with app.state.db.session() as session:
        stored = await session.get(AuditLog, seq)
        assert stored is not None
        assert stored.actor_type in ACTOR_TYPES
        assert stored.via in VIA_CHANNELS
        assert stored.actor_type == "ai"
        assert stored.actor_id == "assistant-1"
        assert stored.via == "ai"
        assert stored.on_behalf_of == "user-42"
        assert stored.reason == "Drafted from a teacher request"
        assert stored.ip == "10.0.0.5"
        assert stored.user_agent == "erp-ai/1.0"
        assert stored.request_id is None
        assert stored.hash
        assert (await verify_chain(session))["ok"] is True


async def test_invalid_actor_type_or_channel_is_rejected(app):
    async with app.state.db.session() as session:
        with pytest.raises(ValueError):
            await record(
                session,
                action="bad.actor",
                actor=Principal(actor_id="x", actor_type="robot", via="web"),
            )
        with pytest.raises(ValueError):
            await record(session, action="bad.via", via="carrier-pigeon")


async def test_sensitive_reads_are_audited(app, client, manager_headers, auditor_headers):
    created = await client.post("/api/v1/sample/notes", json={"content": "read me"}, headers=manager_headers)
    assert created.status_code == 200
    note_id = created.json()["id"]

    me = await client.get("/api/v1/auth/me", headers=auditor_headers)
    assert me.status_code == 200
    auditor_id = me.json()["id"]

    # Single-entry history: full before/after is sensitive, so the read is audited.
    async with app.state.db.session() as session:
        seq = (
            await session.execute(
                select(AuditLog.seq)
                .where(AuditLog.entity_id == note_id)
                .order_by(AuditLog.seq.desc())
                .limit(1)
            )
        ).scalar_one()
    detail = await client.get(f"/api/v1/audit/activity/{seq}", headers=auditor_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["on_behalf_of"] is None

    # Effective permissions are sensitive too. Mobile clients identify themselves
    # through X-Client-Via; the server accepts only client channels.
    permissions = await client.get(
        f"/api/v1/rbac/users/{auditor_id}/permissions",
        headers={**auditor_headers, "X-Client-Via": "mobile"},
    )
    assert permissions.status_code == 200, permissions.text

    async with app.state.db.session() as session:
        reads = (
            (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.action.in_(["audit.activity.read", "rbac.permissions.read"]))
                    .order_by(AuditLog.seq)
                )
            )
            .scalars()
            .all()
        )
    actions = {row.action: row for row in reads}
    assert set(actions) == {"audit.activity.read", "rbac.permissions.read"}
    assert actions["audit.activity.read"].actor_id == auditor_id
    assert actions["audit.activity.read"].entity_id == str(seq)
    assert actions["audit.activity.read"].via == "web"
    assert actions["rbac.permissions.read"].actor_id == auditor_id
    assert actions["rbac.permissions.read"].entity_id == auditor_id
    assert actions["rbac.permissions.read"].via == "mobile"


async def test_controller_channel_cannot_be_claimed_by_a_client_header(app, client, auditor_headers):
    me = await client.get("/api/v1/auth/me", headers=auditor_headers)
    auditor_id = me.json()["id"]
    headers = {**auditor_headers, "X-Client-Via": "controller"}
    response = await client.get(f"/api/v1/rbac/users/{auditor_id}/permissions", headers=headers)
    assert response.status_code == 200, response.text

    async with app.state.db.session() as session:
        read = (
            await session.execute(
                select(AuditLog)
                .where(
                    AuditLog.action == "rbac.permissions.read",
                    AuditLog.entity_id == auditor_id,
                )
                .order_by(AuditLog.seq.desc())
                .limit(1)
            )
        ).scalar_one()
    assert read.via == "web"


def test_retry_backoff_is_exponential_and_capped():
    assert retry_delay(1, base_seconds=30, max_seconds=3_600) == timedelta(seconds=30)
    assert retry_delay(2, base_seconds=30, max_seconds=3_600) == timedelta(seconds=60)
    assert retry_delay(3, base_seconds=30, max_seconds=3_600) == timedelta(seconds=120)
    assert retry_delay(20, base_seconds=30, max_seconds=3_600) == timedelta(seconds=3_600)


def test_sequence_lock_only_applies_to_postgresql():
    assert chain_lock_statement("postgresql") == "SELECT pg_advisory_xact_lock(:key)"
    assert chain_lock_statement("sqlite") is None


async def test_unshipped_skips_rows_waiting_for_a_retry(app):
    from core.audit.service import unshipped

    async with app.state.db.session() as session:
        row = await record(session, action="retry.probe")
        await session.commit()
        outbox = (
            await session.execute(select(AuditOutbox).where(AuditOutbox.audit_seq == row.seq))
        ).scalar_one()
        assert outbox.available_at is None
        assert any(item.id == outbox.id for item in await unshipped(session, limit=100))

        outbox.available_at = datetime.now(UTC) + timedelta(minutes=5)
        outbox.attempts = 1
        outbox.last_error = "controller unavailable"
        await session.commit()

        waiting = [item.id for item in await unshipped(session, limit=100)]
        assert outbox.id not in waiting
