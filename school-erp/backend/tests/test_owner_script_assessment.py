"""Phase 4 checkpoint: the owner script, run end-to-end over the API.

The guide's checkpoint asks the owner to act as three people against a fresh
seed: the academic head defines components and grade bands, a teacher enters a
mark out of 15 and one out of 13 and watches the converted values, marks are
submitted, approved, published and locked, a band change relabels results
without touching raw marks, the teacher requests a correction, and a parent
sees only published results.

This test performs that whole script with three real signed-in accounts, so a
regression in scope, workflow or the published-only rule fails here rather than
in a manual walk-through.
"""

from __future__ import annotations

from decimal import Decimal

from core.rbac.defaults import DEFAULT_ROLES

from tests.conftest import create_role, create_user, login
from tests.test_assessment_portal import _parent_headers
from tests.test_assessment_scales import _band, _scale
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
from tests.test_assessment_workflow import _correction, _move, _submission

BASE = "/api/v1/assessment"
STAFF = "/api/v1/staff"

STRUCTURE_COMPONENTS = [
    _component("quizzes", "10", sort_order=0),
    _component("assignments", "20", sort_order=1),
    _component("midterm", "30", sort_order=2),
    _component("final", "40", sort_order=3),
]

# A year's worth of assessments for two students. The first two cover the
# guide's out-of-15 and out-of-13 examples and would convert to 8.0/10 and
# 6.92/10 on their own.
ASSESSMENT_PLAN = (
    ("Quiz 1", "quizzes", "15", "2026-10-05"),
    ("Quiz 2", "quizzes", "13", "2026-11-09"),
    ("Assignment 1", "assignments", "20", "2026-10-20"),
    ("Midterm exam", "midterm", "30", "2026-11-25"),
    ("Final exam", "final", "40", "2027-01-15"),
)
MARKS = {
    "STU-OWNER-1": ("12", "10", "16", "24", "32"),
    "STU-OWNER-2": ("14", "13", "18", "27", "36"),
}


def _default_role_pairs(key: str) -> list[tuple[str, str]]:
    """The shipped permission set for a role, as ``(code, scope)`` pairs."""
    role = next(item for item in DEFAULT_ROLES if item.key == key)
    return [*((permission, "all") for permission in role.permissions), *role.scoped.items()]


async def _staff_teacher(client, app, headers, *, email: str, year: dict, section: dict, subject: dict):
    """Create a teacher user with a staff profile and one teaching assignment."""
    await create_role(app, "teacher", _default_role_pairs("teacher"), system=True)
    user = await create_user(app, email, roles=["teacher"])
    staff = await client.post(
        STAFF,
        headers=headers,
        json={
            "person": {
                "given_name_en": "Teacher",
                "father_name_en": "One",
                "grandfather_name_en": "Demo",
                "sex": "male",
                "date_of_birth": "1990-02-03",
            },
            "staff_number": "STF-OWNER-1",
            "hire_date": "2026-09-01",
        },
    )
    assert staff.status_code == 201, staff.text
    staff_id = staff.json()["id"]
    linked = await client.post(f"{STAFF}/{staff_id}/account", headers=headers, json={"user_id": str(user.id)})
    assert linked.status_code == 200, linked.text
    assigned = await client.post(
        f"{STAFF}/{staff_id}/teaching-assignments",
        headers=headers,
        json={"year_id": year["id"], "section_id": section["id"], "subject_id": subject["id"]},
    )
    assert assigned.status_code == 201, assigned.text
    return {"user": user, "email": email}


def _sheet_item(sheet: dict, student_id: str) -> dict:
    return next(item for item in sheet["items"] if item["student_id"] == student_id)


def _result_row(sheet: dict, student_number: str) -> dict:
    return next(row for row in sheet["students"] if row["student_number"] == student_number)


async def test_owner_script_academic_head_teacher_and_parent(client, app, superadmin_headers, seeded) -> None:
    # The academic head defines the structure and the grade bands.
    await _enable(client, superadmin_headers)
    await create_role(app, "academic_head", _default_role_pairs("academic_head"), system=True)
    await create_user(app, "owner.academic@demo.school", roles=["academic_head"])
    academic = await login(client, "owner.academic@demo.school")

    year = await _year(client, academic)
    level = await _level(client, academic, "g5")
    section = await _section(client, academic, year, level, code="A")
    subject = await _subject(client, academic, code="math-owner")
    term = await _term(app, year["id"])

    structure = await _structure(
        client, academic, year, components=STRUCTURE_COMPONENTS, name="School mark structure"
    )
    assert structure["total"] == "100"
    assert [component["key"] for component in structure["components"]] == [
        "quizzes",
        "assignments",
        "midterm",
        "final",
    ]

    scale = await _scale(client, academic, name="School grading scale", is_default=True)
    assert [band["label"] for band in scale["bands"]] == ["F", "C", "C+", "A"]
    assert scale["bands"][2]["min_value"] == "75"
    assert scale["bands"][2]["max_value"] == "85"
    assigned = await client.post(
        f"{BASE}/scale-assignments",
        headers=academic,
        json={"scale_id": scale["id"], "context": "default"},
    )
    assert assigned.status_code == 201, assigned.text

    # The test tool shows the C+ band exactly as the guide describes it.
    boundary = await client.post(f"{BASE}/scales/{scale['id']}/test", headers=academic, json={"value": "80"})
    assert boundary.status_code == 200, boundary.text
    assert boundary.json()["label"] == "C+"

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
        for index, number in enumerate(MARKS)
    ]

    # A teacher enters the marks for their own section and subject.
    teacher_email = "owner.teacher@demo.school"
    await _staff_teacher(
        client, app, superadmin_headers, email=teacher_email, year=year, section=section, subject=subject
    )
    teacher = await login(client, teacher_email)

    assessments: dict[str, dict] = {}
    for title, component_key, out_of, on_date in ASSESSMENT_PLAN:
        assessments[title] = await _assessment(
            client,
            teacher,
            year_id=year["id"],
            term_id=str(term.id),
            section_id=section["id"],
            subject_id=subject["id"],
            component_key=component_key,
            title=title,
            assessment_date=on_date,
            out_of=out_of,
        )

    for index, (title, _component_key, _out_of, _date) in enumerate(ASSESSMENT_PLAN):
        items = [
            {
                "student_id": student["id"],
                "raw_score": MARKS[student["student_number"]][index],
            }
            for student in students
        ]
        response = await _scores(client, teacher, assessments[title]["id"], items)
        assert response.status_code == 200, response.text

    # The converted value follows the structure, not the raw maximum.
    quiz_one = await client.get(f"{BASE}/assessments/{assessments['Quiz 1']['id']}/scores", headers=teacher)
    assert quiz_one.status_code == 200, quiz_one.text
    converted_15 = _sheet_item(quiz_one.json(), students[0]["id"])
    assert converted_15["raw_score"] == "12"
    assert converted_15["converted"] == "8"
    quiz_two = await client.get(f"{BASE}/assessments/{assessments['Quiz 2']['id']}/scores", headers=teacher)
    converted_13 = _sheet_item(quiz_two.json(), students[0]["id"])
    assert converted_13["raw_score"] == "10"
    assert converted_13["converted"] == "7.69"

    # Before publishing, a parent's portal is empty.
    await create_role(app, "parent", _default_role_pairs("parent"), system=True)
    parent = await _parent_headers(app, client, [student["id"] for student in students])
    before = await client.get(f"{BASE}/portal/results", headers=parent)
    assert before.status_code == 200, before.text
    assert [result for child in before.json()["children"] for result in child["results"]] == []

    # Submit, approve, publish the marks, publish the term sheet, then lock.
    submission = await _submission(
        client,
        teacher,
        year_id=year["id"],
        term_id=str(term.id),
        section_id=section["id"],
        subject_id=subject["id"],
    )
    for action, headers in (
        ("submit", teacher),
        ("approve", academic),
        ("publish", academic),
        ("lock", academic),
    ):
        moved = await _move(client, headers, submission["id"], action)
        assert moved.status_code == 200, (action, moved.text)

    snapshot = await client.post(
        f"{BASE}/results/term/publish",
        headers=academic,
        json={"year_id": year["id"], "term_id": str(term.id), "section_id": section["id"]},
    )
    assert snapshot.status_code == 200, snapshot.text
    published = snapshot.json()
    published_label = _result_row(published["payload"], "STU-OWNER-1")["grade_label"]
    assert published_label == "C+"

    # The parent now sees both children, and only published data travels.
    after = await client.get(f"{BASE}/portal/results", headers=parent)
    assert after.status_code == 200, after.text
    children = after.json()["children"]
    assert {child["student_number"] for child in children} == set(MARKS)
    for child in children:
        assert len(child["results"]) == 1
        assert child["results"][0]["result"]["grade_label"] is not None
    assert "raw_score" not in after.text

    # Changing a band relabels live results but leaves raw marks alone.
    updated = await client.patch(
        f"{BASE}/scales/{scale['id']}",
        headers=academic,
        json={
            "row_version": scale["row_version"],
            "bands": [_band("0", "50", "F"), _band("50", "100", "A")],
            "reason": "The owner widened the top band",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2

    live = await client.get(
        f"{BASE}/results/term",
        headers=academic,
        params={
            "year_id": year["id"],
            "term_id": str(term.id),
            "section_id": section["id"],
        },
    )
    assert live.status_code == 200, live.text
    assert _result_row(live.json(), "STU-OWNER-1")["grade_label"] == "A"

    untouched = await client.get(f"{BASE}/assessments/{assessments['Quiz 1']['id']}/scores", headers=teacher)
    assert _sheet_item(untouched.json(), students[0]["id"])["raw_score"] == "12"
    assert _sheet_item(untouched.json(), students[0]["id"])["converted"] == "8"

    # The published snapshot keeps the labels it was published with.
    stored = await client.get(f"{BASE}/results/snapshots/{published['id']}", headers=academic)
    assert stored.status_code == 200, stored.text
    assert _result_row(stored.json()["payload"], "STU-OWNER-1")["grade_label"] == published_label

    # After the lock the teacher can request a correction.
    score_id = converted_15["score_id"]
    correction = await _correction(
        client,
        teacher,
        score_id=score_id,
        new_raw="13",
        reason="The second page of the quiz was marked late",
    )
    assert correction.status_code == 201, correction.text
    assert correction.json()["status"] == "pending"
    assert Decimal(correction.json()["new_raw"]) == Decimal("13")
