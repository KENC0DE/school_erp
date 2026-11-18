"""P4-06: assessment creation, bulk score entry, scoping and row versions.

A raw mark is the teacher's input; ``converted`` is always derived from the
structure component and the assessment's ``out_of``. These tests prove the
conversion, the idempotent natural-key upsert, the revision trail, and that a
teacher can only touch their own section and subject.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from modules.academics.models import Term
from modules.assessment.models import Score, ScoreRevision
from sqlalchemy import select

from tests.conftest import create_role, create_user, login, unique_email
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
ACADEMICS = "/api/v1/academics"
STUDENTS = "/api/v1/students"
STAFF = "/api/v1/staff"
ACTIVITY = "/api/v1/audit/activity"


async def _student(
    client,
    headers,
    *,
    number: str,
    year: dict,
    level: dict,
    section: dict,
    roll_number: str | None = None,
) -> dict:
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
                "roll_number": roll_number,
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _term(app, year_id: str) -> Term:
    async with app.state.db.session() as session:
        row = (
            (
                await session.execute(
                    select(Term).where(Term.year_id == uuid.UUID(year_id)).order_by(Term.number)
                )
            )
            .scalars()
            .first()
        )
        assert row is not None
        return row


async def _assessment(client, headers, **payload) -> dict:
    response = await client.post(f"{BASE}/assessments", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def _scores(client, headers, assessment_id: str, items: list[dict], **extra):
    return await client.put(
        f"{BASE}/assessments/{assessment_id}/scores",
        headers=headers,
        json={"items": items, **extra},
    )


async def _activity(client, headers) -> list[dict]:
    response = await client.get(ACTIVITY, headers=headers, params={"limit": 200})
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def _teacher(client, app, headers, *, year: dict, section: dict, subject: dict) -> dict:
    await create_role(
        app,
        "marks_teacher",
        [
            ("assessment.view", "assigned_subjects"),
            ("assessment.enter_marks", "assigned_subjects"),
        ],
    )
    email = unique_email("marks.teacher")
    user = await create_user(app, email, roles=["marks_teacher"])
    staff = await client.post(
        STAFF,
        headers=headers,
        json={
            "person": {
                "given_name_en": "Marks Teacher",
                "father_name_en": "Bekele",
                "grandfather_name_en": "Desta",
                "sex": "female",
                "date_of_birth": "1990-02-03",
            },
            "staff_number": "STF-MARKS-1",
            "hire_date": "2026-09-01",
        },
    )
    assert staff.status_code == 201, staff.text
    staff_id = staff.json()["id"]
    linked = await client.post(
        f"{STAFF}/{staff_id}/account",
        headers=headers,
        json={"user_id": str(user.id)},
    )
    assert linked.status_code == 200, linked.text
    assigned = await client.post(
        f"{STAFF}/{staff_id}/teaching-assignments",
        headers=headers,
        json={"year_id": year["id"], "section_id": section["id"], "subject_id": subject["id"]},
    )
    assert assigned.status_code == 201, assigned.text
    return {"user": user, "headers": await login(client, email)}


async def test_create_assessment_resolves_structure_and_validates(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    subject = await _subject(client, superadmin_headers, code="math-marks")
    term = await _term(app, year["id"])

    school = await _structure(
        client,
        superadmin_headers,
        year,
        components=[_component("quiz", "10"), _component("final", "50", sort_order=1)],
    )
    level_structure = await _structure(
        client,
        superadmin_headers,
        year,
        scope_type="level",
        level_id=level["id"],
        name="Grade 5 marks",
        components=[_component("quiz", "20"), _component("final", "50", sort_order=1)],
    )

    payload = {
        "year_id": year["id"],
        "term_id": str(term.id),
        "section_id": section["id"],
        "subject_id": subject["id"],
        "component_key": "quiz",
        "title": "Quiz 1",
        "assessment_date": "2026-10-01",
        "out_of": "15",
    }
    created = await _assessment(client, superadmin_headers, **payload)
    # The level structure is more specific than the school-wide one.
    assert created["structure_id"] == level_structure["id"]
    assert created["component_max_points"] == "20"
    assert created["out_of"] == "15"
    assert created["status"] == "active"
    assert created["term_name"]
    assert created["section_code"] == "A"
    assert created["subject_name"] == "Mathematics"
    assert created["scores"] == 0

    explicit = await _assessment(client, superadmin_headers, **payload, structure_id=school["id"])
    assert explicit["structure_id"] == school["id"]
    assert explicit["component_max_points"] == "10"

    listing = await client.get(
        f"{BASE}/assessments", headers=superadmin_headers, params={"year_id": year["id"]}
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 2

    detail = await client.get(f"{BASE}/assessments/{created['id']}", headers=superadmin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["title"] == "Quiz 1"

    missing_component = await client.post(
        f"{BASE}/assessments",
        headers=superadmin_headers,
        json={**payload, "component_key": "missing"},
    )
    assert missing_component.status_code == 404
    assert missing_component.json()["error"]["message_key"] == "assessment.error.component_not_found"

    zero_max = await client.post(
        f"{BASE}/assessments", headers=superadmin_headers, json={**payload, "out_of": "0"}
    )
    assert zero_max.status_code == 422

    unused_weight = await client.post(
        f"{BASE}/assessments", headers=superadmin_headers, json={**payload, "weight": "2"}
    )
    assert unused_weight.status_code == 422
    assert unused_weight.json()["error"]["message_key"] == "assessment.error.weight_unused"

    other_year = await _year(client, superadmin_headers, code="2027-2028")
    other_term = await _term(app, other_year["id"])
    term_mismatch = await client.post(
        f"{BASE}/assessments",
        headers=superadmin_headers,
        json={**payload, "year_id": other_year["id"]},
    )
    assert term_mismatch.status_code == 422
    assert term_mismatch.json()["error"]["message_key"] == "assessment.error.term_year"

    other_section = await _section(client, superadmin_headers, other_year, level)
    no_structure = await client.post(
        f"{BASE}/assessments",
        headers=superadmin_headers,
        json={
            **payload,
            "year_id": other_year["id"],
            "term_id": str(other_term.id),
            "section_id": other_section["id"],
        },
    )
    assert no_structure.status_code == 404
    assert no_structure.json()["error"]["message_key"] == "assessment.error.no_structure"

    archived = await client.patch(
        f"{BASE}/assessments/{created['id']}",
        headers=superadmin_headers,
        json={"row_version": created["row_version"], "status": "archived"},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"

    blocked = await client.patch(
        f"{BASE}/assessments/{created['id']}",
        headers=superadmin_headers,
        json={"row_version": archived.json()["row_version"], "title": "Renamed"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["message_key"] == "assessment.error.assessment_archived"

    unarchived = await client.patch(
        f"{BASE}/assessments/{created['id']}",
        headers=superadmin_headers,
        json={"row_version": archived.json()["row_version"], "status": "active"},
    )
    assert unarchived.status_code == 200, unarchived.text

    deleted = await client.delete(f"{BASE}/assessments/{explicit['id']}", headers=superadmin_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    gone = await client.get(f"{BASE}/assessments/{explicit['id']}", headers=superadmin_headers)
    assert gone.status_code == 404


async def test_bulk_scores_upsert_converts_revisions_and_is_idempotent(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    subject = await _subject(client, superadmin_headers, code="math-marks")
    term = await _term(app, year["id"])
    await _structure(
        client,
        superadmin_headers,
        year,
        components=[_component("quiz", "10"), _component("final", "50", sort_order=1)],
    )
    students = [
        await _student(
            client,
            superadmin_headers,
            number=f"STU-MARKS-{index}",
            year=year,
            level=level,
            section=section,
            roll_number=str(index),
        )
        for index in (1, 2)
    ]
    assessment = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Quiz 1",
        assessment_date="2026-10-01",
        out_of="15",
    )
    url = f"{BASE}/assessments/{assessment['id']}/scores"

    first = await client.put(
        url,
        headers=superadmin_headers,
        json={
            "items": [
                {"student_id": students[0]["id"], "raw_score": "7.5", "status": "present"},
                {"student_id": students[1]["id"], "status": "absent"},
            ],
            "reason": "Quiz 1 entry",
        },
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert (body["created"], body["updated"], body["unchanged"]) == (2, 0, 0)
    sheet = body["sheet"]
    assert [item["roll_number"] for item in sheet["items"]] == ["1", "2"]
    scored = sheet["items"][0]
    # 7.5 / 15 = 50%, and the quiz component is worth 10 points.
    assert scored["raw_score"] == "7.5"
    assert scored["converted"] == "5"
    assert scored["row_version"] == 1
    absent = sheet["items"][1]
    assert absent["status"] == "absent"
    assert absent["raw_score"] is None
    assert absent["converted"] is None
    assert sheet["stats"] == {
        "total": 2,
        "entered": 2,
        "missing": 0,
        "present": 1,
        "absent": 1,
        "excused": 0,
        "exempt": 0,
        "not_taken": 0,
        "out_of": "15",
        "component_max_points": "10",
        "average_converted": "5",
        "average_percent": "50",
        "highest_converted": "5",
        "lowest_converted": "5",
    }

    replay = await client.put(
        url,
        headers=superadmin_headers,
        json={
            "items": [
                {"student_id": students[0]["id"], "raw_score": "7.5", "status": "present"},
                {"student_id": students[1]["id"], "status": "absent"},
            ]
        },
    )
    assert replay.status_code == 200, replay.text
    assert (replay.json()["created"], replay.json()["updated"], replay.json()["unchanged"]) == (
        0,
        0,
        2,
    )

    updated = await client.put(
        url,
        headers=superadmin_headers,
        json={
            "items": [
                {
                    "student_id": students[0]["id"],
                    "raw_score": "12",
                    "status": "present",
                    "row_version": scored["row_version"],
                }
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["updated"] == 1
    assert updated.json()["sheet"]["items"][0]["converted"] == "8"

    stale = await client.put(
        url,
        headers=superadmin_headers,
        json={
            "items": [
                {
                    "student_id": students[0]["id"],
                    "raw_score": "1",
                    "status": "present",
                    "row_version": scored["row_version"],
                }
            ]
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CONFLICT"

    over = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [{"student_id": students[0]["id"], "raw_score": "16", "status": "present"}],
    )
    assert over.status_code == 422
    assert over.json()["error"]["message_key"] == "assessment.error.raw_over_out_of"

    missing_raw = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [{"student_id": students[0]["id"], "status": "present"}],
    )
    assert missing_raw.status_code == 422
    assert missing_raw.json()["error"]["message_key"] == "assessment.error.raw_required"

    raw_on_absent = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [{"student_id": students[0]["id"], "raw_score": "3", "status": "absent"}],
    )
    assert raw_on_absent.status_code == 422
    assert raw_on_absent.json()["error"]["message_key"] == "assessment.error.raw_not_allowed"

    duplicate = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [
            {"student_id": students[0]["id"], "raw_score": "3"},
            {"student_id": students[0]["id"], "raw_score": "4"},
        ],
    )
    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["message_key"] == "assessment.error.duplicate_score_entry"

    other_section = await _section(client, superadmin_headers, year, level, code="B")
    outsider = await _student(
        client,
        superadmin_headers,
        number="STU-MARKS-9",
        year=year,
        level=level,
        section=other_section,
    )
    not_enrolled = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [{"student_id": outsider["id"], "raw_score": "3"}],
    )
    assert not_enrolled.status_code == 422
    assert not_enrolled.json()["error"]["message_key"] == "assessment.error.student_not_enrolled"

    async with app.state.db.session() as session:
        score = await session.get(Score, uuid.UUID(scored["score_id"]))
        assert score is not None
        assert score.raw_score == Decimal("12")
        assert score.converted == Decimal("8")
        revisions = (
            (
                await session.execute(
                    select(ScoreRevision)
                    .where(ScoreRevision.score_id == score.id)
                    .order_by(ScoreRevision.created_at, ScoreRevision.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(revisions) == 2
        created_revision, latest = revisions
        assert created_revision.old_raw is None
        assert created_revision.new_raw == Decimal("7.5")
        assert created_revision.new_converted == Decimal("5")
        assert created_revision.reason == "Quiz 1 entry"
        assert latest.old_raw == Decimal("7.5")
        assert latest.new_raw == Decimal("12")
        assert latest.old_converted == Decimal("5")
        assert latest.new_converted == Decimal("8")
        assert latest.source == "entry"
        assert latest.reason is None

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {"assessment.assessment.create", "assessment.score.create", "assessment.score.update"} <= actions

    detail = await client.get(f"{BASE}/assessments/{assessment['id']}", headers=superadmin_headers)
    assert detail.json()["scores"] == 2
    assert detail.json()["entered"] == 1

    locked_max = await client.patch(
        f"{BASE}/assessments/{assessment['id']}",
        headers=superadmin_headers,
        json={"row_version": detail.json()["row_version"], "out_of": "20"},
    )
    assert locked_max.status_code == 409
    assert locked_max.json()["error"]["message_key"] == "assessment.error.out_of_locked"

    protected = await client.delete(f"{BASE}/assessments/{assessment['id']}", headers=superadmin_headers)
    assert protected.status_code == 409
    assert protected.json()["error"]["message_key"] == "assessment.error.assessment_in_use"

    archived = await client.patch(
        f"{BASE}/assessments/{assessment['id']}",
        headers=superadmin_headers,
        json={"row_version": detail.json()["row_version"], "status": "archived"},
    )
    assert archived.status_code == 200, archived.text
    closed = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [{"student_id": students[1]["id"], "raw_score": "3"}],
    )
    assert closed.status_code == 409
    assert closed.json()["error"]["message_key"] == "assessment.error.assessment_archived"


async def test_teacher_scope_limits_marks_to_teaching_assignments(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    first = await _section(client, superadmin_headers, year, level, code="A")
    second = await _section(client, superadmin_headers, year, level, code="B")
    maths = await _subject(client, superadmin_headers, code="math-marks")
    english = await _subject(client, superadmin_headers, code="english-marks")
    term = await _term(app, year["id"])
    await _structure(client, superadmin_headers, year, components=[_component("quiz", "10")])
    for index, section in enumerate((first, second), start=1):
        await _student(
            client,
            superadmin_headers,
            number=f"STU-SCOPE-{index}",
            year=year,
            level=level,
            section=section,
        )

    teacher = await _teacher(
        client,
        app,
        superadmin_headers,
        year=year,
        section=first,
        subject=maths,
    )
    headers = teacher["headers"]
    own = await _assessment(
        client,
        headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=first["id"],
        subject_id=maths["id"],
        component_key="quiz",
        title="My quiz",
        assessment_date="2026-10-01",
        out_of="10",
    )
    other = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=second["id"],
        subject_id=english["id"],
        component_key="quiz",
        title="Another class",
        assessment_date="2026-10-02",
        out_of="10",
    )

    listing = await client.get(f"{BASE}/assessments", headers=headers)
    assert listing.status_code == 200, listing.text
    assert [item["id"] for item in listing.json()["items"]] == [own["id"]]

    own_sheet = await client.get(f"{BASE}/assessments/{own['id']}/scores", headers=headers)
    assert own_sheet.status_code == 200, own_sheet.text
    assert own_sheet.json()["editable"] is True

    forbidden = await client.get(f"{BASE}/assessments/{other['id']}/scores", headers=headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["message_key"] == "error.scope_denied"

    score_entry = await _scores(
        client,
        headers,
        own["id"],
        [{"student_id": own_sheet.json()["items"][0]["student_id"], "raw_score": "9"}],
    )
    assert score_entry.status_code == 200, score_entry.text
    assert score_entry.json()["sheet"]["items"][0]["converted"] == "9"

    outside = await _scores(
        client,
        headers,
        other["id"],
        [{"student_id": own_sheet.json()["items"][0]["student_id"], "raw_score": "9"}],
    )
    assert outside.status_code == 403

    outside_create = await client.post(
        f"{BASE}/assessments",
        headers=headers,
        json={
            "year_id": year["id"],
            "term_id": str(term.id),
            "section_id": second["id"],
            "subject_id": english["id"],
            "component_key": "quiz",
            "title": "Not mine",
            "assessment_date": "2026-10-03",
            "out_of": "10",
        },
    )
    assert outside_create.status_code == 403

    unassigned_email = unique_email("marks.unassigned")
    await create_role(
        app,
        "marks_unassigned",
        [("assessment.view", "assigned_subjects"), ("assessment.enter_marks", "assigned_subjects")],
    )
    await create_user(app, unassigned_email, roles=["marks_unassigned"])
    unassigned = await login(client, unassigned_email)
    empty = await client.get(f"{BASE}/assessments", headers=unassigned)
    assert empty.status_code == 200
    assert empty.json()["items"] == []
    denied = await client.get(f"{BASE}/assessments/{own['id']}", headers=unassigned)
    assert denied.status_code == 403
