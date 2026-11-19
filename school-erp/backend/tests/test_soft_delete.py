"""P1-02: soft-deleted rows are hidden by default, restorable and audited."""

from __future__ import annotations

import uuid

import pytest
from app.errors import NotFound
from core.audit.models import AuditLog
from core.db.filters import INCLUDE_DELETED
from core.db.soft_delete import get_including_deleted, get_live
from modules.sample.models import SampleNote
from sqlalchemy import select

NOTES = "/api/v1/sample/notes"


async def _create(client, headers, content: str) -> dict:
    response = await client.post(NOTES, json={"content": content}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_default_selects_hide_deleted_rows(client, app, superadmin_headers):
    marker = f"soft delete {uuid.uuid4().hex}"
    note = await _create(client, superadmin_headers, marker)

    deleted = await client.delete(f"{NOTES}/{note['id']}", headers=superadmin_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert deleted.json()["changed"] is True

    listing = await client.get(NOTES, params={"q": marker}, headers=superadmin_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 0

    detail = await client.get(f"{NOTES}/{note['id']}", headers=superadmin_headers)
    assert detail.status_code == 404

    async with app.state.db.session() as session:
        hidden = (await session.execute(select(SampleNote))).scalars().all()
        assert all(row.id != uuid.UUID(note["id"]) for row in hidden)

        visible = (
            (await session.execute(select(SampleNote).execution_options(**{INCLUDE_DELETED: True})))
            .scalars()
            .all()
        )
        assert any(row.id == uuid.UUID(note["id"]) for row in visible)

        with pytest.raises(NotFound):
            await get_live(session, SampleNote, uuid.UUID(note["id"]))

        restored = await get_including_deleted(session, SampleNote, uuid.UUID(note["id"]))
        assert restored is not None
        assert restored.deleted_at is not None


async def test_restore_brings_the_row_back_and_bumps_row_version(client, superadmin_headers):
    marker = f"restore me {uuid.uuid4().hex}"
    note = await _create(client, superadmin_headers, marker)
    assert note["row_version"] == 1

    deleted = await client.delete(f"{NOTES}/{note['id']}", headers=superadmin_headers)
    assert deleted.json()["row_version"] == 2

    restored = await client.post(f"{NOTES}/{note['id']}/restore", headers=superadmin_headers)
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert body["content"] == marker
    assert body["row_version"] == 3

    listing = await client.get(NOTES, params={"q": marker}, headers=superadmin_headers)
    assert listing.json()["total"] == 1

    again = await client.post(f"{NOTES}/{note['id']}/restore", headers=superadmin_headers)
    assert again.status_code == 200
    assert again.json()["row_version"] == 3


async def test_delete_accepts_if_match_and_rejects_a_stale_version(client, superadmin_headers):
    note = await _create(client, superadmin_headers, f"versioned delete {uuid.uuid4().hex}")

    stale = await client.delete(
        f"{NOTES}/{note['id']}",
        headers={**superadmin_headers, "If-Match": '"9"'},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CONFLICT"

    ok = await client.delete(
        f"{NOTES}/{note['id']}",
        headers={**superadmin_headers, "If-Match": '"1"'},
        params={"reason": "duplicate note"},
    )
    assert ok.status_code == 200
    assert ok.json()["row_version"] == 2

    twice = await client.delete(f"{NOTES}/{note['id']}", headers=superadmin_headers)
    assert twice.status_code == 404


async def test_delete_and_restore_write_separate_audit_entries(client, app, superadmin_headers):
    marker = f"audited soft delete {uuid.uuid4().hex}"
    note = await _create(client, superadmin_headers, marker)
    await client.delete(
        f"{NOTES}/{note['id']}",
        params={"reason": "test cleanup"},
        headers=superadmin_headers,
    )
    await client.post(
        f"{NOTES}/{note['id']}/restore",
        params={"reason": "mistake"},
        headers=superadmin_headers,
    )

    async with app.state.db.session() as session:
        entries = (
            (
                await session.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.entity_id == note["id"],
                        AuditLog.action.in_(["sample.notes.delete", "sample.notes.restore"]),
                    )
                    .order_by(AuditLog.seq)
                )
            )
            .scalars()
            .all()
        )
        assert [entry.action for entry in entries] == [
            "sample.notes.delete",
            "sample.notes.restore",
        ]
        deleted, restored = entries
        assert deleted.actor_type == "user"
        assert deleted.before["deleted_at"] is None
        assert deleted.after["deleted_at"] is not None
        assert deleted.reason == "test cleanup"
        assert restored.before["deleted_at"] is not None
        assert restored.after["deleted_at"] is None
        assert restored.reason == "mistake"
        assert restored.actor_id == deleted.actor_id


async def test_restore_unknown_id_is_404(client, superadmin_headers):
    response = await client.post(f"{NOTES}/{uuid.uuid4()}/restore", headers=superadmin_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
