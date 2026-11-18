"""P4-07: marking windows, submission states and correction requests.

The workflow is deliberately explicit: ``draft → submitted → approved →
published → locked``, with rejection returning to ``draft``. These tests prove
the window gates entry, that illegal jumps are refused, that only locked marks
accept a correction, and that an accepted correction rewrites the score with a
revision and an audit trail but never touches the raw score history.
"""

from __future__ import annotations

import uuid

from modules.assessment.models import CorrectionRequest, ScoreRevision
from sqlalchemy import func, select

from tests.conftest import create_role, create_user, login, unique_email
from tests.test_assessment_scores import (
    _activity,
    _assessment,
    _scores,
    _student,
    _term,
)
from tests.test_assessment_structures import (
    _component,
    _enable,
    _level,
    _section,
    _structure,
    _subject,
    _year,
)

BASE = "/api/v1/assessment"
STAFF = "/api/v1/staff"

OPEN = {"opens_at": "2020-01-01T00:00:00+00:00", "closes_at": "2030-01-01T00:00:00+00:00"}
CLOSED = {"opens_at": "2020-01-01T00:00:00+00:00", "closes_at": "2020-12-31T00:00:00+00:00"}


async def _window(client, headers, **payload) -> dict:
    response = await client.post(f"{BASE}/windows", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _ensure(client, headers, **payload):
    return await client.post(f"{BASE}/submissions", headers=headers, json=payload)


async def _submission(client, headers, **payload) -> dict:
    response = await _ensure(client, headers, **payload)
    assert response.status_code == 200, response.text
    return response.json()["submission"]


async def _move(client, headers, submission_id: str, action: str, **payload):
    return await client.post(f"{BASE}/submissions/{submission_id}/{action}", headers=headers, json=payload)


async def _correction(client, headers, **payload):
    return await client.post(f"{BASE}/corrections", headers=headers, json=payload)


async def test_marking_windows_control_score_entry(client, app, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    subject = await _subject(client, superadmin_headers, code="math-window")
    term = await _term(app, year["id"])
    await _structure(client, superadmin_headers, year, components=[_component("quiz", "10")])
    student = await _student(
        client,
        superadmin_headers,
        number="STU-WINDOW-1",
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
        title="Window quiz",
        assessment_date="2026-10-01",
        out_of="15",
    )

    both_scopes = await client.post(
        f"{BASE}/windows",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "term_id": str(term.id),
            "level_id": level["id"],
            "section_id": section["id"],
            **OPEN,
        },
    )
    assert both_scopes.status_code == 422, both_scopes.text

    bad_dates = await client.post(
        f"{BASE}/windows",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "term_id": str(term.id),
            "opens_at": "2026-10-02T00:00:00+00:00",
            "closes_at": "2026-10-01T00:00:00+00:00",
        },
    )
    assert bad_dates.status_code == 422, bad_dates.text

    other_year = await _year(client, superadmin_headers, code="2027-2028")
    other_section = await _section(client, superadmin_headers, other_year, level, code="C")
    section_mismatch = await client.post(
        f"{BASE}/windows",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "term_id": str(term.id),
            "section_id": other_section["id"],
            **OPEN,
        },
    )
    assert section_mismatch.status_code == 422
    assert section_mismatch.json()["error"]["message_key"] == "assessment.error.section_year"

    window = await _window(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        **OPEN,
    )
    assert window["state"] == "open"
    assert window["scope_key"] == "all"

    level_window = await _window(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        level_id=level["id"],
        **OPEN,
    )
    assert level_window["scope_key"] == f"level:{level['id']}"

    removed_level = await client.delete(f"{BASE}/windows/{level_window['id']}", headers=superadmin_headers)
    assert removed_level.status_code == 200, removed_level.text

    listing = await client.get(
        f"{BASE}/windows", headers=superadmin_headers, params={"term_id": str(term.id)}
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1

    detail = await client.get(f"{BASE}/windows/{window['id']}", headers=superadmin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["state"] == "open"

    stale = await client.patch(
        f"{BASE}/windows/{window['id']}",
        headers=superadmin_headers,
        json={"row_version": window["row_version"] + 1, "note": "stale"},
    )
    assert stale.status_code == 409

    invalid_update = await client.patch(
        f"{BASE}/windows/{window['id']}",
        headers=superadmin_headers,
        json={
            "row_version": window["row_version"],
            "opens_at": "2026-10-02T00:00:00+00:00",
            "closes_at": "2026-10-01T00:00:00+00:00",
        },
    )
    assert invalid_update.status_code == 422
    assert invalid_update.json()["error"]["message_key"] == "assessment.error.window_dates"

    opened = await client.put(
        f"{BASE}/assessments/{assessment['id']}/scores",
        headers=superadmin_headers,
        json={"items": [{"student_id": student["id"], "raw_score": "9"}]},
    )
    assert opened.status_code == 200, opened.text

    closed = await client.patch(
        f"{BASE}/windows/{window['id']}",
        headers=superadmin_headers,
        json={"row_version": window["row_version"], **CLOSED},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["state"] == "closed"

    blocked = await client.put(
        f"{BASE}/assessments/{assessment['id']}/scores",
        headers=superadmin_headers,
        json={"items": [{"student_id": student["id"], "raw_score": "10"}]},
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["message_key"] == "assessment.error.window_closed"

    deleted = await client.delete(f"{BASE}/windows/{window['id']}", headers=superadmin_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True

    gone = await client.get(f"{BASE}/windows/{window['id']}", headers=superadmin_headers)
    assert gone.status_code == 404
    assert gone.json()["error"]["message_key"] == "assessment.error.window_not_found"

    # With no window left, the term has no deadline and entry stays open.
    reopened = await client.put(
        f"{BASE}/assessments/{assessment['id']}/scores",
        headers=superadmin_headers,
        json={"items": [{"student_id": student["id"], "raw_score": "10"}]},
    )
    assert reopened.status_code == 200, reopened.text


async def test_submission_state_machine_and_corrections(client, app, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level, code="A")
    other_section = await _section(client, superadmin_headers, year, level, code="B")
    subject = await _subject(client, superadmin_headers, code="math-flow")
    term = await _term(app, year["id"])
    await _structure(
        client,
        superadmin_headers,
        year,
        components=[_component("quiz", "10"), _component("final", "50", sort_order=1)],
    )
    first = await _student(
        client,
        superadmin_headers,
        number="STU-FLOW-1",
        year=year,
        level=level,
        section=section,
    )
    second = await _student(
        client,
        superadmin_headers,
        number="STU-FLOW-2",
        year=year,
        level=level,
        section=other_section,
    )
    assessment = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Flow quiz",
        assessment_date="2026-10-01",
        out_of="15",
    )
    other_assessment = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=other_section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Other quiz",
        assessment_date="2026-10-01",
        out_of="15",
    )

    scores = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [{"student_id": first["id"], "raw_score": "7.5"}],
        reason="First entry",
    )
    assert scores.status_code == 200, scores.text
    score_id = scores.json()["sheet"]["items"][0]["score_id"]

    scope = {
        "year_id": year["id"],
        "term_id": str(term.id),
        "section_id": section["id"],
        "subject_id": subject["id"],
    }
    submission = await _submission(client, superadmin_headers, **scope)
    assert submission["status"] == "draft"
    assert submission["assessments"] == 1
    assert submission["scores"] == 1
    assert submission["entered"] == 1

    replay = await _submission(client, superadmin_headers, **scope)
    assert replay["id"] == submission["id"]

    early_publish = await _move(
        client, superadmin_headers, submission["id"], "publish", row_version=submission["row_version"]
    )
    assert early_publish.status_code == 409
    assert early_publish.json()["error"]["message_key"] == "assessment.error.submission_state"

    early_correction = await _correction(
        client,
        superadmin_headers,
        score_id=score_id,
        new_raw="8",
        reason="Too early",
    )
    assert early_correction.status_code == 409
    assert early_correction.json()["error"]["message_key"] == "assessment.error.not_locked"

    submitted = await _move(client, superadmin_headers, submission["id"], "submit", note="Ready for review")
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["submitted_at"] is not None
    assert submitted.json()["submitted_by"] is not None
    assert submitted.json()["note"] == "Ready for review"

    resubmit = await _move(client, superadmin_headers, submission["id"], "submit")
    assert resubmit.status_code == 409
    assert resubmit.json()["error"]["message_key"] == "assessment.error.submission_state"

    blocked_entry = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [{"student_id": first["id"], "raw_score": "8"}],
    )
    assert blocked_entry.status_code == 409
    assert blocked_entry.json()["error"]["message_key"] == "assessment.error.marks_not_draft"

    approved = await _move(
        client, superadmin_headers, submission["id"], "approve", row_version=submitted.json()["row_version"]
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_at"] is not None

    published = await _move(client, superadmin_headers, submission["id"], "publish")
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"

    locked = await _move(client, superadmin_headers, submission["id"], "lock")
    assert locked.status_code == 200, locked.text
    assert locked.json()["status"] == "locked"
    assert locked.json()["locked_at"] is not None

    unchanged = await _correction(
        client,
        superadmin_headers,
        score_id=score_id,
        new_raw="7.5",
        reason="No real change",
    )
    assert unchanged.status_code == 422
    assert unchanged.json()["error"]["message_key"] == "assessment.error.correction_unchanged"

    requested = await _correction(
        client,
        superadmin_headers,
        score_id=score_id,
        new_raw="8",
        reason="Marking slip",
    )
    assert requested.status_code == 201, requested.text
    correction = requested.json()
    assert correction["status"] == "pending"
    assert correction["old_raw"] == "7.5"
    assert correction["new_raw"] == "8"
    assert correction["student_id"] == first["id"]
    assert correction["requested_at"] is not None

    duplicate = await _correction(
        client,
        superadmin_headers,
        score_id=score_id,
        new_raw="9",
        reason="Second request",
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["message_key"] == "assessment.error.correction_pending"

    pending = await client.get(
        f"{BASE}/corrections", headers=superadmin_headers, params={"status": "pending"}
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["total"] == 1

    detail = await client.get(f"{BASE}/corrections/{correction['id']}", headers=superadmin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["reason"] == "Marking slip"

    accepted = await client.post(
        f"{BASE}/corrections/{correction['id']}/approve",
        headers=superadmin_headers,
        json={"note": "Confirmed with the teacher"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "approved"
    assert accepted.json()["decided_at"] is not None
    assert accepted.json()["decision_note"] == "Confirmed with the teacher"

    again = await client.post(
        f"{BASE}/corrections/{correction['id']}/approve",
        headers=superadmin_headers,
        json={},
    )
    assert again.status_code == 409
    assert again.json()["error"]["message_key"] == "assessment.error.correction_state"

    sheet = await client.get(f"{BASE}/assessments/{assessment['id']}/scores", headers=superadmin_headers)
    assert sheet.status_code == 200, sheet.text
    corrected = sheet.json()["items"][0]
    assert corrected["raw_score"] == "8"
    # 8 / 15 = 53.33%, and the quiz component is worth 10 points.
    assert corrected["converted"] == "5.33"

    rejected_request = await _correction(
        client,
        superadmin_headers,
        score_id=score_id,
        new_raw="9",
        reason="Still too low",
    )
    assert rejected_request.status_code == 201, rejected_request.text
    rejected = await client.post(
        f"{BASE}/corrections/{rejected_request.json()['id']}/reject",
        headers=superadmin_headers,
        json={"note": "The mark stands"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["decision_note"] == "The mark stands"

    unchanged_score = await client.get(
        f"{BASE}/assessments/{assessment['id']}/scores", headers=superadmin_headers
    )
    assert unchanged_score.json()["items"][0]["raw_score"] == "8"

    async with app.state.db.session() as session:
        revisions = (
            (
                await session.execute(
                    select(ScoreRevision)
                    .where(ScoreRevision.score_id == uuid.UUID(score_id))
                    .order_by(ScoreRevision.created_at, ScoreRevision.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(revisions) == 2
        latest = revisions[-1]
        assert latest.source == "correction"
        assert latest.correction_request_id == uuid.UUID(correction["id"])
        assert latest.old_raw is not None and latest.new_raw is not None
        assert latest.reason == "Marking slip"
        pending_rows = (
            await session.execute(
                select(func.count())
                .select_from(CorrectionRequest)
                .where(CorrectionRequest.score_id == uuid.UUID(score_id))
            )
        ).scalar_one()
        assert int(pending_rows) == 2

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {
        "assessment.submission.create",
        "assessment.submission.submit",
        "assessment.submission.approve",
        "assessment.submission.publish",
        "assessment.submission.lock",
        "assessment.correction.create",
        "assessment.correction.approve",
        "assessment.correction.reject",
    } <= actions

    listing = await client.get(f"{BASE}/submissions", headers=superadmin_headers, params={"status": "locked"})
    assert listing.status_code == 200, listing.text
    assert [item["id"] for item in listing.json()["items"]] == [submission["id"]]

    other_scope = {
        "year_id": year["id"],
        "term_id": str(term.id),
        "section_id": other_section["id"],
        "subject_id": subject["id"],
    }
    empty_submission = await _submission(client, superadmin_headers, **other_scope)
    assert empty_submission["scores"] == 0
    no_marks = await _move(client, superadmin_headers, empty_submission["id"], "submit")
    assert no_marks.status_code == 422
    assert no_marks.json()["error"]["message_key"] == "assessment.error.no_marks"

    filled = await _scores(
        client,
        superadmin_headers,
        other_assessment["id"],
        [{"student_id": second["id"], "status": "absent"}],
    )
    assert filled.status_code == 200, filled.text

    # An absent mark is still a mark for the submission's progress counts, but
    # entry of a raw value is what the submit guard counts.
    still_empty = await _move(client, superadmin_headers, empty_submission["id"], "submit")
    assert still_empty.status_code == 422
    assert still_empty.json()["error"]["message_key"] == "assessment.error.no_marks"

    present = await _scores(
        client,
        superadmin_headers,
        other_assessment["id"],
        [{"student_id": second["id"], "raw_score": "6"}],
    )
    assert present.status_code == 200, present.text
    pending_review = await _move(client, superadmin_headers, empty_submission["id"], "submit")
    assert pending_review.status_code == 200, pending_review.text

    returned = await _move(
        client, superadmin_headers, empty_submission["id"], "reject", note="Fix the second entry"
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["status"] == "draft"
    assert returned.json()["submitted_at"] is None
    assert returned.json()["note"] == "Fix the second entry"

    editable_again = await _scores(
        client,
        superadmin_headers,
        other_assessment["id"],
        [{"student_id": second["id"], "raw_score": "7"}],
    )
    assert editable_again.status_code == 200, editable_again.text


async def _teacher(
    client,
    app,
    headers,
    *,
    year: dict,
    section: dict,
    subject: dict,
    permissions: list[tuple[str, str]],
    key: str,
    number: str,
) -> dict:
    await create_role(app, key, permissions)
    email = unique_email(key)
    user = await create_user(app, email, roles=[key])
    staff = await client.post(
        STAFF,
        headers=headers,
        json={
            "person": {
                "given_name_en": f"Workflow {number}",
                "father_name_en": "Bekele",
                "grandfather_name_en": "Desta",
                "sex": "female",
                "date_of_birth": "1990-02-03",
            },
            "staff_number": number,
            "hire_date": "2026-09-01",
        },
    )
    assert staff.status_code == 201, staff.text
    linked = await client.post(
        f"{STAFF}/{staff.json()['id']}/account", headers=headers, json={"user_id": str(user.id)}
    )
    assert linked.status_code == 200, linked.text
    if section is not None:
        assigned = await client.post(
            f"{STAFF}/{staff.json()['id']}/teaching-assignments",
            headers=headers,
            json={"year_id": year["id"], "section_id": section["id"], "subject_id": subject["id"]},
        )
        assert assigned.status_code == 201, assigned.text
    return {"email": email, "headers": await login(client, email)}


async def test_workflow_respects_teacher_scope(client, app, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    own_section = await _section(client, superadmin_headers, year, level, code="A")
    other_section = await _section(client, superadmin_headers, year, level, code="B")
    subject = await _subject(client, superadmin_headers, code="math-scope-flow")
    term = await _term(app, year["id"])
    await _structure(client, superadmin_headers, year, components=[_component("quiz", "10")])
    student = await _student(
        client,
        superadmin_headers,
        number="STU-SCOPE-FLOW-1",
        year=year,
        level=level,
        section=own_section,
    )
    assessment = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=own_section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Scoped quiz",
        assessment_date="2026-10-01",
        out_of="10",
    )
    await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=other_section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Other scoped quiz",
        assessment_date="2026-10-01",
        out_of="10",
    )

    teacher = await _teacher(
        client,
        app,
        superadmin_headers,
        year=year,
        section=own_section,
        subject=subject,
        permissions=[
            ("assessment.view", "assigned_subjects"),
            ("assessment.enter_marks", "assigned_subjects"),
            ("assessment.submit", "assigned_subjects"),
            ("assessment.correct", "assigned_subjects"),
        ],
        key="workflow_teacher",
        number="STF-FLOW-1",
    )
    headers = teacher["headers"]

    scope = {
        "year_id": year["id"],
        "term_id": str(term.id),
        "section_id": own_section["id"],
        "subject_id": subject["id"],
    }
    submission = await _submission(client, headers, **scope)
    assert submission["status"] == "draft"

    entered = await _scores(
        client,
        headers,
        assessment["id"],
        [{"student_id": student["id"], "raw_score": "9"}],
    )
    assert entered.status_code == 200, entered.text

    submitted = await _move(client, headers, submission["id"], "submit")
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"

    foreign_scope = {
        "year_id": year["id"],
        "term_id": str(term.id),
        "section_id": other_section["id"],
        "subject_id": subject["id"],
    }
    forbidden = await _ensure(client, headers, **foreign_scope)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["message_key"] == "error.scope_denied"

    listed = await client.get(f"{BASE}/submissions", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [submission["id"]]

    cannot_approve = await _move(client, headers, submission["id"], "approve")
    assert cannot_approve.status_code == 403

    takeover = await _teacher(
        client,
        app,
        superadmin_headers,
        year=year,
        section=None,
        subject=subject,
        permissions=[
            ("assessment.view", "assigned_subjects"),
            ("assessment.correct", "assigned_subjects"),
        ],
        key="workflow_outsider",
        number="STF-FLOW-2",
    )
    outsider = takeover["headers"]
    outside_list = await client.get(f"{BASE}/submissions", headers=outsider)
    assert outside_list.status_code == 200
    assert outside_list.json()["items"] == []

    approved = await _move(client, superadmin_headers, submission["id"], "approve")
    assert approved.status_code == 200, approved.text
    published = await _move(client, superadmin_headers, submission["id"], "publish")
    assert published.status_code == 200, published.text
    locked = await _move(client, superadmin_headers, submission["id"], "lock")
    assert locked.status_code == 200, locked.text

    sheet = await client.get(f"{BASE}/assessments/{assessment['id']}/scores", headers=headers)
    score_id = sheet.json()["items"][0]["score_id"]

    outsider_request = await _correction(
        client,
        outsider,
        score_id=score_id,
        new_raw="10",
        reason="Not my class",
    )
    assert outsider_request.status_code == 403
    assert outsider_request.json()["error"]["message_key"] == "error.scope_denied"

    correction = await _correction(
        client,
        headers,
        score_id=score_id,
        new_raw="10",
        reason="Rounded up",
    )
    assert correction.status_code == 201, correction.text

    teacher_cannot_decide = await client.post(
        f"{BASE}/corrections/{correction.json()['id']}/approve", headers=headers, json={}
    )
    assert teacher_cannot_decide.status_code == 403
