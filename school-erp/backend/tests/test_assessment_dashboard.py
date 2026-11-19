"""P4-14: manager dashboard — completion, overdue list, anomalies and reminders."""

from __future__ import annotations

from modules.academics.models import Term

from tests.test_assessment_scores import (
    _assessment,
    _scores,
    _student,
    _teacher,
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
NOTIFICATIONS = "/api/v1/notifications"
ACTIVITY = "/api/v1/audit/activity"


def _payload(year: dict, term: Term, section: dict, subject: dict, title: str, date: str) -> dict:
    return {
        "year_id": year["id"],
        "term_id": str(term.id),
        "section_id": section["id"],
        "subject_id": subject["id"],
        "component_key": "quiz",
        "title": title,
        "assessment_date": date,
        "out_of": "10",
    }


async def _closed_window(client, headers, year: dict, term: Term, section: dict) -> dict:
    """A marking window that closed before today, so the class is overdue."""
    response = await client.post(
        f"{BASE}/windows",
        headers=headers,
        json={
            "year_id": year["id"],
            "term_id": str(term.id),
            "section_id": section["id"],
            "opens_at": "2026-09-01T00:00:00Z",
            "closes_at": "2026-10-01T00:00:00Z",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _activity(client, headers) -> list[dict]:
    response = await client.get(ACTIVITY, headers=headers, params={"limit": 200})
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def test_dashboard_reports_completion_overdue_and_anomalies(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    subject = await _subject(client, superadmin_headers, code="math-dash")
    term = await _term(app, year["id"])
    await _structure(client, superadmin_headers, year, components=[_component("quiz", "10")])
    students = [
        await _student(
            client,
            superadmin_headers,
            number=f"STU-DASH-{index}",
            year=year,
            level=level,
            section=section,
            roll_number=str(index),
        )
        for index in range(1, 6)
    ]
    first = await _assessment(
        client, superadmin_headers, **_payload(year, term, section, subject, "Quiz 1", "2026-10-01")
    )
    second = await _assessment(
        client, superadmin_headers, **_payload(year, term, section, subject, "Quiz 2", "2026-10-08")
    )
    third = await _assessment(
        client, superadmin_headers, **_payload(year, term, section, subject, "Quiz 3", "2026-10-15")
    )
    fourth = await _assessment(
        client, superadmin_headers, **_payload(year, term, section, subject, "Quiz 4", "2026-10-22")
    )

    async def enter(assessment: dict, values: list[str]) -> None:
        response = await _scores(
            client,
            superadmin_headers,
            assessment["id"],
            [
                {"student_id": student["id"], "raw_score": value, "status": "present"}
                for student, value in zip(students, values, strict=False)
            ],
        )
        assert response.status_code == 200, response.text

    # Quiz 1: every mark identical (a possible copy).
    await enter(first, ["5", "5", "5", "5", "5"])
    # Quiz 2 and 3: ordinary variation around the same average.
    await enter(second, ["4", "5", "5", "5", "6"])
    await enter(third, ["5", "6", "6", "6", "7"])
    # Quiz 4: only two marks entered, both far below the norm.
    await enter(fourth, ["1", "1"])

    # The window is created last because score entry refuses a closed window.
    await _closed_window(client, superadmin_headers, year, term, section)

    response = await client.get(
        f"{BASE}/dashboard",
        headers=superadmin_headers,
        params={"year_id": year["id"], "term_id": str(term.id)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["year_id"] == year["id"]
    assert body["term_id"] == str(term.id)
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["section_code"] == "A"
    assert row["level_name"] == "Grade 5"
    assert row["subject_name"] == "Mathematics"
    assert row["assessments"] == 4
    assert row["students"] == 5
    assert row["expected"] == 20
    assert row["entered"] == 17
    assert row["missing"] == 3
    assert row["completion_percent"] == "85"
    assert row["status"] == "missing"
    assert row["window_state"] == "closed"
    assert row["overdue"] is True
    assert row["deadline"].startswith("2026-10-01")
    assert row["teachers"] == []

    summary = body["summary"]
    assert summary == {
        "sections": 1,
        "assessments": 4,
        "expected": 20,
        "entered": 17,
        "completion_percent": "85",
        "overdue": 1,
        "anomalies": 2,
    }

    anomalies = {item["kind"]: item for item in body["anomalies"]}
    # Quiz 1 flags five identical marks; it is a warning, never a block.
    identical = anomalies["identical"]
    assert identical["title"] == "Quiz 1"
    assert identical["count"] == 5
    assert identical["value"] == "5"
    assert identical["section_code"] == "A"
    # Quiz 4 sits far below the section and subject norm.
    outlier = anomalies["average_outlier"]
    assert outlier["title"] == "Quiz 4"
    assert outlier["count"] == 2
    assert outlier["average_percent"] == "10"
    assert outlier["norm_percent"] == "53.33"
    assert outlier["threshold"] == "25"

    # The dashboard is a read: no reminder and no audit entry from a read.
    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert "assessment.dashboard.remind" not in actions

    # Filters narrow the row set without changing the underlying counts.
    filtered = await client.get(
        f"{BASE}/dashboard",
        headers=superadmin_headers,
        params={
            "year_id": year["id"],
            "term_id": str(term.id),
            "section_id": section["id"],
            "subject_id": subject["id"],
        },
    )
    assert filtered.status_code == 200, filtered.text
    assert len(filtered.json()["rows"]) == 1

    # Another year's term is rejected instead of silently returning nothing.
    other_year = await _year(client, superadmin_headers, code="2027-2028")
    other_term = await _term(app, other_year["id"])
    mismatch = await client.get(
        f"{BASE}/dashboard",
        headers=superadmin_headers,
        params={"year_id": year["id"], "term_id": str(other_term.id)},
    )
    assert mismatch.status_code == 422, mismatch.text
    assert mismatch.json()["error"]["message_key"] == "assessment.error.term_year"


async def test_dashboard_limits_a_teacher_to_their_own_classes(
    client, app, superadmin_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    mine = await _section(client, superadmin_headers, year, level, code="A")
    other = await _section(client, superadmin_headers, year, level, code="B")
    subject = await _subject(client, superadmin_headers, code="math-scope")
    term = await _term(app, year["id"])
    await _structure(client, superadmin_headers, year, components=[_component("quiz", "10")])
    teacher = await _teacher(client, app, superadmin_headers, year=year, section=mine, subject=subject)
    await _assessment(
        client, superadmin_headers, **_payload(year, term, mine, subject, "My quiz", "2026-10-01")
    )
    await _assessment(
        client, superadmin_headers, **_payload(year, term, other, subject, "Other quiz", "2026-10-02")
    )

    response = await client.get(
        f"{BASE}/dashboard",
        headers=teacher["headers"],
        params={"year_id": year["id"], "term_id": str(term.id)},
    )
    assert response.status_code == 200, response.text
    rows = response.json()["rows"]
    assert [row["section_code"] for row in rows] == ["A"]
    assert rows[0]["assessments"] == 1
    # The teacher is named on the row so a manager knows who to chase.
    names = [item["name"] for item in rows[0]["teachers"]]
    assert names == ["Marks Teacher Bekele Desta"]


async def test_dashboard_reminders_notify_linked_teachers_and_are_audited(
    client, app, superadmin_headers, limited_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    subject = await _subject(client, superadmin_headers, code="math-remind")
    term = await _term(app, year["id"])
    await _structure(client, superadmin_headers, year, components=[_component("quiz", "10")])
    await _student(
        client,
        superadmin_headers,
        number="STU-REMIND-1",
        year=year,
        level=level,
        section=section,
    )
    await _assessment(
        client,
        superadmin_headers,
        **_payload(year, term, section, subject, "Reminder quiz", "2026-10-01"),
    )
    teacher = await _teacher(client, app, superadmin_headers, year=year, section=section, subject=subject)
    # A second teacher teaches the same class but has no user account yet.
    unlinked = await client.post(
        STAFF,
        headers=superadmin_headers,
        json={
            "person": {
                "given_name_en": "No Account",
                "father_name_en": "Bekele",
                "grandfather_name_en": "Desta",
                "sex": "male",
                "date_of_birth": "1991-04-05",
            },
            "staff_number": "STF-REMIND-2",
            "hire_date": "2026-09-01",
        },
    )
    assert unlinked.status_code == 201, unlinked.text
    assigned = await client.post(
        f"{STAFF}/{unlinked.json()['id']}/teaching-assignments",
        headers=superadmin_headers,
        json={"year_id": year["id"], "section_id": section["id"], "subject_id": subject["id"]},
    )
    assert assigned.status_code == 201, assigned.text
    await _closed_window(client, superadmin_headers, year, term, section)

    # A role without assessment.manage may read but not chase teachers.
    denied = await client.post(
        f"{BASE}/dashboard/remind",
        headers=limited_headers,
        json={"year_id": year["id"], "term_id": str(term.id)},
    )
    assert denied.status_code == 403, denied.text

    sent = await client.post(
        f"{BASE}/dashboard/remind",
        headers=superadmin_headers,
        json={"year_id": year["id"], "term_id": str(term.id)},
    )
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["rows"] == 1
    assert body["sent"] == 1
    assert body["skipped"] == 1
    assert len(body["recipients"]) == 1
    assert body["recipients"][0]["name"] == "Marks Teacher Bekele Desta"
    assert body["recipients"][0]["section_id"] == section["id"]
    assert body["recipients"][0]["subject_id"] == subject["id"]

    inbox = await client.get(NOTIFICATIONS, headers=teacher["headers"])
    assert inbox.status_code == 200, inbox.text
    items = inbox.json()["items"]
    assert len(items) == 1
    notification = items[0]
    assert notification["template_key"] == "assessment.entry_reminder"
    assert notification["title"] == "Marks are overdue"
    assert "Grade 5 A" in notification["body"]
    assert "Mathematics" in notification["body"]
    assert "0 of 1" in notification["body"]
    assert notification["link"] == "/assessment"
    assert notification["params"]["completion"] == "0"

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert "assessment.dashboard.remind" in actions


async def test_dashboard_requires_the_assessment_permission(
    client, app, superadmin_headers, limited_headers, seeded
) -> None:
    await _enable(client, superadmin_headers)
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers, "g5")
    section = await _section(client, superadmin_headers, year, level)
    term = await _term(app, year["id"])

    denied = await client.get(
        f"{BASE}/dashboard",
        headers=limited_headers,
        params={"year_id": year["id"], "term_id": str(term.id), "section_id": section["id"]},
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["error"]["message_key"] == "error.permission_denied"
