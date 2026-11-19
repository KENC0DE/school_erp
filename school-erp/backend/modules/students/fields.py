"""Student document fields for Document Studio (P5-05, completed in P5-11).

Certificates, ID cards, admission letters and report-card headers all need the
same core identities: the student's name in both scripts, number, grade,
section and status. The keys are stable because a generated document stores the
version and a data snapshot, so an old template keeps resolving.

``student.full_name`` also carries a script format: the renderer prefers
``student.full_name_am`` when a template asks for the Amharic variant.
"""

from __future__ import annotations

from core.documents.fields import DocumentField

FIELDS: tuple[DocumentField, ...] = (
    DocumentField(
        "student.full_name",
        "students.field.full_name",
        "text",
        formats=("script",),
        sample="Abebe Kebede Tadesse",
    ),
    DocumentField(
        "student.short_name",
        "students.field.short_name",
        "text",
        formats=("script",),
        sample="Abebe Kebede",
    ),
    DocumentField(
        "student.first_name",
        "students.field.first_name",
        "text",
        formats=("script",),
        sample="Abebe",
    ),
    DocumentField(
        "student.middle_name",
        "students.field.middle_name",
        "text",
        formats=("script",),
        sample="Kebede",
    ),
    DocumentField(
        "student.last_name",
        "students.field.last_name",
        "text",
        formats=("script",),
        sample="Tadesse",
    ),
    DocumentField(
        "student.student_number",
        "students.field.student_number",
        "text",
        sample="DEMO-2026-0001",
    ),
    DocumentField(
        "student.status",
        "students.field.status",
        "text",
        sample="active",
    ),
    DocumentField(
        "student.next_grade",
        "students.field.next_grade",
        "text",
        formats=("script",),
        sample="Grade 6",
    ),
    DocumentField(
        "student.attendance_present",
        "students.field.attendance_present",
        "integer",
        sample=172,
    ),
    DocumentField(
        "student.attendance_absent",
        "students.field.attendance_absent",
        "integer",
        sample=8,
    ),
    DocumentField(
        "student.attendance_percent",
        "students.field.attendance_percent",
        "decimal",
        sample="95.56",
    ),
    DocumentField(
        "student.remarks",
        "students.field.remarks",
        "text",
        formats=("script",),
        sample="A diligent student who participates actively.",
    ),
    DocumentField(
        "student.admission_date",
        "students.field.admission_date",
        "date",
        formats=("calendar",),
        sample="2026-09-01",
    ),
    DocumentField(
        "student.grade",
        "students.field.grade",
        "text",
        formats=("script",),
        sample="Grade 5",
    ),
    DocumentField(
        "student.section",
        "students.field.section",
        "text",
        formats=("script",),
        sample="5A",
    ),
    DocumentField(
        "student.academic_year",
        "students.field.academic_year",
        "text",
        sample="2026/27",
    ),
    DocumentField(
        "student.guardian_name",
        "students.field.guardian_name",
        "text",
        formats=("script",),
        sample="Kebede Tadesse",
    ),
    DocumentField(
        "school.name",
        "students.field.school_name",
        "text",
        formats=("script",),
        sample="Demo Academy",
    ),
    DocumentField(
        "student.photo",
        "students.field.photo",
        "text",
        sample="https://demo.school/assets/student-photo.png",
    ),
    DocumentField(
        "student.signature",
        "students.field.signature",
        "text",
        sample="https://demo.school/assets/signature.png",
    ),
)

__all__ = ["FIELDS"]
