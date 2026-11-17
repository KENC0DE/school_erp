"""P1-10: activity history filtering, scope and tier visibility."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.audit.models import AuditLog
from core.audit.service import record
from sqlalchemy import select
from tests.conftest import create_role, create_user, login, unique_email


async def test_activity_endpoints_require_the_permission(client, limited_headers):
    for path in (
        "/api/v1/audit/activity",
        "/api/v1/audit/activity/options",
        "/api/v1/audit/activity/1",
    ):
        response = await client.get(path, headers=limited_headers)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_tier_b_actions_are_never_returned(app, client, manager_headers, auditor_headers):
    async with app.state.db.session() as session:
        tier_b = await record(
            session,
            action="auth.password_reset",
            module="core",
            entity_type="user",
            entity_id="user-1",
        )
        business = await record(
            session,
            action="auth.user.invited",
            module="core",
            entity_type="user",
            entity_id="user-2",
            after={"email": "new@demo.school"},
        )
        await session.commit()
        tier_b_seq = tier_b.seq
        business_seq = business.seq

    created = await client.post(
        "/api/v1/sample/notes", json={"content": "visible business action"}, headers=manager_headers
    )
    assert created.status_code == 200

    activity = await client.get("/api/v1/audit/activity", headers=auditor_headers)
    assert activity.status_code == 200, activity.text
    items = activity.json()["items"]
    actions = {item["action"] for item in items}
    assert "auth.password_reset" not in actions
    assert "auth.user.invited" in actions
    assert "sample.notes.create" in actions
    assert all(
        not ({"ip", "user_agent", "request_id", "prev_hash", "hash"} & set(item))
        for item in items
    )
    assert next(item for item in items if item["seq"] == business_seq)["after"] == {
        "email": "new@demo.school"
    }

    hidden = await client.get(f"/api/v1/audit/activity/{tier_b_seq}", headers=auditor_headers)
    assert hidden.status_code == 404

    options = await client.get("/api/v1/audit/activity/options", headers=auditor_headers)
    assert options.status_code == 200
    assert "auth.password_reset" not in options.json()["actions"]
    assert "sample.notes.create" in options.json()["actions"]


async def test_module_scope_limits_list_options_and_detail(app, client, manager_headers):
    role = await create_role(app, "sample_auditor", [("audit.activity.view", "sample")])
    email = unique_email("scope")
    await create_user(app, email, roles=[role.key])
    scoped_headers = await login(client, email)

    created = await client.post(
        "/api/v1/sample/notes", json={"content": "scoped note"}, headers=manager_headers
    )
    assert created.status_code == 200
    note_id = created.json()["id"]

    async with app.state.db.session() as session:
        core_entry = await record(
            session,
            action="settings.update",
            module="core",
            entity_type="setting",
            entity_id="core.branding.theme",
            after={"value": "dark"},
        )
        await session.commit()
        core_seq = core_entry.seq
        note_seq = (
            await session.execute(
                select(AuditLog.seq)
                .where(AuditLog.entity_id == note_id, AuditLog.action == "sample.notes.create")
                .order_by(AuditLog.seq.desc())
                .limit(1)
            )
        ).scalar_one()

    activity = await client.get("/api/v1/audit/activity", headers=scoped_headers)
    assert activity.status_code == 200, activity.text
    items = activity.json()["items"]
    assert items
    assert {item["module"] for item in items} == {"sample"}
    assert all(item["entity_id"] != str(core_seq) for item in items)

    options = await client.get("/api/v1/audit/activity/options", headers=scoped_headers)
    assert options.status_code == 200
    assert options.json()["modules"] == ["sample"]

    out_of_scope = await client.get(
        "/api/v1/audit/activity", params={"module": "core"}, headers=scoped_headers
    )
    assert out_of_scope.status_code == 403
    assert out_of_scope.json()["error"]["code"] == "PERMISSION_DENIED"

    hidden = await client.get(f"/api/v1/audit/activity/{core_seq}", headers=scoped_headers)
    assert hidden.status_code == 404

    own = await client.get(f"/api/v1/audit/activity/{note_seq}", headers=scoped_headers)
    assert own.status_code == 200
    assert own.json()["module"] == "sample"


async def test_super_admin_actions_are_hidden_without_the_extra_permission(
    app, client, superadmin_headers, manager_headers, auditor_headers
):
    super_me = await client.get("/api/v1/auth/me", headers=superadmin_headers)
    super_id = super_me.json()["id"]
    await client.post(
        "/api/v1/sample/notes", json={"content": "by the super admin"}, headers=superadmin_headers
    )
    await client.post(
        "/api/v1/sample/notes", json={"content": "by the manager"}, headers=manager_headers
    )

    activity = await client.get("/api/v1/audit/activity", headers=auditor_headers)
    items = activity.json()["items"]
    assert items
    assert all(item["actor_id"] != super_id for item in items)
    assert any(item["action"] == "sample.notes.create" for item in items)

    async with app.state.db.session() as session:
        super_seq = (
            await session.execute(
                select(AuditLog.seq)
                .where(AuditLog.actor_id == super_id, AuditLog.action == "sample.notes.create")
                .order_by(AuditLog.seq.desc())
                .limit(1)
            )
        ).scalar_one()
    hidden = await client.get(f"/api/v1/audit/activity/{super_seq}", headers=auditor_headers)
    assert hidden.status_code == 404

    role = await create_role(
        app,
        "admin_auditor",
        [
            ("audit.activity.view", "all"),
            ("audit.activity.view_admin_actions", "all"),
        ],
    )
    email = unique_email("adminaudit")
    await create_user(app, email, roles=[role.key])
    privileged = await login(client, email)

    allowed = await client.get("/api/v1/audit/activity", headers=privileged)
    assert any(item["actor_id"] == super_id for item in allowed.json()["items"])
    detail = await client.get(f"/api/v1/audit/activity/{super_seq}", headers=privileged)
    assert detail.status_code == 200
    assert detail.json()["actor_id"] == super_id


async def test_navigation_links_activity_only_for_viewers(client, limited_headers, auditor_headers):
    denied = await client.get("/api/v1/auth/me/navigation", headers=limited_headers)
    assert "/activity" not in [item["path"] for item in denied.json()["items"]]

    allowed = await client.get("/api/v1/auth/me/navigation", headers=auditor_headers)
    item = next(item for item in allowed.json()["items"] if item["key"] == "activity")
    assert item["path"] == "/activity"
    assert item["label_key"] == "nav.activity"


async def test_filters_by_actor_module_entity_action_and_date(
    app, client, manager_headers, auditor_headers
):
    me = await client.get("/api/v1/auth/me", headers=manager_headers)
    manager_id = me.json()["id"]

    first = await client.post(
        "/api/v1/sample/notes", json={"content": "filter one"}, headers=manager_headers
    )
    second = await client.post(
        "/api/v1/sample/notes", json={"content": "filter two"}, headers=manager_headers
    )
    assert first.status_code == 200 and second.status_code == 200
    first_id = first.json()["id"]

    base = {"actor_id": manager_id, "action": "sample.notes.create", "module": "sample"}
    by_entity = await client.get(
        "/api/v1/audit/activity",
        params={**base, "entity_type": "sample_note", "entity_id": first_id},
        headers=auditor_headers,
    )
    assert by_entity.status_code == 200
    assert [item["entity_id"] for item in by_entity.json()["items"]] == [first_id]

    now = datetime.now(UTC)
    by_date = await client.get(
        "/api/v1/audit/activity",
        params={
            **base,
            "date_from": (now - timedelta(minutes=5)).isoformat(),
            "date_to": (now + timedelta(minutes=5)).isoformat(),
            "limit": 1,
        },
        headers=auditor_headers,
    )
    assert by_date.status_code == 200
    assert len(by_date.json()["items"]) == 1
    assert by_date.json()["items"][0]["actor_id"] == manager_id
    assert by_date.json()["items"][0]["module"] == "sample"

    actor_options = await client.get("/api/v1/audit/activity/options", headers=auditor_headers)
    actors = actor_options.json()["actors"]
    assert any(actor["id"] == manager_id for actor in actors)
