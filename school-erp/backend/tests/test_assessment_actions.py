"""P4-17: AI-facing assessment actions and Document Studio fields.

The action registry already exposed the assessment mutations; this task adds
confirmation previews for entering marks and publishing, so the AI layer can
show what a write would do without performing it. The document fields describe
the published values a report-card layout may bind.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path

from core.actions.registry import registry
from modules.assessment.fields import FIELDS
from modules.assessment.manifest import MANIFEST as ASSESSMENT_MANIFEST
from modules.assessment.models import ResultSnapshot, Score
from sqlalchemy import func, select

from tests.test_assessment_results import _approve, _scale
from tests.test_assessment_scores import _assessment, _scores, _student, _term
from tests.test_assessment_structures import (
    _component,
    _enable,
    _level,
    _section,
    _structure,
    _subject,
    _year,
)
from tests.test_assessment_workflow import _submission

BASE = "/api/v1/assessment"
AI = "/api/v1/ai/actions"


def test_mutating_actions_declare_previews_and_fields_are_registered() -> None:
    for key in (
        "assessment.scores.upsert",
        "assessment.submissions.publish",
        "assessment.results.publish_term",
        "assessment.results.republish_term",
        "assessment.results.publish_year",
        "assessment.results.republish_year",
    ):
        action = registry.get(key)
        assert action is not None, key
        assert action.preview is not None, key

    keys = {field.key for field in ASSESSMENT_MANIFEST.document_fields}
    assert {
        "student.marks.term.total",
        "student.marks.term.grade",
        "student.marks.year.percent",
        "student.marks.subjects",
        "student.rank",
        "student.rank_size",
    } <= keys
    assert len(keys) == len(FIELDS)
    assert all(field.label_key.startswith("assessment.field.") for field in FIELDS)

    bundle = json.loads((Path(__file__).resolve().parents[1] / "modules/assessment/i18n/en.json").read_text())
    for field in FIELDS:
        assert field.label_key.removeprefix("assessment.") in bundle


async def test_entering_marks_preview_converts_without_writing(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    subject = await _subject(client, superadmin_headers, code="math-preview")
    term = await _term(app, year["id"])
    await _structure(
        client,
        superadmin_headers,
        year,
        components=[_component("quiz", "20")],
    )
    student = await _student(
        client,
        superadmin_headers,
        number="STU-PREVIEW-1",
        year=year,
        level=level,
        section=section,
        roll_number="1",
    )
    assessment = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Preview quiz",
        assessment_date="2026-10-01",
        out_of="15",
    )
    preview_url = f"{AI}/assessment.scores.upsert/preview"

    response = await client.post(
        preview_url,
        headers=superadmin_headers,
        json={
            "assessment_id": assessment["id"],
            "items": [
                {"student_id": student["id"], "raw_score": "7.5"},
                {"student_id": student["id"], "status": "absent"},
            ],
        },
    )
    # A duplicate child is rejected with the same rule the write uses.
    assert response.status_code == 422, response.text

    response = await client.post(
        preview_url,
        headers=superadmin_headers,
        json={
            "assessment_id": assessment["id"],
            "items": [{"student_id": student["id"], "raw_score": "7.5"}],
        },
    )
    assert response.status_code == 200, response.text
    preview = response.json()["preview"]
    assert preview["created"] == 1
    assert preview["updated"] == 0
    assert preview["unchanged"] == 0
    item = preview["items"][0]
    assert item["student_number"] == "STU-PREVIEW-1"
    assert item["change"] == "create"
    # 7.5 / 15 = 50%, and the quiz component is worth 20 points.
    assert item["converted"] == "10"
    assert preview["out_of"] == "15"

    async with app.state.db.session() as session:
        assert int((await session.execute(select(func.count()).select_from(Score))).scalar_one()) == 0

    created = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [{"student_id": student["id"], "raw_score": "7.5"}],
    )
    assert created.status_code == 200, created.text

    response = await client.post(
        preview_url,
        headers=superadmin_headers,
        json={
            "assessment_id": assessment["id"],
            "items": [{"student_id": student["id"], "raw_score": "7.5"}],
        },
    )
    assert response.json()["preview"]["unchanged"] == 1

    response = await client.post(
        preview_url,
        headers=superadmin_headers,
        json={
            "assessment_id": assessment["id"],
            "items": [{"student_id": student["id"], "raw_score": "12"}],
        },
    )
    preview = response.json()["preview"]
    assert preview["updated"] == 1
    assert preview["items"][0]["change"] == "update"
    assert preview["items"][0]["converted"] == "16"

    # The preview never wrote the proposed value.
    async with app.state.db.session() as session:
        score = (
            await session.execute(select(Score).where(Score.assessment_id == uuid.UUID(assessment["id"])))
        ).scalar_one()
        assert score.raw_score is not None
        assert score.raw_score == Decimal("7.5")


async def test_publishing_preview_reports_the_sheet_without_a_snapshot(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    subject = await _subject(client, superadmin_headers, code="math-publish-preview")
    term = await _term(app, year["id"])
    await _structure(
        client,
        superadmin_headers,
        year,
        components=[_component("quiz", "10"), _component("final", "40", sort_order=1)],
        intended_total="50",
    )
    await _scale(app)
    first = await _student(
        client,
        superadmin_headers,
        number="STU-PUBLISH-1",
        year=year,
        level=level,
        section=section,
        roll_number="1",
    )
    second = await _student(
        client,
        superadmin_headers,
        number="STU-PUBLISH-2",
        year=year,
        level=level,
        section=section,
        roll_number="2",
    )
    assessment = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Publish preview quiz",
        assessment_date="2026-10-01",
        out_of="10",
    )
    entered = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [
            {"student_id": first["id"], "raw_score": "9"},
            {"student_id": second["id"], "raw_score": "5"},
        ],
    )
    assert entered.status_code == 200, entered.text
    await _approve(
        client,
        superadmin_headers,
        year=year,
        term=term,
        section=section,
        subject=subject,
    )
    payload = {
        "year_id": year["id"],
        "term_id": str(term.id),
        "section_id": section["id"],
    }

    preview = await client.post(
        f"{AI}/assessment.results.publish_term/preview",
        headers=superadmin_headers,
        json=payload,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()["preview"]
    assert body["kind"] == "term"
    assert body["term_name"] == term.name
    assert body["section_code"] == "A"
    assert body["students"] == 2
    assert body["subjects"] == 1
    assert body["already_published"] is False
    assert [row["student_number"] for row in body["rows"]] == [
        "STU-PUBLISH-1",
        "STU-PUBLISH-2",
    ]
    assert body["rows"][0]["total"] == "9"
    assert body["rows"][0]["out_of"] == "50"
    assert body["rows"][0]["percent"] == "18"
    assert body["rows"][1]["total"] == "5"
    assert body["rows"][1]["percent"] == "10"

    async with app.state.db.session() as session:
        snapshots = int(
            (await session.execute(select(func.count()).select_from(ResultSnapshot))).scalar_one()
        )
    assert snapshots == 0

    published = await client.post(f"{BASE}/results/term/publish", headers=superadmin_headers, json=payload)
    assert published.status_code == 200, published.text
    snapshot_id = published.json()["id"]

    # Publishing again is the same conflict the write raises; re-publish is the
    # path that previews the new snapshot.
    conflict = await client.post(
        f"{AI}/assessment.results.publish_term/preview",
        headers=superadmin_headers,
        json=payload,
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["error"]["message_key"] == "assessment.error.results_already_published"

    republish = await client.post(
        f"{AI}/assessment.results.republish_term/preview",
        headers=superadmin_headers,
        json=payload,
    )
    assert republish.status_code == 200, republish.text
    body = republish.json()["preview"]
    assert body["already_published"] is True
    assert body["snapshot_id"] == snapshot_id


async def test_publishing_marks_preview_requires_an_approved_submission(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    subject = await _subject(client, superadmin_headers, code="math-submission-preview")
    term = await _term(app, year["id"])
    await _structure(client, superadmin_headers, year, components=[_component("quiz", "10")])
    student = await _student(
        client,
        superadmin_headers,
        number="STU-SUBMISSION-PREVIEW",
        year=year,
        level=level,
        section=section,
    )
    assessment = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Submission preview",
        assessment_date="2026-10-01",
        out_of="10",
    )
    entered = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [{"student_id": student["id"], "raw_score": "8"}],
    )
    assert entered.status_code == 200, entered.text
    submission = await _submission(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=section["id"],
        subject_id=subject["id"],
    )
    payload = {"submission_id": submission["id"]}

    draft = await client.post(
        f"{AI}/assessment.submissions.publish/preview",
        headers=superadmin_headers,
        json=payload,
    )
    assert draft.status_code == 409, draft.text
    assert draft.json()["error"]["message_key"] == "assessment.error.submission_not_approved"

    approved = await _approve(
        client,
        superadmin_headers,
        year=year,
        term=term,
        section=section,
        subject=subject,
    )
    ready = await client.post(
        f"{AI}/assessment.submissions.publish/preview",
        headers=superadmin_headers,
        json=payload,
    )
    assert ready.status_code == 200, ready.text
    preview = ready.json()["preview"]
    assert preview["submission_id"] == approved["id"]
    assert preview["status"] == "approved"


async def test_previews_are_permission_checked(client, superadmin_headers, limited_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    denied = await client.post(
        f"{AI}/assessment.scores.upsert/preview",
        headers=limited_headers,
        json={"assessment_id": "00000000-0000-0000-0000-000000000000", "items": []},
    )
    assert denied.status_code == 403, denied.text
