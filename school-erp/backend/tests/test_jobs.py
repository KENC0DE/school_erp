"""P0-11 and P1-25: worker jobs, the jobs API, user-safe errors and retry."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from core.auth.models import User
from core.events.celery_app import celery_app, ship_audit_task, verify_audit_chain
from core.events.models import Job
from core.notifications.models import DeliveryLog, Notification
from sqlalchemy import select


@pytest.fixture
async def env_db(app, monkeypatch):
    url = app.state.settings.database_url
    monkeypatch.setenv("ERP_DATABASE_URL", url)
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield url
    celery_app.conf.task_always_eager = False


async def _create_job(app, kind: str, status: str, **values) -> str:
    async with app.state.db.session() as session:
        job = Job(kind=kind, status=status, payload=values.pop("payload", {}), **values)
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return str(job.id)


async def _job(app, job_id: str) -> Job:
    async with app.state.db.session() as session:
        row = await session.get(Job, uuid.UUID(job_id))
        assert row is not None
        return row


async def _actions(client, headers) -> list[str]:
    response = await client.get("/api/v1/audit/activity", headers=headers)
    assert response.status_code == 200, response.text
    return [item["action"] for item in response.json()["items"]]


async def test_ping_job_completes(app, client, auditor_headers, env_db):
    response = await client.post("/api/v1/jobs/ping", headers=auditor_headers)
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]

    async with app.state.db.session() as session:
        job = await session.get(Job, __import__("uuid").UUID(job_id))
        assert job is not None
        assert job.status == "succeeded"
        assert job.result == {"pong": True}
        assert job.progress == 100


async def test_jobs_require_permission(client, limited_headers):
    response = await client.get("/api/v1/jobs", headers=limited_headers)
    assert response.status_code == 403


async def test_job_list_exposes_only_user_safe_errors(app, client, superadmin_headers):
    failed = await _create_job(
        app,
        "files.thumbnail",
        "failed",
        progress=40,
        error="Traceback: /srv/erp/secret/path.py line 42, provider key=abc",
    )
    await _create_job(app, "ping", "succeeded", progress=100)
    running = await _create_job(app, "files.thumbnail", "running", progress=30)

    response = await client.get("/api/v1/jobs", headers=superadmin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    items = {item["id"]: item for item in body["items"]}

    assert "error" not in items[failed]
    assert items[failed]["error_key"] == "jobs.error.thumbnail"
    assert items[failed]["retryable"] is True
    assert items[failed]["progress"] == 40
    assert items[failed]["created_at"]
    assert items[running]["error_key"] is None
    assert items[running]["retryable"] is False

    # The raw failure never travels to the client, not even inside a nested key.
    assert "/srv/erp/secret/path.py" not in response.text

    assert items[failed]["status"] == "failed"
    assert len(body["items"]) == 3


async def test_job_list_filters_by_status_and_kind(app, client, superadmin_headers):
    failed_ping = await _create_job(app, "ping", "failed", error="boom")
    await _create_job(app, "ping", "succeeded", progress=100)
    failed_delivery = await _create_job(
        app, "notifications.delivery", "failed", payload={"notification_id": "x"}
    )

    failed = await client.get("/api/v1/jobs", params={"status": "failed"}, headers=superadmin_headers)
    assert failed.status_code == 200, failed.text
    assert {item["id"] for item in failed.json()["items"]} == {failed_ping, failed_delivery}

    deliveries = await client.get(
        "/api/v1/jobs",
        params={"kind": "notifications.delivery"},
        headers=superadmin_headers,
    )
    assert deliveries.status_code == 200, deliveries.text
    assert [item["id"] for item in deliveries.json()["items"]] == [failed_delivery]

    page = await client.get(
        "/api/v1/jobs",
        params={"limit": 1, "offset": 0},
        headers=superadmin_headers,
    )
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1

    invalid = await client.get("/api/v1/jobs", params={"status": "exploded"}, headers=superadmin_headers)
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_FILTER"
    assert invalid.json()["error"]["details"]["allowed"] == [
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
    ]


async def test_retry_requires_jobs_manage(app, client, auditor_headers):
    job_id = await _create_job(app, "ping", "failed", error="boom")

    # The auditor can see the queue but must not be able to rerun work.
    assert (await client.get("/api/v1/jobs", headers=auditor_headers)).status_code == 200
    denied = await client.post(f"/api/v1/jobs/{job_id}/retry", headers=auditor_headers)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

    assert (await _job(app, job_id)).status == "failed"


async def test_retry_requeues_a_failed_job_and_audits_it(app, client, superadmin_headers):
    job_id = await _create_job(
        app,
        "ping",
        "failed",
        progress=55,
        error="internal failure",
        result={"partial": True},
    )

    response = await client.post(f"/api/v1/jobs/{job_id}/retry", headers=superadmin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["progress"] == 0
    assert body["error_key"] is None
    assert body["retryable"] is False

    row = await _job(app, job_id)
    assert row.status == "queued"
    assert row.progress == 0
    assert row.error is None
    assert row.result is None
    assert row.started_at is None
    assert row.finished_at is None

    assert "job.retry" in await _actions(client, superadmin_headers)


async def test_retry_rejects_finished_unknown_and_missing_jobs(app, client, superadmin_headers):
    queued = await _create_job(app, "ping", "queued")
    conflict = await client.post(f"/api/v1/jobs/{queued}/retry", headers=superadmin_headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "JOB_NOT_FAILED"

    unknown = await _create_job(app, "backup.nightly", "failed", error="nope")
    refused = await client.post(f"/api/v1/jobs/{unknown}/retry", headers=superadmin_headers)
    assert refused.status_code == 422
    assert refused.json()["error"]["message_key"] == "error.job_not_retryable"

    missing = await client.post(f"/api/v1/jobs/{uuid.uuid4()}/retry", headers=superadmin_headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["message_key"] == "error.job_not_found"

    malformed = await client.post("/api/v1/jobs/not-a-uuid/retry", headers=superadmin_headers)
    assert malformed.status_code == 404


async def test_retry_notification_delivery_requeues_failed_channels(app, client, superadmin_headers):
    async with app.state.db.session() as session:
        user = (
            await session.execute(select(User).where(User.email == "superadmin@demo.school"))
        ).scalar_one()
        notification = Notification(
            user_id=user.id,
            template_key="account.welcome",
            category="system",
            title="Welcome",
            body="Hello",
            params={},
            channels=["email", "sms"],
        )
        session.add(notification)
        await session.flush()
        failed = DeliveryLog(
            notification_id=notification.id,
            user_id=user.id,
            template_key="account.welcome",
            channel="email",
            recipient="superadmin@demo.school",
            status="failed",
            attempts=2,
            error="provider down",
        )
        skipped = DeliveryLog(
            notification_id=notification.id,
            user_id=user.id,
            template_key="account.welcome",
            channel="sms",
            recipient=None,
            status="skipped",
            attempts=0,
            error="No phone number on file",
        )
        job = Job(
            kind="notifications.delivery",
            status="failed",
            payload={"notification_id": str(notification.id)},
            error="provider down",
        )
        session.add_all([failed, skipped, job])
        await session.commit()
        notification_id, job_id, failed_id, skipped_id = (
            notification.id,
            str(job.id),
            failed.id,
            skipped.id,
        )

    response = await client.post(f"/api/v1/jobs/{job_id}/retry", headers=superadmin_headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "queued"

    async with app.state.db.session() as session:
        email_log = await session.get(DeliveryLog, failed_id)
        sms_log = await session.get(DeliveryLog, skipped_id)
        assert email_log is not None and sms_log is not None
        assert email_log.status == "queued"
        assert email_log.error is None
        assert email_log.attempts == 2  # history is preserved
        # Skipped channels were skipped for a reason and stay untouched.
        assert sms_log.status == "skipped"
        assert sms_log.error == "No phone number on file"

        stored = await session.get(Job, uuid.UUID(job_id))
        assert stored is not None
        assert stored.payload == {"notification_id": str(notification_id)}


async def test_retry_with_a_missing_payload_is_refused_without_changing_the_job(
    app, client, superadmin_headers
):
    job_id = await _create_job(app, "files.thumbnail", "failed", payload={}, error="boom")

    response = await client.post(f"/api/v1/jobs/{job_id}/retry", headers=superadmin_headers)
    assert response.status_code == 422
    assert response.json()["error"]["message_key"] == "error.job_invalid_payload"

    row = await _job(app, job_id)
    assert row.status == "failed"
    assert row.error == "boom"


def test_audit_tasks_are_registered_and_scheduled():
    schedule = celery_app.conf.beat_schedule
    assert schedule["ship-audit"]["task"] == "erp.ship_audit"
    assert schedule["verify-audit-chain"]["task"] == "erp.verify_audit_chain"
    assert "erp.ship_audit" in celery_app.tasks
    assert "erp.verify_audit_chain" in celery_app.tasks


async def test_audit_verify_task_checks_the_chain(app, client, manager_headers, env_db):
    created = await client.post(
        "/api/v1/sample/notes", json={"content": "verification target"}, headers=manager_headers
    )
    assert created.status_code == 200
    result = await asyncio.to_thread(verify_audit_chain)
    assert result["ok"] is True
    assert result["entries"] >= 1


async def test_ship_audit_task_is_safe_without_an_enrolled_instance(app, env_db):
    result = await asyncio.to_thread(ship_audit_task)
    assert result == {"ok": True, "shipped": 0}
