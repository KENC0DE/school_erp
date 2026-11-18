"""P4-09: assessment and academic-term domain events.

Marks changes publish ``marks.submitted`` and ``marks.published`` through the
transactional outbox, and closing a term publishes ``term.closed`` once. These
tests prove the event name, the payload needed by notifications and report
cards, and that a repeated close does not duplicate the event.
"""

from __future__ import annotations

import uuid

from core.events.models import DomainEvent
from modules.academics.models import Term
from sqlalchemy import select

from tests.test_assessment_results import _scale
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
from tests.test_assessment_workflow import _move, _submission

BASE = "/api/v1/assessment"
ACADEMICS = "/api/v1/academics"


async def _events(app, event_type: str) -> list[dict]:
    async with app.state.db.session() as session:
        rows = (
            (
                await session.execute(
                    select(DomainEvent)
                    .where(DomainEvent.event_type == event_type)
                    .order_by(DomainEvent.occurred_at, DomainEvent.id)
                )
            )
            .scalars()
            .all()
        )
        return [row.payload for row in rows]


async def test_marks_submitted_and_published_events(client, app, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    subject = await _subject(client, superadmin_headers, code="math-events")
    term = await _term(app, year["id"])
    await _structure(client, superadmin_headers, year, components=[_component("quiz", "10")])
    await _scale(app)
    student = await _student(
        client,
        superadmin_headers,
        number="STU-EVENT-1",
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
        title="Event quiz",
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
    submitted = await _move(client, superadmin_headers, submission["id"], "submit", note="Ready")
    assert submitted.status_code == 200, submitted.text

    submitted_events = await _events(app, "marks.submitted")
    assert len(submitted_events) == 1
    event = submitted_events[0]
    assert event["submission_id"] == submission["id"]
    assert event["year_id"] == year["id"]
    assert event["term_id"] == str(term.id)
    assert event["section_id"] == section["id"]
    assert event["subject_id"] == subject["id"]
    assert event["status"] == "submitted"
    assert event["assessments"] == 1
    assert event["scores"] == 1
    assert event["entered"] == 1
    assert event["submitted_at"]
    assert event["note"] == "Ready"

    approved = await _move(client, superadmin_headers, submission["id"], "approve")
    assert approved.status_code == 200, approved.text
    assert await _events(app, "marks.published") == []

    published = await _move(client, superadmin_headers, submission["id"], "publish")
    assert published.status_code == 200, published.text
    submission_events = await _events(app, "marks.published")
    assert len(submission_events) == 1
    assert submission_events[0]["submission_id"] == submission["id"]
    assert submission_events[0]["status"] == "published"
    assert submission_events[0]["published_at"]

    # Publishing the term result sheet is also a ``marks.published`` fact, with
    # the snapshot identity instead of a submission identity.
    snapshot = await client.post(
        f"{BASE}/results/term/publish",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "term_id": str(term.id),
            "section_id": section["id"],
        },
    )
    assert snapshot.status_code == 200, snapshot.text
    result_events = await _events(app, "marks.published")
    assert len(result_events) == 2
    sheet_event = result_events[-1]
    assert sheet_event["snapshot_id"] == snapshot.json()["id"]
    assert sheet_event["kind"] == "term"
    assert sheet_event["term_id"] == str(term.id)
    assert sheet_event["students"] == 1
    assert sheet_event["checksum"] == snapshot.json()["checksum"]
    assert "submission_id" not in sheet_event


async def test_term_closed_event_is_emitted_once(client, app, superadmin_headers, seeded) -> None:
    year = await _year(client, superadmin_headers)
    opened = await client.post(f"{ACADEMICS}/academic-years/{year['id']}/open", headers=superadmin_headers)
    assert opened.status_code == 200, opened.text

    async with app.state.db.session() as session:
        terms = list(
            (
                await session.execute(
                    select(Term).where(Term.year_id == uuid.UUID(year["id"])).order_by(Term.number)
                )
            )
            .scalars()
            .all()
        )
    assert len(terms) == 2

    first_opened = await client.post(
        f"{ACADEMICS}/academic-years/{year['id']}/terms/{terms[0].id}/open",
        headers=superadmin_headers,
    )
    assert first_opened.status_code == 200, first_opened.text
    first_closed = await client.post(
        f"{ACADEMICS}/academic-years/{year['id']}/terms/{terms[0].id}/close",
        headers=superadmin_headers,
        params={"reason": "Exams finished"},
    )
    assert first_closed.status_code == 200, first_closed.text

    events = await _events(app, "term.closed")
    assert len(events) == 1
    assert events[0]["year_id"] == year["id"]
    assert events[0]["year_code"] == year["code"]
    assert events[0]["term_id"] == str(terms[0].id)
    assert events[0]["term_number"] == 1
    assert events[0]["status"] == "closed"
    assert events[0]["closed_at"]
    assert events[0]["reason"] == "Exams finished"

    # Closing again is idempotent and must not duplicate the event.
    again = await client.post(
        f"{ACADEMICS}/academic-years/{year['id']}/terms/{terms[0].id}/close",
        headers=superadmin_headers,
    )
    assert again.status_code == 200, again.text
    assert len(await _events(app, "term.closed")) == 1

    year_closed = await client.post(
        f"{ACADEMICS}/academic-years/{year['id']}/close",
        headers=superadmin_headers,
        params={"reason": "Year end"},
    )
    assert year_closed.status_code == 200, year_closed.text
    events = await _events(app, "term.closed")
    # Only the second term was newly closed by the year close.
    assert len(events) == 2
    assert events[1]["term_id"] == str(terms[1].id)
    assert events[1]["term_number"] == 2
    assert events[1]["reason"] == "Year end"

    repeated = await client.post(
        f"{ACADEMICS}/academic-years/{year['id']}/close",
        headers=superadmin_headers,
    )
    assert repeated.status_code == 200, repeated.text
    assert len(await _events(app, "term.closed")) == 2
