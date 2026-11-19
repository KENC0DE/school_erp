"""P5-08: single and bulk generation, snapshots, numbering and reprints.

Generation is deliberately two-phase: the request authorises and records a
batch, a worker renders it. These tests drive both halves. The heavy renderer is
replaced with a tiny valid PDF in most cases so the assertions stay about the
batch, the numbering, the stored artifact and the snapshot; one test uses the
real renderer when Chromium is installed.

The critical promise is pinned by ``test_reprint_serves_the_original...``: once
issued, a document never changes, even when the student is renamed afterwards.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import date

import pytest
from core.documents.chromium import RenderError, find_chromium
from core.documents.render import RenderResult
from core.people.models import Person, build_search_name
from modules.documents.models import DocumentBatch
from modules.students.models import StudentEnrollment, StudentProfile
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from tests.conftest import create_role, create_user, login, unique_email

GENERATION = "/api/v1/documents/generation"
ISSUED = "/api/v1/documents/issued"
TEMPLATES = "/api/v1/documents/templates"
MODULES = "/api/v1/system/modules"
ACADEMICS = "/api/v1/academics"
STUDENTS = "/api/v1/students"
JOBS = "/api/v1/jobs"

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


def _layout(*tokens: str) -> dict:
    return {
        "version": 1,
        "page": {"size": "A5"},
        "elements": [
            {
                "id": "line",
                "type": "text",
                "rect": {"x_mm": 10, "y_mm": 10, "w_mm": 128, "h_mm": 30},
                "content": " ".join(tokens),
                "style": {"font_family": "Inter", "font_size_pt": 11},
            }
        ],
    }


def _pdf(text: str = "document") -> bytes:
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer)
    page.drawString(72, 720, text)
    page.showPage()
    page.save()
    return buffer.getvalue()


def _fake_render(layout, context=None, **kwargs):  # type: ignore[no-untyped-def]
    data = (context.data if context is not None else {}) or {}
    document = data.get("document") if isinstance(data, dict) else None
    number = document.get("number") if isinstance(document, dict) else None
    return RenderResult(
        html="<html><body>preview</body></html>",
        pdf=_pdf(str(number or "document")),
        engine="test",
        page_mm=(148.0, 210.0),
        media_mm=(148.0, 210.0),
    )


@pytest.fixture
def fake_render(monkeypatch):
    monkeypatch.setattr("modules.documents.generation.render_layout", _fake_render)
    return _fake_render


def _chromium_available() -> bool:
    try:
        find_chromium()
    except RenderError:
        return False
    return True


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


async def _open_year(client, headers, year: dict) -> dict:
    response = await client.post(
        f"{ACADEMICS}/academic-years/{year['id']}/open",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _level(client, headers) -> dict:
    response = await client.get(f"{ACADEMICS}/levels", headers=headers, params={"scope": "all"})
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["items"] if item["code"] == "g5")


async def _section(client, headers, year: dict, level: dict, code: str = "A") -> dict:
    response = await client.post(
        f"{ACADEMICS}/sections",
        headers=headers,
        json={"year_id": year["id"], "level_id": level["id"], "code": code},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _student(
    client,
    headers,
    year: dict,
    level: dict,
    section: dict,
    *,
    number: str,
    given_name: str = "Hana",
) -> dict:
    person = {**PERSON, "given_name_en": given_name}
    response = await client.post(
        STUDENTS,
        headers=headers,
        json={
            "person": person,
            "student_number": number,
            "admission_date": "2026-09-15",
            "enrollment": {
                "year_id": year["id"],
                "level_id": level["id"],
                "section_id": section["id"],
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _published_template(client, headers, layout: dict, name: str = "Certificate") -> dict:
    created = await client.post(
        TEMPLATES,
        headers=headers,
        json={"name": name, "doc_type": "certificate_completion", "layout": layout},
    )
    assert created.status_code == 201, created.text
    template = created.json()
    published = await client.post(
        f"{TEMPLATES}/{template['id']}/versions/{template['draft_version_id']}/publish",
        headers=headers,
    )
    assert published.status_code == 200, published.text
    template["published_version"] = published.json()
    return template


async def _request_batch(client, headers, template: dict, target: dict, **extra) -> dict:
    response = await client.post(
        GENERATION,
        headers=headers,
        json={
            "template_id": template["id"],
            "version_id": template["published_version"]["id"],
            "target": target,
            **extra,
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


async def _run_batch(app, batch_id: str):
    """Run the worker body in-process with the app's storage and settings."""
    from modules.documents.generation import generate_batch, system_principal

    async with app.state.db.session() as session:
        batch = await session.get(DocumentBatch, uuid.UUID(batch_id))
        assert batch is not None
        return await generate_batch(
            session,
            batch_id=batch.id,
            principal=system_principal(batch),
            storage=app.state.storage,
            settings=app.state.settings,
            on_progress=None,
        )


async def _issued(client, headers, issued_id: str) -> dict:
    response = await client.get(f"{ISSUED}/{issued_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --- single generation ------------------------------------------------------


async def test_single_generation_issues_a_numbered_snapshot(
    client, app, superadmin_headers, fake_render
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    student = await _student(client, superadmin_headers, year, level, section, number="GEN-0001")

    template = await _published_template(
        client,
        superadmin_headers,
        _layout("{{student.full_name}}", "{{document.number}}", "{{school.name}}"),
    )
    started = await _request_batch(
        client,
        superadmin_headers,
        template,
        {"type": "student", "student_id": student["id"]},
    )
    assert started["status"] == "queued"
    assert started["count"] == 1
    assert started["batch_id"] and started["job_id"]

    # The API stays a request: nothing is rendered until the worker runs.
    pending = await client.get(f"{GENERATION}/batches/{started['batch_id']}", headers=superadmin_headers)
    assert pending.status_code == 200, pending.text
    assert pending.json()["status"] == "queued"
    assert pending.json()["template_version_number"] == 1

    await _run_batch(app, started["batch_id"])

    batch = await client.get(f"{GENERATION}/batches/{started['batch_id']}", headers=superadmin_headers)
    assert batch.status_code == 200, batch.text
    body = batch.json()
    assert body["status"] == "succeeded"
    assert body["issued_count"] == 1
    assert body["failed_count"] == 0
    assert body["progress"] == 100
    assert body["issued_at"]

    listing = await client.get(
        f"{GENERATION}/batches", headers=superadmin_headers, params={"template_id": template["id"]}
    )
    assert listing.status_code == 200, listing.text
    assert [item["id"] for item in listing.json()["items"]] == [started["batch_id"]]

    issued_list = await client.get(ISSUED, headers=superadmin_headers)
    assert issued_list.status_code == 200, issued_list.text
    assert issued_list.json()["total"] == 1
    summary = issued_list.json()["items"][0]
    assert summary["number"] == "DOC-2026-00001"
    assert summary["recipient_name"] == "Hana Tesfaye Bekele"
    assert summary["doc_type"] == "certificate_completion"
    assert summary["template_version_number"] == 1
    assert summary["verification_code"]
    assert summary["download_url"]

    detail = await _issued(client, superadmin_headers, summary["id"])
    assert detail["layout"]["elements"][0]["content"].startswith("{{student.full_name}}")
    assert detail["data_snapshot"]["student"]["full_name"] == "Hana Tesfaye Bekele"
    assert detail["data_snapshot"]["document"]["number"] == "DOC-2026-00001"
    assert detail["data_snapshot"]["document"]["verification_code"] == summary["verification_code"]
    assert detail["data_snapshot"]["document"]["verify_url"].endswith(
        f"/verify/{summary['verification_code']}"
    )
    assert detail["data_snapshot"]["school"]["name"] == "Demo Academy"

    job = await client.get(JOBS, headers=superadmin_headers, params={"kind": "documents.generate"})
    assert job.status_code == 200, job.text
    assert job.json()["items"][0]["status"] == "queued"
    assert job.json()["items"][0]["retryable"] is False


async def test_numbering_and_verification_codes_are_unique_across_batches(
    client, app, superadmin_headers, fake_render
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    first = await _student(client, superadmin_headers, year, level, section, number="GEN-0101")
    second = await _student(client, superadmin_headers, year, level, section, number="GEN-0102")
    template = await _published_template(client, superadmin_headers, _layout("{{student.full_name}}"))

    for student in (first, second):
        started = await _request_batch(
            client,
            superadmin_headers,
            template,
            {"type": "student", "student_id": student["id"]},
        )
        await _run_batch(app, started["batch_id"])

    listing = await client.get(ISSUED, headers=superadmin_headers, params={"sort": "number", "order": "asc"})
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    assert [item["number"] for item in items] == ["DOC-2026-00001", "DOC-2026-00002"]
    assert len({item["verification_code"] for item in items}) == 2
    for item in items:
        assert len(item["verification_code"]) >= 16
        assert set(item["verification_code"]) <= set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        )


async def test_reprint_serves_the_original_after_the_student_is_renamed(
    client, app, superadmin_headers, fake_render
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    student = await _student(client, superadmin_headers, year, level, section, number="GEN-0201")
    template = await _published_template(client, superadmin_headers, _layout("{{student.full_name}}"))
    started = await _request_batch(
        client,
        superadmin_headers,
        template,
        {"type": "student", "student_id": student["id"]},
    )
    await _run_batch(app, started["batch_id"])

    issued_id = (await client.get(ISSUED, headers=superadmin_headers)).json()["items"][0]["id"]
    first = await client.get(f"{ISSUED}/{issued_id}/reprint", headers=superadmin_headers)
    assert first.status_code == 200, first.text
    first_body = first.json()
    first_bytes = (await client.get(first_body["url"])).content
    assert first_bytes.startswith(b"%PDF")

    async with app.state.db.session() as session:
        person = await session.get(Person, uuid.UUID(student["person"]["id"]))
        assert person is not None
        person.given_name_en = "Renamed"
        person.search_name = build_search_name(person)
        await session.commit()

    again = await client.get(f"{ISSUED}/{issued_id}/reprint", headers=superadmin_headers)
    assert again.status_code == 200, again.text
    assert again.json()["checksum_sha256"] == first_body["checksum_sha256"]
    assert again.json()["file_id"] == first_body["file_id"]
    assert (await client.get(again.json()["url"])).content == first_bytes

    detail = await _issued(client, superadmin_headers, issued_id)
    assert detail["data_snapshot"]["student"]["full_name"] == "Hana Tesfaye Bekele"

    # A fresh generation would pick up the new name; the issued artifact does not.
    second = await _request_batch(
        client,
        superadmin_headers,
        template,
        {"type": "student", "student_id": student["id"]},
    )
    await _run_batch(app, second["batch_id"])
    newest = (await client.get(ISSUED, headers=superadmin_headers)).json()["items"][0]
    assert newest["recipient_name"] == "Renamed Tesfaye Bekele"


# --- bulk generation --------------------------------------------------------


async def test_section_batch_issues_every_placed_student(
    client, app, superadmin_headers, fake_render
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    other = await _section(client, superadmin_headers, year, level, code="B")
    students = [
        await _student(client, superadmin_headers, year, level, section, number=f"GEN-03{i:02d}")
        for i in range(1, 4)
    ]
    await _student(client, superadmin_headers, year, level, other, number="GEN-0399")
    template = await _published_template(client, superadmin_headers, _layout("{{student.full_name}}"))

    started = await _request_batch(
        client,
        superadmin_headers,
        template,
        {"type": "section", "section_id": section["id"]},
    )
    assert started["count"] == 3
    await _run_batch(app, started["batch_id"])

    batch = (
        await client.get(f"{GENERATION}/batches/{started['batch_id']}", headers=superadmin_headers)
    ).json()
    assert batch["status"] == "succeeded"
    assert batch["issued_count"] == 3
    assert batch["failed_count"] == 0

    listing = await client.get(
        ISSUED,
        headers=superadmin_headers,
        params={"batch_id": started["batch_id"], "sort": "number", "order": "asc"},
    )
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    assert [item["recipient_name"] for item in items] == [
        "Hana Tesfaye Bekele",
        "Hana Tesfaye Bekele",
        "Hana Tesfaye Bekele",
    ]
    assert [item["number"] for item in items] == [
        "DOC-2026-00001",
        "DOC-2026-00002",
        "DOC-2026-00003",
    ]
    assert {item["recipient_id"] for item in items} == {student["id"] for student in students}

    # The section's students are distinct even though the printed names match.
    assert (
        len(
            {
                item["data_snapshot"]["student"]["student_number"]
                for item in [await _issued(client, superadmin_headers, item["id"]) for item in items]
            }
        )
        == 3
    )


async def _bulk_students(app, year: dict, level: dict, section: dict, count: int) -> None:
    """Create many placed students directly; the API path is covered above."""
    async with app.state.db.session() as session:
        for index in range(1, count + 1):
            person = Person(
                given_name_en=f"Student{index:03d}",
                father_name_en="Bulk",
                grandfather_name_en="Test",
                search_name="",
                sex="female",
                date_of_birth=date(2015, 3, 4),
            )
            session.add(person)
            await session.flush()
            person.search_name = build_search_name(person)
            student = StudentProfile(
                person_id=person.id,
                student_number=f"BULK-{index:04d}",
                status="active",
                admission_date=date(2026, 9, 15),
            )
            session.add(student)
            await session.flush()
            session.add(
                StudentEnrollment(
                    student_id=student.id,
                    year_id=uuid.UUID(year["id"]),
                    level_id=uuid.UUID(level["id"]),
                    section_id=uuid.UUID(section["id"]),
                    status="active",
                )
            )
        await session.commit()


async def test_three_hundred_documents_queue_before_any_render(
    client, app, superadmin_headers, fake_render
) -> None:
    """The request stays fast: one bulk is queued, not rendered on the API."""
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    await _bulk_students(app, year, level, section, 300)
    template = await _published_template(client, superadmin_headers, _layout("{{student.full_name}}"))

    started = await _request_batch(
        client,
        superadmin_headers,
        template,
        {"type": "section", "section_id": section["id"]},
    )
    assert started["count"] == 300
    assert started["status"] == "queued"

    # The response is the proof the API did not block: the queue is recorded
    # and nothing has been rendered yet.
    before = await client.get(ISSUED, headers=superadmin_headers)
    assert before.status_code == 200, before.text
    assert before.json()["total"] == 0
    pending = await client.get(f"{GENERATION}/batches/{started['batch_id']}", headers=superadmin_headers)
    assert pending.json()["status"] == "queued"
    assert pending.json()["issued_count"] == 0

    await _run_batch(app, started["batch_id"])

    batch = (
        await client.get(f"{GENERATION}/batches/{started['batch_id']}", headers=superadmin_headers)
    ).json()
    assert batch["status"] == "succeeded"
    assert batch["issued_count"] == 300
    assert batch["failed_count"] == 0
    assert batch["progress"] == 100

    listing = await client.get(
        ISSUED,
        headers=superadmin_headers,
        params={
            "batch_id": started["batch_id"],
            "limit": 100,
            "sort": "number",
            "order": "asc",
        },
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 300
    numbers = [item["number"] for item in listing.json()["items"]]
    assert len(set(numbers)) == 100
    assert numbers[0] == "DOC-2026-00001"
    assert numbers[-1] == "DOC-2026-00100"


async def test_combined_batch_merges_every_document_and_keeps_individual_files(
    client, app, superadmin_headers, fake_render
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    for index in (1, 2):
        await _student(
            client,
            superadmin_headers,
            year,
            level,
            section,
            number=f"GEN-04{index:02d}",
            given_name=f"Student{index}",
        )
    template = await _published_template(client, superadmin_headers, _layout("{{student.full_name}}"))

    started = await _request_batch(
        client,
        superadmin_headers,
        template,
        {"type": "section", "section_id": section["id"]},
        combine=True,
    )
    await _run_batch(app, started["batch_id"])

    batch = (
        await client.get(f"{GENERATION}/batches/{started['batch_id']}", headers=superadmin_headers)
    ).json()
    assert batch["status"] == "succeeded"
    assert batch["combine"] is True
    assert batch["file_id"]
    assert batch["download_url"]

    download = await client.get(
        f"{GENERATION}/batches/{started['batch_id']}/download",
        headers=superadmin_headers,
    )
    assert download.status_code == 200, download.text
    link = download.json()
    assert link["filename"].endswith(".pdf")
    merged = (await client.get(link["url"])).content
    reader = PdfReader(io.BytesIO(merged))
    assert len(reader.pages) == 2
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    assert "DOC-2026-00001" in text
    assert "DOC-2026-00002" in text

    individual = await client.get(
        ISSUED, headers=superadmin_headers, params={"batch_id": started["batch_id"]}
    )
    assert individual.json()["total"] == 2
    for item in individual.json()["items"]:
        assert item["download_url"]
        assert (await client.get(item["download_url"])).content.startswith(b"%PDF")


# --- request validation and permissions ------------------------------------


async def test_generation_requires_a_published_version(client, superadmin_headers) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    student = await _student(client, superadmin_headers, year, level, section, number="GEN-0501")
    draft = await client.post(
        TEMPLATES,
        headers=superadmin_headers,
        json={"name": "Draft only", "layout": _layout("{{student.full_name}}")},
    )
    template = draft.json()

    response = await client.post(
        GENERATION,
        headers=superadmin_headers,
        json={
            "template_id": template["id"],
            "target": {"type": "student", "student_id": student["id"]},
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["message_key"] == "error.documents.version_not_published"


async def test_generation_rejects_empty_and_malformed_targets(client, superadmin_headers) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    empty = await _section(client, superadmin_headers, year, level)
    student = await _student(client, superadmin_headers, year, level, empty, number="GEN-0601")
    template = await _published_template(client, superadmin_headers, _layout("{{student.full_name}}"))

    target = await client.post(
        GENERATION,
        headers=superadmin_headers,
        json={
            "template_id": template["id"],
            "target": {"type": "section", "section_id": str(uuid.uuid4())},
        },
    )
    assert target.status_code == 404, target.text

    mixed = await client.post(
        GENERATION,
        headers=superadmin_headers,
        json={
            "template_id": template["id"],
            "target": {
                "type": "student",
                "student_id": student["id"],
                "section_id": empty["id"],
            },
        },
    )
    assert mixed.status_code == 422, mixed.text

    unknown = await client.post(
        GENERATION,
        headers=superadmin_headers,
        json={
            "template_id": template["id"],
            "target": {"type": "student", "student_id": str(uuid.uuid4())},
        },
    )
    assert unknown.status_code == 404, unknown.text

    # A second empty section has nobody enrolled.
    lonely = await _section(client, superadmin_headers, year, level, code="Z")
    blank = await client.post(
        GENERATION,
        headers=superadmin_headers,
        json={
            "template_id": template["id"],
            "target": {"type": "section", "section_id": lonely["id"]},
        },
    )
    assert blank.status_code == 422, blank.text
    assert blank.json()["error"]["message_key"] == "error.documents.target_empty"


async def test_generation_is_gated_by_permission_and_module(client, app, superadmin_headers) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    student = await _student(client, superadmin_headers, year, level, section, number="GEN-0701")
    template = await _published_template(client, superadmin_headers, _layout("{{student.full_name}}"))
    body = {
        "template_id": template["id"],
        "target": {"type": "student", "student_id": student["id"]},
    }

    await create_role(app, "document_designer", [("documents.template.design", "all")])
    email = unique_email("designer")
    await create_user(app, email, roles=["document_designer"])
    designer = await login(client, email)

    denied = await client.post(GENERATION, headers=designer, json=body)
    assert denied.status_code == 403, denied.text
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"
    assert (await client.get(f"{GENERATION}/targets", headers=designer)).status_code == 403

    anonymous = await client.post(GENERATION, json=body)
    assert anonymous.status_code == 401

    disabled = await client.put(
        f"{MODULES}/documents",
        headers=superadmin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200, disabled.text
    try:
        blocked = await client.post(GENERATION, headers=superadmin_headers, json=body)
        assert blocked.status_code == 403, blocked.text
        assert blocked.json()["error"]["code"] == "MODULE_DISABLED"
    finally:
        await client.put(f"{MODULES}/documents", headers=superadmin_headers, json={"enabled": True})


async def test_generation_targets_and_student_search_follow_the_open_year(client, superadmin_headers) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    student = await _student(client, superadmin_headers, year, level, section, number="GEN-0801")
    await _open_year(client, superadmin_headers, year)

    targets = await client.get(f"{GENERATION}/targets", headers=superadmin_headers)
    assert targets.status_code == 200, targets.text
    body = targets.json()
    assert body["year"]["id"] == year["id"]
    assert body["year"]["is_current"] is True
    assert any(item["code"] == "g5" for item in body["levels"])
    assert [item["id"] for item in body["sections"]] == [section["id"]]

    matches = await client.get(
        f"{GENERATION}/students",
        headers=superadmin_headers,
        params={"q": "GEN-0801"},
    )
    assert matches.status_code == 200, matches.text
    items = matches.json()["items"]
    assert [item["id"] for item in items] == [student["id"]]
    assert items[0]["student_number"] == "GEN-0801"
    assert items[0]["level_name"] == "Grade 5"
    assert items[0]["section_code"] == "A"

    amharic = await client.get(
        f"{GENERATION}/students",
        headers=superadmin_headers,
        params={"q": "ሀና"},
    )
    assert amharic.status_code == 200, amharic.text
    assert [item["id"] for item in amharic.json()["items"]] == [student["id"]]


# --- worker wiring ----------------------------------------------------------


async def test_worker_task_marks_the_job_and_batch(
    client, app, superadmin_headers, fake_render, monkeypatch
) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    student = await _student(client, superadmin_headers, year, level, section, number="GEN-0901")
    template = await _published_template(client, superadmin_headers, _layout("{{student.full_name}}"))
    started = await _request_batch(
        client,
        superadmin_headers,
        template,
        {"type": "student", "student_id": student["id"]},
    )

    monkeypatch.setenv("ERP_DATABASE_URL", app.state.settings.database_url)
    monkeypatch.setattr("core.events.celery_app.get_settings", lambda: app.state.settings)
    from core.events.celery_app import documents_generate_task

    result = await asyncio.to_thread(
        documents_generate_task,
        started["job_id"],
        started["batch_id"],
    )
    assert result["ok"] is True

    job = await client.get(JOBS, headers=superadmin_headers, params={"kind": "documents.generate"})
    assert job.status_code == 200, job.text
    item = job.json()["items"][0]
    assert item["id"] == started["job_id"]
    assert item["status"] == "succeeded"
    assert item["progress"] == 100

    batch = (
        await client.get(f"{GENERATION}/batches/{started['batch_id']}", headers=superadmin_headers)
    ).json()
    assert batch["status"] == "succeeded"
    assert batch["issued_count"] == 1


@pytest.mark.skipif(not _chromium_available(), reason="Chromium is not installed")
async def test_real_renderer_produces_a_searchable_pdf(client, app, superadmin_headers) -> None:
    year = await _year(client, superadmin_headers)
    level = await _level(client, superadmin_headers)
    section = await _section(client, superadmin_headers, year, level)
    student = await _student(client, superadmin_headers, year, level, section, number="GEN-1001")
    template = await _published_template(client, superadmin_headers, _layout("{{student.full_name}}"))
    started = await _request_batch(
        client,
        superadmin_headers,
        template,
        {"type": "student", "student_id": student["id"]},
    )
    await _run_batch(app, started["batch_id"])

    summary = (await client.get(ISSUED, headers=superadmin_headers)).json()["items"][0]
    pdf = (await client.get(summary["download_url"])).content
    reader = PdfReader(io.BytesIO(pdf))
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    assert "Hana Tesfaye Bekele" in text
