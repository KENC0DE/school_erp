"""P1-11: revert and restore create new entries and never edit history."""

from __future__ import annotations

from core.audit.models import AuditLog
from sqlalchemy import select


async def _note_activity(client, headers, note_id):
    response = await client.get(
        "/api/v1/audit/activity",
        params={"entity_type": "sample_note", "entity_id": note_id},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def test_revert_updates_entity_and_links_the_new_entry(
    app, client, manager_headers, superadmin_headers, auditor_headers
):
    created = await client.post("/api/v1/sample/notes", json={"content": "original"}, headers=manager_headers)
    assert created.status_code == 200
    note_id = created.json()["id"]
    version = created.json()["row_version"]

    updated = await client.patch(
        f"/api/v1/sample/notes/{note_id}",
        json={"content": "changed", "row_version": version},
        headers=manager_headers,
    )
    assert updated.status_code == 200, updated.text

    entries = await _note_activity(client, superadmin_headers, note_id)
    update_entry = next(item for item in entries if item["action"] == "sample.notes.update")
    assert update_entry["revertible"] is True
    original_before = update_entry["before"]
    original_after = update_entry["after"]

    denied = await client.post(
        f"/api/v1/audit/activity/{update_entry['seq']}/revert",
        json={"reason": "wrong value"},
        headers=auditor_headers,
    )
    assert denied.status_code == 403

    reverted = await client.post(
        f"/api/v1/audit/activity/{update_entry['seq']}/revert",
        json={"reason": "wrong value"},
        headers=superadmin_headers,
    )
    assert reverted.status_code == 200, reverted.text
    body = reverted.json()
    assert body["reverted_seq"] == update_entry["seq"]

    note = await client.get(f"/api/v1/sample/notes/{note_id}", headers=manager_headers)
    assert note.json()["content"] == "original"

    entries = await _note_activity(client, superadmin_headers, note_id)
    revert_entry = next(item for item in entries if item["seq"] == body["audit_seq"])
    assert revert_entry["action"] == "sample_note.revert"
    assert revert_entry["reverts_id"] == str(update_entry["seq"])
    assert revert_entry["reason"] == "wrong value"
    assert revert_entry["before"] == original_after
    assert revert_entry["after"]["content"] == "original"

    # The original entry is byte-for-byte untouched.
    async with app.state.db.session() as session:
        stored = (
            await session.execute(select(AuditLog).where(AuditLog.seq == update_entry["seq"]))
        ).scalar_one()
        assert stored.before == original_before
        assert stored.after == original_after
        assert stored.reverts_id is None


async def test_revert_requires_a_reason_and_a_revertible_entity(client, superadmin_headers):
    created = await client.post(
        "/api/v1/sample/notes", json={"content": "reason please"}, headers=superadmin_headers
    )
    note_id = created.json()["id"]
    entries = await _note_activity(client, superadmin_headers, note_id)
    create_entry = next(item for item in entries if item["action"] == "sample.notes.create")

    empty = await client.post(
        f"/api/v1/audit/activity/{create_entry['seq']}/revert",
        json={"reason": ""},
        headers=superadmin_headers,
    )
    assert empty.status_code == 422

    missing = await client.post(
        "/api/v1/audit/activity/999999/revert",
        json={"reason": "nope"},
        headers=superadmin_headers,
    )
    assert missing.status_code == 404


async def test_restore_brings_back_a_soft_deleted_note(client, superadmin_headers, manager_headers):
    created = await client.post(
        "/api/v1/sample/notes", json={"content": "delete me"}, headers=superadmin_headers
    )
    note_id = created.json()["id"]

    deleted = await client.delete(f"/api/v1/sample/notes/{note_id}", headers=superadmin_headers)
    assert deleted.status_code == 200
    entries = await _note_activity(client, superadmin_headers, note_id)
    delete_entry = next(item for item in entries if item["action"] == "sample.notes.delete")
    assert delete_entry["revertible"] is True

    missing = await client.get(f"/api/v1/sample/notes/{note_id}", headers=manager_headers)
    assert missing.status_code == 404

    restored = await client.post(
        f"/api/v1/audit/activity/{delete_entry['seq']}/restore",
        json={"reason": "deleted by mistake"},
        headers=superadmin_headers,
    )
    assert restored.status_code == 200, restored.text

    note = await client.get(f"/api/v1/sample/notes/{note_id}", headers=manager_headers)
    assert note.status_code == 200
    assert note.json()["content"] == "delete me"

    entries = await _note_activity(client, superadmin_headers, note_id)
    restore_entry = next(item for item in entries if item["seq"] == restored.json()["audit_seq"])
    assert restore_entry["action"] == "sample_note.restore"
    assert restore_entry["reverts_id"] == str(delete_entry["seq"])


async def test_non_revertible_entities_return_a_clear_conflict(app, client, superadmin_headers):
    async with app.state.db.session() as session:
        from core.audit.service import record

        row = await record(
            session,
            action="settings.update",
            module="core",
            entity_type="setting",
            entity_id="core.branding.theme",
            before={"value": "light"},
            after={"value": "dark"},
            actor=None,
        )
        await session.commit()
        seq = row.seq

    response = await client.post(
        f"/api/v1/audit/activity/{seq}/revert",
        json={"reason": "undo"},
        headers=superadmin_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
