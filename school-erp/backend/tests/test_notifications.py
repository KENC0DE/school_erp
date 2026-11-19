"""P1-23: notification templates, in-app centre, delivery logs and channels."""

from __future__ import annotations

import uuid

from core.auth.models import User
from core.events.models import Job
from core.notifications.service import deliver_notification
from sqlalchemy import select

from tests.conftest import create_user, login, unique_email


def headers_for(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {user.id}"}


async def _set_contact(app, user_id, *, locale: str = "en", phone: str | None = None):
    async with app.state.db.session() as session:
        row = await session.get(User, uuid.UUID(str(user_id)))
        assert row is not None
        row.locale = locale
        row.phone = phone
        await session.commit()


async def _activity(client, headers) -> list[str]:
    response = await client.get("/api/v1/audit/activity", headers=headers)
    assert response.status_code == 200, response.text
    return [item["action"] for item in response.json()["items"]]


async def test_default_templates_are_seeded_and_manageable(client, app, superadmin_headers, limited_headers):
    denied = await client.get("/api/v1/notifications/templates", headers=limited_headers)
    assert denied.status_code == 403

    listed = await client.get("/api/v1/notifications/templates", headers=superadmin_headers)
    assert listed.status_code == 200
    templates = {item["key"]: item for item in listed.json()["items"]}
    assert {"account.welcome", "academics.results_published", "finance.invoice_overdue"} <= set(templates)
    assert templates["account.welcome"]["is_system"] is True
    assert templates["account.welcome"]["default_channels"] == ["in_app", "email"]

    created = await client.post(
        "/api/v1/notifications/templates",
        headers=superadmin_headers,
        json={
            "key": "probe.alert",
            "name": "Probe alert",
            "description": "Used by the tests.",
            "category": "general",
            "title_key": "notifications.probe.title",
            "body_key": "notifications.probe.body",
            "default_channels": ["in_app", "push"],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["key"] == "probe.alert"
    assert body["is_system"] is False
    assert body["row_version"] == 1

    duplicate = await client.post(
        "/api/v1/notifications/templates",
        headers=superadmin_headers,
        json={
            "key": "probe.alert",
            "name": "Probe alert again",
            "title_key": "notifications.probe.title",
            "body_key": "notifications.probe.body",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "error.notification.duplicate_template"

    literal = await client.post(
        "/api/v1/notifications/templates",
        headers=superadmin_headers,
        json={
            "key": "probe.literal",
            "name": "Literal",
            "title_key": "Hello there",
            "body_key": "notifications.probe.body",
        },
    )
    assert literal.status_code == 422
    assert literal.json()["error"]["message_key"] == "error.notification.invalid_template"

    stale = await client.put(
        f"/api/v1/notifications/templates/{body['id']}",
        headers=superadmin_headers,
        json={"row_version": 9, "name": "Stale"},
    )
    assert stale.status_code == 409

    updated = await client.put(
        f"/api/v1/notifications/templates/{body['id']}",
        headers=superadmin_headers,
        json={"row_version": 1, "name": "Probe alert v2", "is_active": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Probe alert v2"
    assert updated.json()["is_active"] is False
    assert updated.json()["row_version"] == 2

    system_delete = await client.delete(
        f"/api/v1/notifications/templates/{templates['account.welcome']['id']}",
        headers=superadmin_headers,
    )
    assert system_delete.status_code == 422
    assert system_delete.json()["error"]["message_key"] == "error.notification.system_template"

    removed = await client.delete(f"/api/v1/notifications/templates/{body['id']}", headers=superadmin_headers)
    assert removed.status_code == 200
    assert removed.json()["deleted"] is True
    remaining = await client.get("/api/v1/notifications/templates", headers=superadmin_headers)
    keys = {item["key"] for item in remaining.json()["items"]}
    assert "probe.alert" not in keys

    actions = await _activity(client, superadmin_headers)
    assert "notification.template_create" in actions
    assert "notification.template_update" in actions
    assert "notification.template_delete" in actions


async def test_send_renders_in_recipient_locale_and_marks_read(
    client, app, superadmin_headers, limited_headers
):
    recipient = await create_user(app, unique_email("notify"), display_name="Hanna", roles=["limited"])
    await _set_contact(app, recipient.id, locale="am", phone="+251911123456")
    recipient_headers = await login(client, recipient.email)
    stranger = await create_user(app, unique_email("stranger"), roles=["limited"])
    stranger_headers = await login(client, stranger.email)
    await _set_contact(app, stranger.id, locale="en")

    sent = await client.post(
        "/api/v1/notifications/send",
        headers=superadmin_headers,
        json={
            "user_ids": [str(recipient.id)],
            "template_key": "account.welcome",
            "params": {"school": "Alpha Academy", "name": "Hanna"},
            "link": "/dashboard",
        },
    )
    assert sent.status_code == 200, sent.text
    payload = sent.json()
    assert payload["count"] == 1
    notification = payload["items"][0]
    assert notification["title"] == "ወደ Alpha Academy እንኳን ደህና መጡ"
    assert "Hanna" in notification["body"]
    assert notification["read"] is False
    assert notification["job_id"]

    inbox = await client.get("/api/v1/notifications", headers=recipient_headers)
    assert inbox.status_code == 200
    assert inbox.json()["unread"] == 1
    assert inbox.json()["items"][0]["id"] == notification["id"]
    count = await client.get("/api/v1/notifications/unread-count", headers=recipient_headers)
    assert count.json() == {"unread": 1}

    unread_only = await client.get(
        "/api/v1/notifications", params={"unread_only": "true"}, headers=recipient_headers
    )
    assert len(unread_only.json()["items"]) == 1

    hidden = await client.get(f"/api/v1/notifications/{notification['id']}/read", headers=stranger_headers)
    assert hidden.status_code == 405
    other_read = await client.post(
        f"/api/v1/notifications/{notification['id']}/read", headers=stranger_headers
    )
    assert other_read.status_code == 404
    assert other_read.json()["error"]["message_key"] == "error.notification.not_found"

    read = await client.post(f"/api/v1/notifications/{notification['id']}/read", headers=recipient_headers)
    assert read.status_code == 200
    assert read.json()["read"] is True
    assert (await client.get("/api/v1/notifications/unread-count", headers=recipient_headers)).json() == {
        "unread": 0
    }

    again = await client.post(
        "/api/v1/notifications/send",
        headers=superadmin_headers,
        json={"user_ids": [str(recipient.id)], "template_key": "account.welcome"},
    )
    assert again.status_code == 200
    bulk = await client.post("/api/v1/notifications/read-all", headers=recipient_headers)
    assert bulk.status_code == 200
    assert bulk.json()["updated"] == 1

    actions = await _activity(client, superadmin_headers)
    assert "notification.send" in actions
    assert "notification.read" in actions
    assert "notification.read_all" in actions


async def test_delivery_logs_cover_sent_skipped_and_failed_channels(client, app, superadmin_headers):
    full = await create_user(app, unique_email("full"), roles=["limited"])
    await _set_contact(app, full.id, phone="+251911000111")
    no_phone = await create_user(app, unique_email("nophone"), roles=["limited"])
    await _set_contact(app, no_phone.id, phone=None)

    sent = await client.post(
        "/api/v1/notifications/send",
        headers=superadmin_headers,
        json={
            "user_ids": [str(full.id), str(no_phone.id)],
            "template_key": "finance.invoice_overdue",
            "params": {"invoice": "INV-7", "student": "Bereket"},
            "channels": ["in_app", "email", "sms", "push"],
            "link": "/fees/invoices/7",
        },
    )
    assert sent.status_code == 200, sent.text
    full_notification = sent.json()["items"][0]
    no_phone_notification = sent.json()["items"][1]

    async with app.state.db.session() as session:
        jobs = (
            (await session.execute(select(Job).where(Job.kind == "notifications.delivery"))).scalars().all()
        )
    assert {job.payload["notification_id"] for job in jobs} == {
        full_notification["id"],
        no_phone_notification["id"],
    }

    async with app.state.db.session() as session:
        result = await deliver_notification(
            session,
            full_notification["id"],
            mailer=app.state.mailer,
            sms=app.state.sms,
            push=app.state.push,
        )
    assert result["channels"] == {"email": "sent", "sms": "sent", "push": "sent"}
    assert app.state.mailer.outbox[-1].to == full.email
    assert app.state.mailer.outbox[-1].subject == "Invoice overdue"
    assert "INV-7" in app.state.mailer.outbox[-1].body
    assert app.state.sms.outbox[-1].to == "+251911000111"
    assert "Bereket" in app.state.sms.outbox[-1].body
    push = app.state.push.outbox[-1]
    assert push.title == "Invoice overdue"
    assert push.body == ""
    assert push.data["link"] == "/fees/invoices/7"
    assert push.data["notification_id"] == full_notification["id"]

    logs = await client.get(
        "/api/v1/notifications/deliveries",
        params={"notification_id": full_notification["id"]},
        headers=superadmin_headers,
    )
    assert logs.status_code == 200
    by_channel = {row["channel"]: row for row in logs.json()["items"]}
    assert by_channel["email"]["status"] == "sent"
    assert by_channel["email"]["recipient"] == "f***@demo.school"
    assert by_channel["sms"]["recipient"] == "***0111"
    assert by_channel["push"]["recipient"].startswith("***")
    assert by_channel["in_app"]["status"] == "sent"

    skipped = await client.get(
        "/api/v1/notifications/deliveries",
        params={"notification_id": no_phone_notification["id"]},
        headers=superadmin_headers,
    )
    no_phone_logs = {row["channel"]: row for row in skipped.json()["items"]}
    assert no_phone_logs["sms"]["status"] == "skipped"
    assert no_phone_logs["sms"]["error"] == "No phone number on file"

    class FailingEmail:
        async def send(self, *, to: str, subject: str, body: str) -> None:
            raise RuntimeError("smtp is down")

    failed_notification = (
        await client.post(
            "/api/v1/notifications/send",
            headers=superadmin_headers,
            json={
                "user_ids": [str(full.id)],
                "template_key": "account.welcome",
                "channels": ["in_app", "email"],
            },
        )
    ).json()["items"][0]
    async with app.state.db.session() as session:
        failed = await deliver_notification(
            session,
            failed_notification["id"],
            mailer=FailingEmail(),
        )
    assert failed["channels"]["email"] == "failed"
    failed_logs = await client.get(
        "/api/v1/notifications/deliveries",
        params={"notification_id": failed_notification["id"]},
        headers=superadmin_headers,
    )
    failed_rows = {row["channel"]: row for row in failed_logs.json()["items"]}
    assert failed_rows["email"]["status"] == "failed"
    assert "smtp is down" in failed_rows["email"]["error"]
    assert failed_rows["email"]["attempts"] == 1


async def test_notification_centre_requires_a_session_and_admin_routes_require_permission(
    client, limited_headers
):
    assert (await client.get("/api/v1/notifications")).status_code == 401
    assert (await client.get("/api/v1/notifications/unread-count")).status_code == 401

    denied = await client.post(
        "/api/v1/notifications/send",
        headers=limited_headers,
        json={"user_ids": ["00000000-0000-0000-0000-000000000001"], "template_key": "account.welcome"},
    )
    assert denied.status_code == 403
    assert (await client.get("/api/v1/notifications/deliveries", headers=limited_headers)).status_code == 403


async def test_inactive_templates_and_unknown_recipients_are_rejected(client, app, superadmin_headers):
    created = await client.post(
        "/api/v1/notifications/templates",
        headers=superadmin_headers,
        json={
            "key": "probe.inactive",
            "name": "Inactive",
            "title_key": "notifications.probe.title",
            "body_key": "notifications.probe.body",
            "default_channels": ["in_app"],
        },
    )
    assert created.status_code == 201
    template = created.json()
    await client.put(
        f"/api/v1/notifications/templates/{template['id']}",
        headers=superadmin_headers,
        json={"row_version": 1, "is_active": False},
    )

    inactive = await client.post(
        "/api/v1/notifications/send",
        headers=superadmin_headers,
        json={
            "user_ids": [str(uuid.uuid4())],
            "template_key": "probe.inactive",
        },
    )
    assert inactive.status_code == 422
    assert inactive.json()["error"]["message_key"] == "error.notification.inactive_template"

    unknown = await client.post(
        "/api/v1/notifications/send",
        headers=superadmin_headers,
        json={"user_ids": [str(uuid.uuid4())], "template_key": "account.welcome"},
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["message_key"] == "error.user.not_found"
