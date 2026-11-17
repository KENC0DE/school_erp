"""P0-11: a worker task processes a job row."""

from __future__ import annotations

import asyncio

import pytest
from core.events.celery_app import celery_app, ship_audit_task, verify_audit_chain
from core.events.models import Job


@pytest.fixture
async def env_db(app, monkeypatch):
    url = app.state.settings.database_url
    monkeypatch.setenv("ERP_DATABASE_URL", url)
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield url
    celery_app.conf.task_always_eager = False


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
