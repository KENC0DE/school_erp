"""Preview data for the template editor (P5-07).

A preview is only useful if it is produced by the same renderer that prints the
document. This module builds the two data sets that renderer receives:

* **sample** data comes from the declared field samples, so a designer can see
  every placeholder even before a student exists;
* **student** data comes from the live student record, the student's current
  assessment snapshot and (when the caller may read it) attendance.

The two sets share the school profile and issue dates. Nothing here writes
anything: previewing a layout never creates an issued document, a snapshot or an
audit entry.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from core.auth.principal import Principal
from core.documents.registry import RegisteredField
from core.documents.render import RenderContext, layout_to_html, page_trim_mm
from core.settings.core_schema import CoreSettings
from core.settings.service import load_model
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import GradeLevel, Section
from modules.assessment.results import list_snapshots
from modules.assessment.schemas import ResultSnapshotQuery
from modules.attendance.models import AttendanceRecord, AttendanceSession
from modules.documents.service import parse_layout
from modules.students import service as student_service


def _assign(data: dict[str, Any], path: str, value: Any) -> None:
    """Place ``value`` at a dotted path, creating intermediate mappings."""
    if value is None:
        return
    parts = path.split(".")
    cursor = data
    for part in parts[:-1]:
        current = cursor.get(part)
        if not isinstance(current, dict):
            current = {}
            cursor[part] = current
        cursor = current
    cursor[parts[-1]] = value


def sample_context(fields: list[RegisteredField]) -> dict[str, Any]:
    """A dataset where every declared field has its example value."""
    data: dict[str, Any] = {}
    for registered in fields:
        _assign(data, registered.field.key, registered.field.sample)
    return data


async def common_context(session: AsyncSession) -> dict[str, Any]:
    """Values every document can use, regardless of the selected record."""
    core = await load_model(session, "core", CoreSettings)
    issued = date.today()
    expires = issued + timedelta(days=365)
    return {
        "school": {"name": core.school_profile.name},
        "date": {"issued": issued.isoformat(), "expires": expires.isoformat()},
    }


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge two contexts, preferring the override at each leaf."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _join_parts(*parts: str | None) -> str:
    return " ".join(part for part in parts if part)


def _names(person: Any) -> tuple[str, str, str, str]:
    """English and Amharic full/short names from a ``PersonOut``."""
    english = _join_parts(
        person.given_name_en,
        person.father_name_en,
        person.grandfather_name_en,
    )
    amharic = _join_parts(
        person.given_name_am,
        person.father_name_am,
        person.grandfather_name_am,
    )
    short_english = _join_parts(person.given_name_en, person.father_name_en)
    short_amharic = _join_parts(person.given_name_am, person.father_name_am)
    return english, amharic, short_english, short_amharic


async def _attendance_context(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    year_id: uuid.UUID,
) -> dict[str, Any]:
    """Present/absent totals for one student, when the caller may read them."""
    if not principal.can("attendance.view"):
        return {}
    rows = (
        await session.execute(
            select(AttendanceRecord.status, func.count())
            .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
            .where(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.deleted_at.is_(None),
                AttendanceSession.year_id == year_id,
                AttendanceSession.deleted_at.is_(None),
            )
            .group_by(AttendanceRecord.status)
        )
    ).all()
    counts = {status: int(count) for status, count in rows}
    present = counts.get("present", 0)
    absent = counts.get("absent", 0)
    total = sum(counts.values())
    if total == 0:
        return {}
    percent = (Decimal(present) * 100 / Decimal(total)).quantize(Decimal("0.01"))
    text = format(percent, "f").rstrip("0").rstrip(".")
    return {
        "student": {
            "attendance_present": present,
            "attendance_absent": absent,
            "attendance_percent": text or "0",
        }
    }


def _subject_rows(student: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for subject in student.get("subjects") or []:
        if not isinstance(subject, dict):
            continue
        rows.append(
            {
                "subject": subject.get("subject_name"),
                "total": subject.get("total"),
                "out_of": subject.get("out_of"),
                "percent": subject.get("percent"),
                "grade": subject.get("grade_label"),
                "remark": subject.get("grade_remark"),
                "rank": subject.get("rank"),
            }
        )
    return rows


def _result_values(prefix: str, student: dict[str, Any]) -> dict[str, Any]:
    values = {
        f"{prefix}.total": student.get("total"),
        f"{prefix}.out_of": student.get("out_of"),
        f"{prefix}.percent": student.get("percent"),
        f"{prefix}.grade": student.get("grade_label"),
        f"{prefix}.remark": student.get("grade_remark"),
        f"{prefix}.gpa": student.get("gpa_points"),
        f"{prefix}.pass": student.get("is_pass"),
    }
    return {key: value for key, value in values.items() if value is not None}


async def _results_context(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    year_id: uuid.UUID,
    section_id: uuid.UUID | None,
) -> dict[str, Any]:
    """Read the latest published term and year sheets that include the student."""
    if section_id is None:
        return {}
    context: dict[str, Any] = {}
    for kind in ("term", "year"):
        snapshots = await list_snapshots(
            session,
            principal,
            ResultSnapshotQuery(
                year_id=year_id,
                section_id=section_id,
                kind=kind,
                limit=1,
                order="desc",
            ),
        )
        if not snapshots.items:
            continue
        payload = snapshots.items[0].payload
        student = next(
            (
                item
                for item in payload.get("students") or []
                if str(item.get("student_id")) == str(student_id)
            ),
            None,
        )
        if not isinstance(student, dict):
            continue
        if kind == "term":
            for path, value in _result_values("student.marks.term", student).items():
                _assign(context, path, value)
            if payload.get("term_name"):
                context.setdefault("term", {})["name"] = payload["term_name"]
        else:
            for path, value in _result_values("student.marks.year", student).items():
                _assign(context, path, value)
        if "student.marks.subjects" not in context:
            _assign(context, "student.marks.subjects", _subject_rows(student))
        _assign(context, "student.rank", student.get("rank"))
        _assign(context, "student.rank_size", student.get("rank_size"))
    return context


async def student_context(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
) -> tuple[dict[str, Any], str]:
    """Real data for one student, plus the name shown in the preview picker."""
    detail = await student_service.get_student(session, principal, student_id)
    person = detail.person
    full_english, full_amharic, short_english, short_amharic = _names(person)

    data: dict[str, Any] = {}
    _assign(data, "student.full_name", full_english)
    _assign(data, "student.full_name_am", full_amharic or None)
    _assign(data, "student.short_name", short_english)
    _assign(data, "student.short_name_am", short_amharic or None)
    _assign(data, "student.first_name", person.given_name_en)
    _assign(data, "student.first_name_am", person.given_name_am or None)
    _assign(data, "student.middle_name", person.father_name_en)
    _assign(data, "student.middle_name_am", person.father_name_am or None)
    _assign(data, "student.last_name", person.grandfather_name_en)
    _assign(data, "student.last_name_am", person.grandfather_name_am or None)
    _assign(data, "student.student_number", detail.student_number)
    _assign(data, "student.status", detail.status)
    _assign(
        data, "student.admission_date", detail.admission_date.isoformat() if detail.admission_date else None
    )
    _assign(data, "student.remarks", detail.notes)

    guardian = next((item for item in detail.guardians if item.is_primary), None)
    if guardian is None and detail.guardians:
        guardian = detail.guardians[0]
    if guardian is not None:
        guardian_name = guardian.person.full_name
        _assign(data, "student.guardian_name", guardian_name)

    enrollment = detail.enrollment
    if enrollment is not None:
        _assign(data, "student.grade", enrollment.level_name)
        _assign(data, "student.section", enrollment.section_code)
        _assign(data, "student.academic_year", enrollment.year_name)

        if enrollment.level_id:
            level = await session.get(GradeLevel, uuid.UUID(enrollment.level_id))
            if level is not None:
                _assign(data, "student.grade", level.name)
                _assign(data, "student.grade_am", level.name_am)
                _assign(data, "student.next_grade", await _next_level_name(session, level))
        if enrollment.section_id:
            section = await session.get(Section, uuid.UUID(enrollment.section_id))
            if section is not None:
                _assign(data, "student.section", section.code)
                _assign(data, "student.section_am", section.name_am)

        attendance = await _attendance_context(
            session,
            principal,
            student_id,
            uuid.UUID(enrollment.year_id),
        )
        data = _merge(data, attendance)
        results = await _results_context(
            session,
            principal,
            student_id,
            uuid.UUID(enrollment.year_id),
            uuid.UUID(enrollment.section_id) if enrollment.section_id else None,
        )
        data = _merge(data, results)
    return data, full_english or detail.student_number


async def _next_level_name(session: AsyncSession, level: GradeLevel) -> str | None:
    row = (
        await session.execute(
            select(GradeLevel)
            .where(
                GradeLevel.deleted_at.is_(None),
                GradeLevel.is_active.is_(True),
                GradeLevel.sort_order > level.sort_order,
            )
            .order_by(GradeLevel.sort_order)
            .limit(1)
        )
    ).scalar_one_or_none()
    return row.name if row is not None else None


def render_preview(
    layout: dict[str, Any],
    data: dict[str, Any],
    *,
    locale: str,
) -> dict[str, Any]:
    """Render a layout payload with the production HTML renderer."""
    parsed = parse_layout(layout)
    html = layout_to_html(parsed, RenderContext(data=data, locale=locale))
    trim = page_trim_mm(parsed.page)
    bleed = float(parsed.page.bleed_mm)
    return {
        "html": html,
        "page_mm": [trim[0], trim[1]],
        "media_mm": [trim[0] + 2 * bleed, trim[1] + 2 * bleed],
    }


__all__ = [
    "common_context",
    "render_preview",
    "sample_context",
    "student_context",
]
