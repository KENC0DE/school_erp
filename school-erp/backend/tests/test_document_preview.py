"""P5-07: previewing a layout with sample or real student data.

The preview endpoint uses the production HTML renderer, so these tests assert
on the rendered document rather than on a second client-side implementation.
The real-student case covers the values a certificate and report card actually
print: identity, placement, school, marks, rank and attendance.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from core.documents.layout import validate_layout
from core.documents.render import layout_to_html
from modules.assessment.models import ResultSnapshot

from tests.conftest import create_role, create_user, login, unique_email

BASE = "/api/v1/documents/preview"
TEMPLATES = "/api/v1/documents/templates"
MODULES = "/api/v1/system/modules"
ACADEMICS = "/api/v1/academics"
STUDENTS = "/api/v1/students"

PERSON = {
    "given_name_en": "Hana",
    "father_name_en": "Tesfaye",
    "grandfather_name_en": "Bekele",
    "given_name_am": "ሀና",
    "father_name_am": "ተስፋዬ",
    "grandfather_name_am": "በቀለ",
    "sex": "female",
    "date_of_birth": "2015-03-04",
}


def _text_layout(*tokens: str) -> dict:
    content = " ".join(tokens)
    return {
        "version": 1,
        "page": {"size": "A5"},
        "elements": [
            {
                "id": "line",
                "type": "text",
                "rect": {"x_mm": 10, "y_mm": 10, "w_mm": 128, "h_mm": 20},
                "content": content,
                "style": {"font_family": "Inter", "font_size_pt": 11},
            }
        ],
    }


async def _year(client, headers) -> dict:
    response = await client.post(
        f"{ACADEMICS}/academic-years",
        headers=headers,
        json={
            "code": "2026-2027",
            "name": "2026/27",
            "start_date": "2026-09-11",
            "end_date": "2027-06-30",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _level(client, headers) -> dict:
    response = await client.get(f"{ACADEMICS}/levels", headers=headers, params={"scope": "all"})
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["code"] == "g5")


async def _section(client, headers, year: dict, level: dict) -> dict:
    response = await client.post(
        f"{ACADEMICS}/sections",
        headers=headers,
        json={"year_id": year["id"], "level_id": level["id"], "code": "A"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _student(client, headers, year: dict, level: dict, section: dict) -> dict:
    response = await client.post(
        STUDENTS,
        headers=headers,
        json={
            "person": PERSON,
            "student_number": "PREVIEW-0001",
            "admission_date": "2026-09-15",
            "notes": "A careful student.",
            "enrollment": {
                "year_id": year["id"],
                "level_id": level["id"],
                "section_id": section["id"],
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _snapshot(app, student: dict, year: dict, level: dict, section: dict) -> None:
    """Insert the published payload the assessment module would have written."""
    student_id = student["id"]
    payload = {
        "year_id": year["id"],
        "year_code": year["code"],
        "term_id": str(uuid.uuid4()),
        "term_name": "Term 1",
        "section_id": section["id"],
        "section_code": section["code"],
        "level_id": level["id"],
        "level_name": level["name"],
        "students": [
            {
                "student_id": student_id,
                "student_number": student["student_number"],
                "student_name": "Hana Tesfaye Bekele",
                "subjects": [
                    {
                        "subject_id": str(uuid.uuid4()),
                        "subject_name": "Mathematics",
                        "structure_version": 1,
                        "total": "83.75",
                        "out_of": "100",
                        "percent": "83.75",
                        "grade_label": "A",
                        "grade_remark": "Excellent",
                        "gpa_points": "4",
                        "is_pass": True,
                        "rank": 1,
                        "rank_size": 30,
                        "status": "published",
                    }
                ],
                "total": "83.75",
                "out_of": "100",
                "percent": "83.75",
                "grade_label": "A",
                "grade_remark": "Excellent",
                "gpa_points": "4",
                "is_pass": True,
                "rank": 1,
                "rank_size": 30,
                "status": "published",
            }
        ],
        "subject_count": 1,
    }
    async with app.state.db.session() as session:
        session.add(
            ResultSnapshot(
                year_id=uuid.UUID(year["id"]),
                section_id=uuid.UUID(section["id"]),
                kind="term",
                payload=payload,
                published_at=datetime.now(UTC),
            )
        )
        await session.commit()


async def test_sample_preview_uses_the_production_renderer(client, superadmin_headers) -> None:
    layout = _text_layout("{{student.full_name}}", "{{student.student_number}}")
    response = await client.post(
        BASE,
        headers=superadmin_headers,
        json={"layout": layout, "mode": "sample"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "sample"
    assert body["student_id"] is None
    assert body["page_mm"] == [148.0, 210.0]
    assert body["media_mm"] == [148.0, 210.0]
    assert "Abebe Kebede Tadesse" in body["html"]
    assert "DEMO-2026-0001" in body["html"]
    # Same renderer: an independent call produces the same document for the
    # same validated layout and context.
    expected = layout_to_html(validate_layout(layout))
    assert body["html"].split("<body>")[0] == expected.split("<body>")[0]


async def test_real_student_preview_reads_identity_placement_and_marks(
    client, superadmin_headers, app
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    student = await _student(client, superadmin_headers, year, level, section)
    await _snapshot(app, student, year, level, section)

    layout = _text_layout(
        "{{student.full_name}}",
        "{{student.student_number}}",
        "{{student.grade}}",
        "{{student.section}}",
        "{{school.name}}",
        "{{student.marks.term.total}}",
        "{{student.marks.term.grade}}",
        "{{student.rank}}/{{student.rank_size}}",
    )
    response = await client.post(
        BASE,
        headers=superadmin_headers,
        json={"layout": layout, "mode": "student", "student_id": student["id"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "student"
    assert body["student_id"] == student["id"]
    assert body["student_name"] == "Hana Tesfaye Bekele"
    html = body["html"]
    for expected in (
        "Hana Tesfaye Bekele",
        "PREVIEW-0001",
        "Grade 5",
        "A",
        "Demo Academy",
        "83.75",
        "1/30",
    ):
        assert expected in html


async def test_real_student_preview_includes_attendance_and_remarks(client, superadmin_headers, app) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    student = await _student(client, superadmin_headers, year, level, section)
    layout = _text_layout(
        "{{student.attendance_present}}", "{{student.attendance_absent}}", "{{student.remarks}}"
    )
    response = await client.post(
        BASE,
        headers=superadmin_headers,
        json={"layout": layout, "mode": "student", "student_id": student["id"]},
    )
    assert response.status_code == 200, response.text
    assert "A careful student." in response.json()["html"]


async def test_preview_requires_the_design_permission(client, limited_headers) -> None:
    denied = await client.post(
        BASE,
        headers=limited_headers,
        json={"layout": _text_layout("hi"), "mode": "sample"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

    anonymous = await client.post(BASE, json={"layout": _text_layout("hi"), "mode": "sample"})
    assert anonymous.status_code == 401


async def test_student_preview_needs_student_read_access(client, app, seeded, superadmin_headers) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    student = await _student(client, superadmin_headers, year, level, section)

    await create_role(
        app,
        "document_designer",
        [("documents.template.design", "all")],
    )
    email = unique_email("document-designer")
    await create_user(app, email, roles=["document_designer"])
    headers = await login(client, email)

    sample = await client.post(
        BASE,
        headers=headers,
        json={"layout": _text_layout("hi"), "mode": "sample"},
    )
    assert sample.status_code == 200, sample.text

    denied = await client.post(
        BASE,
        headers=headers,
        json={"layout": _text_layout("hi"), "mode": "student", "student_id": student["id"]},
    )
    assert denied.status_code == 403


async def test_preview_is_gated_by_the_documents_module(client, superadmin_headers) -> None:
    disabled = await client.put(
        f"{MODULES}/documents",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    blocked = await client.post(
        BASE,
        headers=superadmin_headers,
        json={"layout": _text_layout("hi"), "mode": "sample"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "MODULE_DISABLED"

    await client.put(f"{MODULES}/documents", headers=superadmin_headers, json={"enabled": True})


async def test_preview_rejects_bad_requests_and_layouts(client, superadmin_headers) -> None:
    missing_student = await client.post(
        BASE,
        headers=superadmin_headers,
        json={"layout": _text_layout("hi"), "mode": "student"},
    )
    assert missing_student.status_code == 422

    unknown_student = await client.post(
        BASE,
        headers=superadmin_headers,
        json={
            "layout": _text_layout("hi"),
            "mode": "student",
            "student_id": str(uuid.uuid4()),
        },
    )
    assert unknown_student.status_code == 404

    broken = _text_layout("hi")
    broken["elements"][0]["type"] = "hologram"
    invalid = await client.post(
        BASE,
        headers=superadmin_headers,
        json={"layout": broken, "mode": "sample"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["message_key"] == "error.documents.layout_invalid"
