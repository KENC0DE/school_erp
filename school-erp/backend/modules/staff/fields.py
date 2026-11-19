"""Staff document fields for Document Studio (P5-11).

An experience letter is a claim about a person's employment, so the field
vocabulary mirrors the staff record rather than the student vocabulary:
identity in both scripts, staff number, position, department and the employment
dates. The keys are stable because issued documents keep a data snapshot.
"""

from __future__ import annotations

from core.documents.fields import DocumentField

FIELDS: tuple[DocumentField, ...] = (
    DocumentField(
        "staff.full_name",
        "staff.field.full_name",
        "text",
        formats=("script",),
        sample="Solomon Tesfaye Gebre",
    ),
    DocumentField(
        "staff.short_name",
        "staff.field.short_name",
        "text",
        formats=("script",),
        sample="Solomon Tesfaye",
    ),
    DocumentField(
        "staff.first_name",
        "staff.field.first_name",
        "text",
        formats=("script",),
        sample="Solomon",
    ),
    DocumentField(
        "staff.middle_name",
        "staff.field.middle_name",
        "text",
        formats=("script",),
        sample="Tesfaye",
    ),
    DocumentField(
        "staff.last_name",
        "staff.field.last_name",
        "text",
        formats=("script",),
        sample="Gebre",
    ),
    DocumentField(
        "staff.staff_number",
        "staff.field.staff_number",
        "text",
        sample="STF-2026-0001",
    ),
    DocumentField(
        "staff.status",
        "staff.field.status",
        "text",
        sample="active",
    ),
    DocumentField(
        "staff.position",
        "staff.field.position",
        "text",
        formats=("script",),
        sample="Mathematics Teacher",
    ),
    DocumentField(
        "staff.department",
        "staff.field.department",
        "text",
        formats=("script",),
        sample="Science",
    ),
    DocumentField(
        "staff.start_date",
        "staff.field.start_date",
        "date",
        formats=("calendar",),
        sample="2020-09-01",
    ),
    DocumentField(
        "staff.end_date",
        "staff.field.end_date",
        "date",
        formats=("calendar",),
        sample="2026-06-30",
    ),
    DocumentField(
        "staff.notes",
        "staff.field.notes",
        "text",
        formats=("script",),
        sample="Head of the mathematics department.",
    ),
    DocumentField(
        "staff.photo",
        "staff.field.photo",
        "text",
        sample="https://demo.school/assets/staff-photo.png",
    ),
    DocumentField(
        "staff.signature",
        "staff.field.signature",
        "text",
        sample="https://demo.school/assets/staff-signature.png",
    ),
)

__all__ = ["FIELDS"]
