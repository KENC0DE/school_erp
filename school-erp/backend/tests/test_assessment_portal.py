"""P4-16: parent and student read views of published results only.

The portal endpoint resolves a user account to its own student profile (student
portal) or to every linked child (parent portal), and reads only immutable
publish snapshots. These tests prove the published-only rule, the family scope,
that raw marks and workflow rows never travel, and that a later live edit does
not rewrite what a parent already saw.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

from core.people.models import Person
from modules.assessment.models import GradeBand, GradeScale, ScaleAssignment
from modules.students.models import StudentGuardian, StudentProfile
from sqlalchemy import select

from tests.conftest import create_user, login, unique_email
from tests.test_assessment_scores import (
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
PORTAL = f"{BASE}/portal/results"

BANDS = [
    ("0", "50", "F", False, "0"),
    ("50", "75", "C", True, "2"),
    ("75", "100", "A", True, "4"),
]


async def _scale(app) -> str:
    async with app.state.db.session() as session:
        scale = GradeScale(
            name="Portal scale",
            type="numeric_bands",
            is_default=True,
            version=1,
        )
        session.add(scale)
        await session.flush()
        for index, (low, high, label, is_pass, gpa) in enumerate(BANDS):
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
        session.add(ScaleAssignment(scale_id=scale.id, context="default", scope_key="default"))
        await session.commit()
        return str(scale.id)


async def _publish(
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
    published = await client.post(
        f"{BASE}/results/term/publish",
        headers=headers,
        json={
            "year_id": year["id"],
            "term_id": str(term.id),
            "section_id": section["id"],
        },
    )
    assert published.status_code == 200, published.text
    return published.json()


async def _parent_headers(app, client, student_ids: list[str]) -> dict[str, str]:
    email = unique_email("portal-parent")
    user = await create_user(app, email, roles=["parent"])
    async with app.state.db.session() as session:
        person = Person(
            given_name_en="Portal",
            father_name_en="Parent",
            grandfather_name_en="Demo",
            search_name="portal parent demo",
        )
        session.add(person)
        await session.flush()
        for student_id in student_ids:
            session.add(
                StudentGuardian(
                    student_id=uuid.UUID(student_id),
                    person_id=person.id,
                    relationship="father",
                    is_primary=True,
                    user_id=user.id,
                )
            )
        await session.commit()
    return await login(client, email)


async def _student_headers(app, client, student_id: str) -> dict[str, str]:
    email = unique_email("portal-student")
    user = await create_user(app, email, roles=["student"])
    async with app.state.db.session() as session:
        profile = await session.get(StudentProfile, uuid.UUID(student_id))
        assert profile is not None
        profile.user_id = user.id
        await session.commit()
    return await login(client, email)


async def _class(
    client,
    app,
    superadmin_headers,
    *,
    section_code: str,
    subject_code: str,
    numbers: list[str],
):
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level, code=section_code)
    subject = await _subject(client, superadmin_headers, code=subject_code)
    term = await _term(app, year["id"])
    await _structure(client, superadmin_headers, year, components=[_component("quiz", "10")])
    students = [
        await _student(
            client,
            superadmin_headers,
            number=number,
            year=year,
            level=level,
            section=section,
            roll_number=str(index + 1),
        )
        for index, number in enumerate(numbers)
    ]
    return year, level, section, subject, term, students


async def test_parent_sees_published_results_for_both_children_only(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    await _scale(app)
    year, level, section, subject, term, students = await _class(
        client,
        app,
        superadmin_headers,
        section_code="A",
        subject_code="math-portal-a",
        numbers=["STU-PORTAL-1", "STU-PORTAL-2"],
    )
    other_section = await _section(client, superadmin_headers, year, level, code="B")
    other_subject = await _subject(client, superadmin_headers, code="math-portal-b")
    other = await _student(
        client,
        superadmin_headers,
        number="STU-PORTAL-OTHER",
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
        title="Portal quiz",
        assessment_date="2026-10-01",
        out_of="10",
    )
    other_assessment = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=other_section["id"],
        subject_id=other_subject["id"],
        component_key="quiz",
        title="Other quiz",
        assessment_date="2026-10-02",
        out_of="10",
    )
    entered = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [
            {"student_id": students[0]["id"], "raw_score": "8"},
            {"student_id": students[1]["id"], "raw_score": "6"},
        ],
    )
    assert entered.status_code == 200, entered.text
    entered = await _scores(
        client,
        superadmin_headers,
        other_assessment["id"],
        [{"student_id": other["id"], "raw_score": "9"}],
    )
    assert entered.status_code == 200, entered.text

    headers = await _parent_headers(app, client, [students[0]["id"], students[1]["id"]])

    # Approved but unpublished marks do not leave the API.
    before = await client.get(PORTAL, headers=headers)
    assert before.status_code == 200, before.text
    assert before.json() == {"children": []}

    await _publish(
        client,
        superadmin_headers,
        year=year,
        term=term,
        section=section,
        subject=subject,
    )
    await _publish(
        client,
        superadmin_headers,
        year=year,
        term=term,
        section=other_section,
        subject=other_subject,
    )

    response = await client.get(PORTAL, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert [child["student_number"] for child in body["children"]] == [
        "STU-PORTAL-1",
        "STU-PORTAL-2",
    ]
    # Another family's child is published but never visible.
    assert "STU-PORTAL-OTHER" not in json.dumps(body)

    first, second = body["children"]
    assert first["student_name"]
    assert len(first["results"]) == 1
    result = first["results"][0]
    assert result["kind"] == "term"
    assert result["year_code"] == year["code"]
    assert result["term_id"] == str(term.id)
    assert result["term_name"] == term.name
    assert result["section_code"] == "A"
    assert result["level_name"] == "Grade 5"
    assert result["result"]["status"] == "published"
    assert result["result"]["total"] == "8"
    assert result["result"]["out_of"] == "10"
    assert result["result"]["percent"] == "80"
    assert result["result"]["grade_label"] == "A"
    assert result["result"]["is_pass"] is True
    assert result["result"]["subjects"][0]["subject_name"] == "Mathematics"
    assert result["result"]["rank"] == 1
    assert result["result"]["rank_size"] == 2
    assert second["results"][0]["result"]["percent"] == "60"
    assert second["results"][0]["result"]["grade_label"] == "C"

    # Raw marks, revision rows and workflow flags never travel.
    dump = json.dumps(body)
    assert "raw_score" not in dump
    assert "converted" not in dump
    assert "submitted_at" not in dump

    # Filtering by another year empties the view without raising.
    filtered = await client.get(PORTAL, headers=headers, params={"year_id": str(uuid.uuid4())})
    assert filtered.status_code == 200, filtered.text
    assert filtered.json() == {"children": []}


async def test_student_sees_only_their_own_published_result(client, app, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    await _scale(app)
    year, _, section, subject, term, students = await _class(
        client,
        app,
        superadmin_headers,
        section_code="A",
        subject_code="math-portal-self",
        numbers=["STU-PORTAL-SELF-1", "STU-PORTAL-SELF-2"],
    )
    assessment = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Self quiz",
        assessment_date="2026-10-01",
        out_of="10",
    )
    entered = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [
            {"student_id": students[0]["id"], "raw_score": "9"},
            {"student_id": students[1]["id"], "raw_score": "4"},
        ],
    )
    assert entered.status_code == 200, entered.text
    headers = await _student_headers(app, client, students[1]["id"])

    # Unpublished class results stay invisible even though the student is linked.
    before = await client.get(PORTAL, headers=headers)
    assert before.status_code == 200, before.text
    assert before.json() == {"children": []}

    await _publish(
        client,
        superadmin_headers,
        year=year,
        term=term,
        section=section,
        subject=subject,
    )

    response = await client.get(PORTAL, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["children"]) == 1
    child = body["children"][0]
    assert child["student_number"] == "STU-PORTAL-SELF-2"
    assert len(child["results"]) == 1
    assert child["results"][0]["result"]["percent"] == "40"
    assert "STU-PORTAL-SELF-1" not in json.dumps(body)


async def test_live_edits_after_publishing_do_not_rewrite_the_portal(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    await _scale(app)
    year, _, section, subject, term, students = await _class(
        client,
        app,
        superadmin_headers,
        section_code="A",
        subject_code="math-portal-freeze",
        numbers=["STU-PORTAL-FREEZE-1"],
    )
    assessment = await _assessment(
        client,
        superadmin_headers,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=section["id"],
        subject_id=subject["id"],
        component_key="quiz",
        title="Freeze quiz",
        assessment_date="2026-10-01",
        out_of="10",
    )
    entered = await _scores(
        client,
        superadmin_headers,
        assessment["id"],
        [{"student_id": students[0]["id"], "raw_score": "7"}],
    )
    assert entered.status_code == 200, entered.text
    headers = await _parent_headers(app, client, [students[0]["id"]])
    await _publish(
        client,
        superadmin_headers,
        year=year,
        term=term,
        section=section,
        subject=subject,
    )

    # Change the stored raw mark and the scale after publishing. The live sheet
    # would move, but the portal keeps the snapshot the parent already saw.
    async with app.state.db.session() as session:
        from modules.assessment.models import Score

        score = (
            await session.execute(
                select(Score).where(
                    Score.assessment_id == uuid.UUID(assessment["id"]),
                    Score.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        score.raw_score = Decimal("1")
        scale = (
            await session.execute(select(GradeScale).where(GradeScale.is_default.is_(True)))
        ).scalar_one()
        scale.version = 2
        await session.commit()

    response = await client.get(PORTAL, headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()["children"][0]["results"][0]
    assert result["result"]["percent"] == "70"
    assert result["result"]["grade_label"] == "C"


async def test_portal_requires_the_assessment_permission(
    client, app, superadmin_headers, limited_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    denied = await client.get(PORTAL, headers=limited_headers)
    assert denied.status_code == 403, denied.text
    assert denied.json()["error"]["message_key"] == "error.permission_denied"


async def test_an_unlinked_account_sees_nothing(client, app, superadmin_headers, seeded) -> None:
    await _enable(client, superadmin_headers)
    email = unique_email("portal-unlinked")
    await create_user(app, email, roles=["parent"])
    headers = await login(client, email)
    response = await client.get(PORTAL, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"children": []}
