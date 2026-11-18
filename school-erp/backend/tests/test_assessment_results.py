"""P4-08: term and year results, ranks and publish snapshots.

Results are derived from the stored raw scores and the current mark structure.
These tests prove the term total and grading, competition ranks, the publish
gate (approved marks only), the immutable snapshot and ``TermResult`` copy, and
that re-publishing after a scale change is an explicit audited action that
supersedes the previous snapshot. A scoped teacher sees only their own subject
and never the class-wide rank.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from modules.assessment.models import (
    GradeBand,
    GradeScale,
    ResultSnapshot,
    ScaleAssignment,
    TermResult,
)
from sqlalchemy import select

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
from tests.test_assessment_workflow import _move, _submission

BASE = "/api/v1/assessment"
STAFF = "/api/v1/staff"

DEFAULT_BANDS = [
    ("0", "50", "F", False, "0"),
    ("50", "75", "C", True, "2"),
    ("75", "100", "A", True, "4"),
]


async def _scale(
    app,
    *,
    name: str = "Default scale",
    version: int = 1,
    bands: list[tuple[str, str, str, bool, str]] | None = None,
    is_default: bool = True,
) -> str:
    rows = bands or DEFAULT_BANDS
    async with app.state.db.session() as session:
        scale = GradeScale(
            name=name,
            type="numeric_bands",
            is_default=is_default,
            version=version,
        )
        session.add(scale)
        await session.flush()
        for index, (low, high, label, is_pass, gpa) in enumerate(rows):
            session.add(
                GradeBand(
                    scale_id=scale.id,
                    min_value=Decimal(low),
                    max_value=Decimal(high),
                    label=label,
                    sort_order=index * 10,
                    is_pass=is_pass,
                    gpa_points=Decimal(gpa),
                )
            )
        if is_default:
            session.add(ScaleAssignment(scale_id=scale.id, context="default", scope_key="default"))
        await session.commit()
        return str(scale.id)


async def _terms(app, year_id: str):
    from modules.academics.models import Term

    async with app.state.db.session() as session:
        return list(
            (
                await session.execute(
                    select(Term).where(Term.year_id == uuid.UUID(year_id)).order_by(Term.number)
                )
            )
            .scalars()
            .all()
        )


async def _approve(
    client,
    headers,
    *,
    year: dict,
    term,
    section: dict,
    subject: dict,
) -> dict:
    submission = await _submission(
        client,
        headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=section["id"],
        subject_id=subject["id"],
    )
    submitted = await _move(client, headers, submission["id"], "submit")
    assert submitted.status_code == 200, submitted.text
    approved = await _move(client, headers, submission["id"], "approve")
    assert approved.status_code == 200, approved.text
    return approved.json()


async def test_term_results_sheet_grades_and_ranks(client, app, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    subject = await _subject(client, superadmin_headers, code="math-results")
    term = await _term(app, year["id"])
    await _structure(
        client,
        superadmin_headers,
        year,
        components=[
            _component("quiz", "10"),
            _component("final", "40", sort_order=1),
        ],
        intended_total="50",
    )
    scale_id = await _scale(app)
    first = await _student(
        client,
        superadmin_headers,
        number="STU-RESULT-1",
        year=year,
        level=level,
        section=section,
        roll_number="1",
    )
    second = await _student(
        client,
        superadmin_headers,
        number="STU-RESULT-2",
        year=year,
        level=level,
        section=section,
        roll_number="2",
    )
    third = await _student(
        client,
        superadmin_headers,
        number="STU-RESULT-3",
        year=year,
        level=level,
        section=section,
        roll_number="3",
    )
    quiz = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Result quiz",
        assessment_date="2026-10-01",
        out_of="15",
    )
    final = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=section["id"],
        subject_id=subject["id"],
        component_key="final",
        title="Result final",
        assessment_date="2026-11-01",
        out_of="13",
    )
    entered = await _scores(
        client,
        superadmin_headers,
        quiz["id"],
        [
            {"student_id": first["id"], "raw_score": "12"},
            {"student_id": second["id"], "raw_score": "12"},
            {"student_id": third["id"], "raw_score": "6"},
        ],
    )
    assert entered.status_code == 200, entered.text
    entered = await _scores(
        client,
        superadmin_headers,
        final["id"],
        [
            {"student_id": first["id"], "raw_score": "9"},
            {"student_id": second["id"], "raw_score": "9"},
            {"student_id": third["id"], "raw_score": "5"},
        ],
    )
    assert entered.status_code == 200, entered.text

    response = await client.get(
        f"{BASE}/results/term",
        headers=superadmin_headers,
        params={
            "year_id": year["id"],
            "term_id": str(term.id),
            "section_id": section["id"],
        },
    )
    assert response.status_code == 200, response.text
    sheet = response.json()
    assert sheet["year_code"] == year["code"]
    assert sheet["term_name"] == term.name
    assert sheet["section_code"] == "A"
    assert sheet["subject_count"] == 1
    assert [student["student_number"] for student in sheet["students"]] == [
        "STU-RESULT-1",
        "STU-RESULT-2",
        "STU-RESULT-3",
    ]

    top = sheet["students"][0]
    assert top["total"] == "35.69"
    assert top["out_of"] == "50"
    assert top["percent"] == "71.38"
    assert top["grade_label"] == "C"
    assert top["gpa_points"] == "2"
    assert top["is_pass"] is True
    # Equal marks share first place; the next student is third (competition).
    assert top["rank"] == 1
    assert top["rank_size"] == 3
    assert sheet["students"][1]["rank"] == 1
    assert sheet["students"][2]["rank"] == 3

    subject_row = top["subjects"][0]
    assert subject_row["subject_id"] == subject["id"]
    assert subject_row["subject_name"] == "Mathematics"
    assert subject_row["total"] == "35.69"
    assert subject_row["percent"] == "71.38"
    assert subject_row["grade_label"] == "C"
    assert subject_row["is_pass"] is True
    assert subject_row["scale_id"] == scale_id
    assert subject_row["scale_version"] == 1
    assert subject_row["structure_version"] == 1
    assert subject_row["rank"] == 1
    assert subject_row["terms"] is None
    assert top["status"] == "draft"

    low = sheet["students"][2]
    assert low["total"] == "19.38"
    assert low["percent"] == "38.76"
    assert low["grade_label"] == "F"
    assert low["is_pass"] is False

    # A subject filter narrows the sheet to that subject only.
    filtered = await client.get(
        f"{BASE}/results/term",
        headers=superadmin_headers,
        params={
            "year_id": year["id"],
            "term_id": str(term.id),
            "section_id": section["id"],
            "subject_id": subject["id"],
        },
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["subject_count"] == 1


async def test_publish_snapshot_and_republish_after_scale_change(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    subject = await _subject(client, superadmin_headers, code="math-publish")
    term = await _term(app, year["id"])
    await _structure(client, superadmin_headers, year, components=[_component("quiz", "10")])
    await _scale(app)
    student = await _student(
        client,
        superadmin_headers,
        number="STU-PUBLISH-1",
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
        title="Publish quiz",
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

    payload = {
        "year_id": year["id"],
        "term_id": str(term.id),
        "section_id": section["id"],
    }
    blocked = await client.post(f"{BASE}/results/term/publish", headers=superadmin_headers, json=payload)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["message_key"] == "assessment.error.results_not_ready"

    approved = await _approve(
        client,
        superadmin_headers,
        year=year,
        term=term,
        section=section,
        subject=subject,
    )
    assert approved["status"] == "approved"

    published = await client.post(f"{BASE}/results/term/publish", headers=superadmin_headers, json=payload)
    assert published.status_code == 200, published.text
    snapshot = published.json()
    assert snapshot["kind"] == "term"
    assert snapshot["term_id"] == str(term.id)
    assert snapshot["section_id"] == section["id"]
    assert snapshot["scale_version"] == 1
    assert snapshot["structure_version"] == 1
    assert snapshot["checksum"]
    assert snapshot["supersedes_id"] is None
    assert snapshot["published_by"]
    assert snapshot["payload"]["students"][0]["percent"] == "80"
    assert snapshot["payload"]["students"][0]["grade_label"] == "A"

    async with app.state.db.session() as session:
        rows = (
            (
                await session.execute(
                    select(TermResult).where(
                        TermResult.term_id == term.id,
                        TermResult.section_id == uuid.UUID(section["id"]),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].student_id == uuid.UUID(student["id"])
        assert rows[0].status == "published"
        assert rows[0].scale_version == 1
        assert rows[0].grade_label == "A"
        assert rows[0].percent == Decimal("80")
        assert rows[0].published_at is not None

    again = await client.post(f"{BASE}/results/term/publish", headers=superadmin_headers, json=payload)
    assert again.status_code == 409
    assert again.json()["error"]["message_key"] == "assessment.error.results_already_published"

    # A scale edit bumps the version; only an explicit re-publish applies it.
    async with app.state.db.session() as session:
        scale = (
            await session.execute(select(GradeScale).where(GradeScale.is_default.is_(True)))
        ).scalar_one()
        scale.version = 2
        bands = (
            (await session.execute(select(GradeBand).where(GradeBand.scale_id == scale.id))).scalars().all()
        )
        labels = {"A": "A+", "C": "C+", "F": "F"}
        for band in bands:
            band.label = labels.get(band.label, band.label)
        await session.commit()

    before_republish = await client.get(
        f"{BASE}/results/term",
        headers=superadmin_headers,
        params={"year_id": year["id"], "term_id": str(term.id), "section_id": section["id"]},
    )
    assert before_republish.status_code == 200, before_republish.text
    assert before_republish.json()["students"][0]["grade_label"] == "A+"

    republished = await client.post(
        f"{BASE}/results/term/republish",
        headers=superadmin_headers,
        json={**payload, "note": "Scale corrected"},
    )
    assert republished.status_code == 200, republished.text
    newer = republished.json()
    assert newer["id"] != snapshot["id"]
    assert newer["supersedes_id"] == snapshot["id"]
    assert newer["scale_version"] == 2
    assert newer["note"] == "Scale corrected"
    assert newer["payload"]["students"][0]["grade_label"] == "A+"

    async with app.state.db.session() as session:
        stored = (
            (await session.execute(select(ResultSnapshot).order_by(ResultSnapshot.published_at)))
            .scalars()
            .all()
        )
        assert [row.kind for row in stored] == ["term", "term"]
        refreshed = (
            await session.execute(select(TermResult).where(TermResult.student_id == uuid.UUID(student["id"])))
        ).scalar_one()
        assert refreshed.scale_version == 2
        assert refreshed.grade_label == "A+"

    listing = await client.get(
        f"{BASE}/results/snapshots",
        headers=superadmin_headers,
        params={"year_id": year["id"], "term_id": str(term.id)},
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 2
    assert listing.json()["items"][0]["id"] == newer["id"]

    detail = await client.get(f"{BASE}/results/snapshots/{newer['id']}", headers=superadmin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["checksum"] == newer["checksum"]

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {"assessment.results.publish", "assessment.results.republish"} <= actions


async def test_year_results_combine_terms_and_publish(client, app, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    subject = await _subject(client, superadmin_headers, code="math-year")
    terms = await _terms(app, year["id"])
    assert len(terms) == 2
    await _structure(client, superadmin_headers, year, components=[_component("quiz", "10")])
    await _scale(app)
    students = [
        await _student(
            client,
            superadmin_headers,
            number=f"STU-YEAR-{index}",
            year=year,
            level=level,
            section=section,
            roll_number=str(index),
        )
        for index in (1, 2)
    ]
    term_scores = [("8", "6"), ("10", "8")]
    assessments = []
    for term, (first_mark, second_mark) in zip(terms, term_scores, strict=True):
        assessment = await _assessment(
            client,
            superadmin_headers,
            year_id=year["id"],
            term_id=str(term.id),
            section_id=section["id"],
            subject_id=subject["id"],
            component_key="quiz",
            title=f"Year quiz {term.number}",
            assessment_date="2026-10-01",
            out_of="10",
        )
        assessments.append(assessment)
        entered = await _scores(
            client,
            superadmin_headers,
            assessment["id"],
            [
                {"student_id": students[0]["id"], "raw_score": first_mark},
                {"student_id": students[1]["id"], "raw_score": second_mark},
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

    response = await client.get(
        f"{BASE}/results/year",
        headers=superadmin_headers,
        params={"year_id": year["id"], "section_id": section["id"]},
    )
    assert response.status_code == 200, response.text
    sheet = response.json()
    assert [item["number"] for item in sheet["terms"]] == [1, 2]
    assert sheet["subject_count"] == 1
    top, second = sheet["students"]
    assert top["student_number"] == "STU-YEAR-1"
    assert top["total"] == "9"
    assert top["out_of"] == "10"
    assert top["percent"] == "90"
    assert top["grade_label"] == "A"
    assert top["rank"] == 1
    assert second["total"] == "7"
    assert second["percent"] == "70"
    assert second["grade_label"] == "C"
    assert second["rank"] == 2
    subject_row = top["subjects"][0]
    assert subject_row["total"] == "9"
    assert subject_row["out_of"] == "10"
    assert subject_row["terms"] == {
        str(terms[0].id): "8",
        str(terms[1].id): "10",
    }

    payload = {"year_id": year["id"], "section_id": section["id"]}
    published = await client.post(f"{BASE}/results/year/publish", headers=superadmin_headers, json=payload)
    assert published.status_code == 200, published.text
    snapshot = published.json()
    assert snapshot["kind"] == "year"
    assert snapshot["term_id"] is None
    assert snapshot["payload"]["kind"] == "year"
    assert len(snapshot["payload"]["terms"]) == 2
    assert snapshot["payload"]["students"][0]["subjects"][0]["terms"]

    again = await client.post(f"{BASE}/results/year/publish", headers=superadmin_headers, json=payload)
    assert again.status_code == 409
    assert again.json()["error"]["message_key"] == "assessment.error.results_already_published"

    republished = await client.post(
        f"{BASE}/results/year/republish",
        headers=superadmin_headers,
        json={**payload, "note": "Reissue"},
    )
    assert republished.status_code == 200, republished.text
    assert republished.json()["supersedes_id"] == snapshot["id"]

    # A term that was never published cannot be re-published.
    never = await client.post(
        f"{BASE}/results/term/republish",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "term_id": str(terms[1].id),
            "section_id": section["id"],
        },
    )
    assert never.status_code == 409
    assert never.json()["error"]["message_key"] == "assessment.error.no_published_result"


async def test_results_respect_teacher_subject_scope(client, app, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    own_section = await _section(client, superadmin_headers, year, level, code="A")
    other_section = await _section(client, superadmin_headers, year, level, code="B")
    subject = await _subject(client, superadmin_headers, code="math-scope-results")
    term = await _term(app, year["id"])
    await _structure(client, superadmin_headers, year, components=[_component("quiz", "10")])
    await _scale(app)
    student = await _student(
        client,
        superadmin_headers,
        number="STU-SCOPE-RESULT-1",
        year=year,
        level=level,
        section=own_section,
    )
    other_student = await _student(
        client,
        superadmin_headers,
        number="STU-SCOPE-RESULT-2",
        year=year,
        level=level,
        section=other_section,
    )
    own_assessment = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=own_section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Scoped result quiz",
        assessment_date="2026-10-01",
        out_of="10",
    )
    other_assessment = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=other_section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Other result quiz",
        assessment_date="2026-10-01",
        out_of="10",
    )
    entered = await _scores(
        client,
        superadmin_headers,
        own_assessment["id"],
        [{"student_id": student["id"], "raw_score": "9"}],
    )
    assert entered.status_code == 200, entered.text
    entered = await _scores(
        client,
        superadmin_headers,
        other_assessment["id"],
        [{"student_id": other_student["id"], "raw_score": "5"}],
    )
    assert entered.status_code == 200, entered.text

    await create_role(
        app,
        "results_teacher",
        [
            ("assessment.view", "assigned_subjects"),
            ("assessment.enter_marks", "assigned_subjects"),
        ],
    )
    email = unique_email("results.teacher")
    user = await create_user(app, email, roles=["results_teacher"])
    staff = await client.post(
        STAFF,
        headers=superadmin_headers,
        json={
            "person": {
                "given_name_en": "Results Teacher",
                "father_name_en": "Bekele",
                "grandfather_name_en": "Desta",
                "sex": "female",
                "date_of_birth": "1990-02-03",
            },
            "staff_number": "STF-RESULT-1",
            "hire_date": "2026-09-01",
        },
    )
    assert staff.status_code == 201, staff.text
    linked = await client.post(
        f"{STAFF}/{staff.json()['id']}/account",
        headers=superadmin_headers,
        json={"user_id": str(user.id)},
    )
    assert linked.status_code == 200, linked.text
    assigned = await client.post(
        f"{STAFF}/{staff.json()['id']}/teaching-assignments",
        headers=superadmin_headers,
        json={
            "year_id": year["id"],
            "section_id": own_section["id"],
            "subject_id": subject["id"],
        },
    )
    assert assigned.status_code == 201, assigned.text
    headers = await login(client, email)

    own = await client.get(
        f"{BASE}/results/term",
        headers=headers,
        params={
            "year_id": year["id"],
            "term_id": str(term.id),
            "section_id": own_section["id"],
        },
    )
    assert own.status_code == 200, own.text
    sheet = own.json()
    assert sheet["subject_count"] == 1
    assert len(sheet["students"]) == 1
    assert [row["subject_id"] for row in sheet["students"][0]["subjects"]] == [subject["id"]]
    # A scoped caller never sees the class-wide rank, only the subject rank.
    assert sheet["students"][0]["rank"] is None
    assert sheet["students"][0]["subjects"][0]["rank"] == 1

    denied = await client.get(
        f"{BASE}/results/term",
        headers=headers,
        params={
            "year_id": year["id"],
            "term_id": str(term.id),
            "section_id": other_section["id"],
        },
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["message_key"] == "error.scope_denied"

    own_year = await client.get(
        f"{BASE}/results/year",
        headers=headers,
        params={"year_id": year["id"], "section_id": own_section["id"]},
    )
    assert own_year.status_code == 200, own_year.text
    assert own_year.json()["subject_count"] == 1
    assert own_year.json()["students"][0]["rank"] is None
