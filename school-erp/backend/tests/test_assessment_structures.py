"""P4-05: mark structure management, impact preview and recalculation.

Changing a component maximum is the moment a converted mark can drift from the
structure that produced it. These tests prove the raw score never changes, the
impact preview predicts the change, and the background job applies it.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date
from decimal import Decimal

from core.audit.models import AuditLog
from core.events.celery_app import assessment_recalculate_task, celery_app
from core.events.models import Job
from modules.academics.models import Term
from modules.assessment.models import Assessment, Score
from sqlalchemy import select

from tests.conftest import create_role, create_user, login, unique_email

BASE = "/api/v1/assessment"
MODULES = "/api/v1/system/modules"
ACADEMICS = "/api/v1/academics"
STUDENTS = "/api/v1/students"


async def _enable(client, headers) -> None:
    response = await client.put(f"{MODULES}/assessment", headers=headers, json={"enabled": True})
    assert response.status_code == 200, response.text


async def _year(client, headers, code: str = "2026-2027") -> dict:
    response = await client.post(
        f"{ACADEMICS}/academic-years",
        headers=headers,
        json={
            "code": code,
            "name": code.replace("-", "/"),
            "start_date": "2026-09-11",
            "end_date": "2027-06-30",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _level(client, headers, code: str = "g5") -> dict:
    response = await client.get(f"{ACADEMICS}/levels", headers=headers, params={"scope": "all"})
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["code"] == code)


async def _section(client, headers, year: dict, level: dict, code: str = "A") -> dict:
    response = await client.post(
        f"{ACADEMICS}/sections",
        headers=headers,
        json={"year_id": year["id"], "level_id": level["id"], "code": code},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _subject(client, headers, code: str = "math-marks") -> dict:
    response = await client.post(
        f"{ACADEMICS}/subjects",
        headers=headers,
        json={"code": code, "name": "Mathematics"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _student(client, headers, *, number: str, year: dict, level: dict, section: dict) -> dict:
    response = await client.post(
        STUDENTS,
        headers=headers,
        json={
            "person": {
                "given_name_en": "Selam",
                "father_name_en": "Bekele",
                "grandfather_name_en": "Desta",
                "given_name_am": "ሰላም",
                "father_name_am": "በቀለ",
                "grandfather_name_am": "ደስታ",
                "sex": "female",
                "date_of_birth": "2015-01-10",
            },
            "student_number": number,
            "enrollment": {
                "year_id": year["id"],
                "level_id": level["id"],
                "section_id": section["id"],
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _component(key: str = "quiz", max_points: str = "10", **overrides) -> dict:
    payload = {
        "key": key,
        "name": key.title(),
        "name_am": "ኩዊዝ",
        "max_points": max_points,
    }
    payload.update(overrides)
    return payload


async def _structure(
    client,
    headers,
    year: dict,
    *,
    components: list[dict] | None = None,
    **overrides,
) -> dict:
    payload = {
        "year_id": year["id"],
        "scope_type": "school",
        "name": "Lower primary",
        "intended_total": "100",
        "components": components or [_component()],
        **overrides,
    }
    response = await client.post(f"{BASE}/structures", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _assessment_state(app, client, headers):
    """Create one assessment with two scores, as P4-06 will once it exists."""
    year = await _year(client, headers, code="2026-2027")
    level = await _level(client, headers)
    section = await _section(client, headers, year, level)
    subject = await _subject(client, headers)
    students = [
        await _student(client, headers, number=f"STU-{index}", year=year, level=level, section=section)
        for index in (1, 2)
    ]
    structure = await _structure(
        client,
        headers,
        year,
        components=[
            _component("quiz", "10"),
            _component("final", "50", sort_order=1),
        ],
        intended_total="100",
    )
    async with app.state.db.session() as session:
        term = (
            (await session.execute(select(Term).where(Term.year_id == uuid.UUID(year["id"]))))
            .scalars()
            .first()
        )
        assert term is not None
        component_id = uuid.UUID(structure["components"][0]["id"])
        assessment = Assessment(
            year_id=uuid.UUID(year["id"]),
            term_id=term.id,
            section_id=uuid.UUID(section["id"]),
            subject_id=uuid.UUID(subject["id"]),
            structure_id=uuid.UUID(structure["id"]),
            component_id=component_id,
            title="Quiz 1",
            assessment_date=date(2026, 10, 1),
            out_of=Decimal("10"),
        )
        session.add(assessment)
        await session.flush()
        scores = [
            Score(
                assessment_id=assessment.id,
                student_id=uuid.UUID(students[0]["id"]),
                raw_score=Decimal("5"),
                out_of=Decimal("10"),
                status="present",
                converted=Decimal("5.000000"),
            ),
            Score(
                assessment_id=assessment.id,
                student_id=uuid.UUID(students[1]["id"]),
                raw_score=None,
                out_of=Decimal("10"),
                status="absent",
                converted=None,
            ),
        ]
        session.add_all(scores)
        await session.commit()
        return structure, assessment.id, [score.id for score in scores]


async def _structure_state(app, structure_id: str):
    async with app.state.db.session() as session:
        from modules.assessment.models import AssessmentStructure

        row = await session.get(AssessmentStructure, uuid.UUID(structure_id))
        assert row is not None
        return row.row_version


async def test_create_list_and_scope_validation(client, app, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)

    structure = await _structure(
        client,
        superadmin_headers,
        year,
        components=[_component("quiz"), _component("mid", "20", sort_order=1)],
    )
    assert structure["total"] == "30"
    assert structure["total_matches"] is False
    assert structure["term_system"] == year["term_system"]
    assert structure["version"] == 1
    assert len(structure["components"]) == 2

    listing = await client.get(
        f"{BASE}/structures", headers=superadmin_headers, params={"year_id": year["id"]}
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1

    duplicate = await client.post(
        f"{BASE}/structures",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "scope_type": "school",
            "name": "Another",
            "components": [_component()],
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"
    assert duplicate.json()["error"]["message_key"] == "assessment.error.duplicate_structure"

    scoped = await client.post(
        f"{BASE}/structures",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "scope_type": "level",
            "level_id": level["id"],
            "name": "Grade 5",
            "components": [_component()],
        },
    )
    assert scoped.status_code == 201, scoped.text
    assert scoped.json()["scope_key"] == f"level:{level['id']}"
    assert scoped.json()["level_name"] == level["name"]

    missing_target = await client.post(
        f"{BASE}/structures",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "scope_type": "level",
            "name": "No target",
            "components": [_component()],
        },
    )
    assert missing_target.status_code == 422

    g6 = await _level(client, superadmin_headers, "g6")
    over_total = await client.post(
        f"{BASE}/structures",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "scope_type": "level",
            "level_id": g6["id"],
            "name": "Too big",
            "intended_total": "10",
            "components": [_component("quiz", "20")],
        },
    )
    assert over_total.status_code == 422, over_total.text
    assert over_total.json()["error"]["message_key"] == "assessment.error.component_sum"

    role = await create_role(
        app,
        "assessment_reader",
        [("assessment.view", "all")],
    )
    assert role is not None
    email = unique_email("marksviewer")
    await create_user(app, email, roles=["assessment_reader"])
    headers = await login(client, email)
    allowed = await client.get(f"{BASE}/structures", headers=headers)
    assert allowed.status_code == 200
    denied = await client.post(
        f"{BASE}/structures",
        headers=headers,
        json={"year_id": year["id"], "scope_type": "school", "name": "Nope", "components": [_component()]},
    )
    assert denied.status_code == 403


async def test_impact_preview_and_recalculation_rewrite_only_converted_values(
    client, app, superadmin_headers, seeded, monkeypatch
) -> None:
    await _enable(client, superadmin_headers)
    structure, assessment_id, score_ids = await _assessment_state(app, client, superadmin_headers)
    version = await _structure_state(app, structure["id"])

    preview = await client.post(
        f"{BASE}/structures/{structure['id']}/impact",
        headers=superadmin_headers,
        json={
            "components": [
                {**_component("quiz", "20"), "id": structure["components"][0]["id"]},
                {**_component("final", "50"), "id": structure["components"][1]["id"]},
            ]
        },
    )
    assert preview.status_code == 200, preview.text
    impact = preview.json()
    assert impact["assessments"] == 1
    assert impact["scores"] == 2
    assert impact["changed"] == 1
    assert impact["recalculation_required"] is True
    assert impact["total_before"] == "60"
    assert impact["total_after"] == "70"
    sample = impact["samples"][0]
    assert sample["raw"] == "5"
    assert sample["before"] == "5"
    assert sample["after"] == "10"

    components = [
        {**_component("quiz", "20"), "id": structure["components"][0]["id"]},
        {**_component("final", "50"), "id": structure["components"][1]["id"]},
    ]
    update = await client.patch(
        f"{BASE}/structures/{structure['id']}",
        headers=superadmin_headers,
        json={
            "row_version": version,
            "components": components,
            "reason": "Quizzes are worth 20 this year",
        },
    )
    assert update.status_code == 200, update.text
    body = update.json()
    assert body["structure"]["total"] == "70"
    assert body["structure"]["version"] == 2
    assert body["recalculation_job_id"] is not None
    assert body["changed_scores"] == 1

    async with app.state.db.session() as session:
        score = await session.get(Score, score_ids[0])
        assert score is not None
        assert score.raw_score == Decimal("5.000000")
        assert score.converted == Decimal("5.000000")
        job = await session.get(Job, uuid.UUID(body["recalculation_job_id"]))
        assert job is not None
        assert job.kind == "assessment.recalculate"
        assert job.payload == {"structure_id": structure["id"]}
        assert job.status == "queued"

    monkeypatch.setenv("ERP_DATABASE_URL", app.state.settings.database_url)
    celery_app.conf.task_always_eager = True
    try:
        # Eager Celery still runs synchronously; hand it a thread without a
        # running event loop, exactly as the API process does in production.
        result = await asyncio.to_thread(
            assessment_recalculate_task.delay,
            body["recalculation_job_id"],
            structure["id"],
        )
    finally:
        celery_app.conf.task_always_eager = False
    assert result.get()["ok"] is True

    async with app.state.db.session() as session:
        score = await session.get(Score, score_ids[0])
        assert score is not None
        assert score.raw_score == Decimal("5.000000")
        assert score.converted == Decimal("10.000000")
        absent = await session.get(Score, score_ids[1])
        assert absent is not None
        assert absent.raw_score is None
        assert absent.converted is None
        job = await session.get(Job, uuid.UUID(body["recalculation_job_id"]))
        assert job is not None
        assert job.status == "succeeded"
        assert job.result == {
            "structure_id": structure["id"],
            "assessments": 1,
            "scores": 2,
            "changed": 1,
            "job_id": None,
        }
        assessment = await session.get(Assessment, assessment_id)
        assert assessment is not None
        assert assessment.out_of == Decimal("10.000000")
        actions = set(
            (await session.execute(select(AuditLog.action).where(AuditLog.entity_id == structure["id"])))
            .scalars()
            .all()
        )
        assert {"assessment.structure.create", "assessment.structure.update"} <= actions
        assert "assessment.structure.recalculate" in actions

    # The checkpoint property: recalculating again is a no-op. Raw marks and
    # converted values are stable, so a retried job cannot drift a report.
    from modules.assessment.service import recalculate_structure

    async with app.state.db.session() as session:
        again = await recalculate_structure(session, uuid.UUID(structure["id"]))
    assert again.changed == 0
    assert again.scores == 2
    async with app.state.db.session() as session:
        score = await session.get(Score, score_ids[0])
        assert score is not None
        assert score.converted == Decimal("10.000000")


async def test_component_in_use_and_stale_version_are_rejected(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    structure, _assessment_id, _score_ids = await _assessment_state(app, client, superadmin_headers)
    version = await _structure_state(app, structure["id"])

    removal = await client.patch(
        f"{BASE}/structures/{structure['id']}",
        headers=superadmin_headers,
        json={
            "row_version": version,
            "components": [{**_component("final", "50"), "id": structure["components"][1]["id"]}],
        },
    )
    assert removal.status_code == 409
    assert removal.json()["error"]["message_key"] == "assessment.error.component_in_use"

    stale = await client.patch(
        f"{BASE}/structures/{structure['id']}",
        headers=superadmin_headers,
        json={"row_version": version + 50, "name": "Renamed"},
    )
    assert stale.status_code == 409

    protected = await client.delete(f"{BASE}/structures/{structure['id']}", headers=superadmin_headers)
    assert protected.status_code == 409
    assert protected.json()["error"]["message_key"] == "assessment.error.structure_in_use"

    empty_year = await _year(client, superadmin_headers, code="2027-2028")
    empty = await _structure(client, superadmin_headers, empty_year, name="Empty")
    deleted = await client.delete(
        f"{BASE}/structures/{empty['id']}",
        headers=superadmin_headers,
        params={"reason": "Created by mistake"},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    listing = await client.get(
        f"{BASE}/structures", headers=superadmin_headers, params={"year_id": empty_year["id"]}
    )
    assert listing.json()["total"] == 0
