"""The starter template library (P5-04).

A school should not face an empty canvas on first use. Each starter is a normal
version 1 layout that the user can create a template from, then edit freely. The
names and descriptions are i18n keys: the client translates them when it lists
the library, and sends the translated name it showed back when it creates the
template, so the backend never invents user-facing text.

The layouts use the field vocabulary the enabled modules offer. A module that is
not enabled simply renders those tokens as empty text. P5-11 registers the
staff fields, so experience letters bind live employment data; fee fields wait
for the fees module in Phase 7.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LATIN = "Inter"
ETHIOPIC = "Noto Sans Ethiopic"
INK = "#111111"
BRAND = "#123c4a"
ACCENT = "#8b5e3c"
PAPER = "#ffffff"


def _rect(x: float, y: float, w: float, h: float) -> dict[str, float]:
    return {"x_mm": x, "y_mm": y, "w_mm": w, "h_mm": h}


def _text(
    element_id: str,
    content: str,
    rect: tuple[float, float, float, float],
    *,
    size: float = 10,
    family: str = LATIN,
    bold: bool = False,
    italic: bool = False,
    align: str = "left",
    vertical_align: str = "top",
    colour: str = INK,
    wrap: bool = True,
    spacing: float = 0,
    format: dict[str, Any] | None = None,
    condition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    element: dict[str, Any] = {
        "id": element_id,
        "type": "text",
        "rect": _rect(*rect),
        "content": content,
        "style": {
            "font_family": family,
            "font_size_pt": size,
            "bold": bold,
            "italic": italic,
            "colour": colour,
            "letter_spacing_pt": spacing,
        },
        "align": align,
        "vertical_align": vertical_align,
        "wrap": wrap,
    }
    if format is not None:
        element["format"] = format
    if condition is not None:
        element["visible_when"] = condition
    return element


def _shape(
    element_id: str,
    shape: str,
    rect: tuple[float, float, float, float],
    *,
    fill: str | None = None,
    stroke: str | None = None,
    stroke_width: float = 0.4,
    radius: float = 0,
    z: int = 0,
) -> dict[str, Any]:
    element: dict[str, Any] = {
        "id": element_id,
        "type": "shape",
        "rect": _rect(*rect),
        "shape": shape,
        "z": z,
    }
    if fill is not None:
        element["fill"] = fill
    if stroke is not None:
        element["stroke"] = {"colour": stroke, "width_mm": stroke_width}
    if shape == "rect" and radius:
        element["radius_mm"] = radius
    return element


def _line(
    element_id: str,
    x: float,
    y: float,
    w: float,
    *,
    colour: str = ACCENT,
    width: float = 0.4,
) -> dict[str, Any]:
    return _shape(
        element_id,
        "line",
        (x, y, w, max(width, 0.2)),
        stroke=colour,
        stroke_width=width,
    )


def _image(
    element_id: str,
    rect: tuple[float, float, float, float],
    value: str,
    *,
    fit: str = "cover",
    alt: str | None = None,
) -> dict[str, Any]:
    element: dict[str, Any] = {
        "id": element_id,
        "type": "image",
        "rect": _rect(*rect),
        "source": {"kind": "field", "value": value},
        "fit": fit,
    }
    if alt:
        element["alt"] = alt
    return element


def _qr(
    element_id: str,
    rect: tuple[float, float, float, float],
    data: str,
) -> dict[str, Any]:
    return {
        "id": element_id,
        "type": "qr",
        "rect": _rect(*rect),
        "data": data,
        "error_correction": "M",
    }


def _barcode(
    element_id: str,
    rect: tuple[float, float, float, float],
    data: str,
) -> dict[str, Any]:
    return {
        "id": element_id,
        "type": "barcode",
        "rect": _rect(*rect),
        "data": data,
        "symbology": "code128",
        "show_text": False,
    }


def _layout(
    page: dict[str, Any],
    elements: list[dict[str, Any]],
    *,
    name: str | None = None,
) -> dict[str, Any]:
    return {
        "version": 1,
        "page": page,
        **({"name": name} if name else {}),
        "elements": elements,
    }


@dataclass(frozen=True)
class Starter:
    key: str
    doc_type: str
    name_key: str
    description_key: str
    layout: dict[str, Any]


def _report_card() -> dict[str, Any]:
    return _layout(
        {"size": "A4", "margins_mm": {"top": 12, "right": 12, "bottom": 12, "left": 12}},
        [
            _shape("band", "rect", (0, 0, 210, 26), fill=BRAND),
            _text(
                "school",
                "{{school.name}}",
                (12, 6, 186, 10),
                size=16,
                family=ETHIOPIC,
                bold=True,
                align="center",
                colour="#ffffff",
            ),
            _text(
                "heading",
                "Report Card",
                (12, 17, 186, 6),
                size=9,
                align="center",
                colour="#ffffff",
                spacing=1.2,
            ),
            _text("student", "{{student.full_name}}", (12, 32, 120, 10), size=16, family=ETHIOPIC, bold=True),
            _text(
                "placement",
                "Grade {{student.grade}} — Section {{student.section}}",
                (12, 43, 120, 6),
                size=10,
                family=ETHIOPIC,
            ),
            _text(
                "term",
                "{{term.name}}",
                (120, 32, 78, 6),
                size=10,
                align="right",
                family=ETHIOPIC,
            ),
            _image("photo", (168, 32, 30, 36), "student.photo", alt="Student photograph"),
            _text(
                "grid",
                "Subject",
                (12, 66, 60, 5),
                size=8,
                bold=True,
                colour="#6b6b6b",
                condition={"op": "exists", "field": "student.marks.subjects"},
            ),
            {
                "id": "marks",
                "type": "table",
                "rect": _rect(12, 72, 186, 92),
                "table": {
                    "source": "student.marks.subjects",
                    "row_height_mm": 7,
                    "columns": [
                        {"key": "subject", "label": "Subject", "binding": "subject", "width_mm": 44},
                        {
                            "key": "classwork",
                            "label": "Class work",
                            "binding": "classwork",
                            "group": "Term 1",
                            "width_mm": 18,
                            "align": "right",
                        },
                        {
                            "key": "test",
                            "label": "Test",
                            "binding": "test",
                            "group": "Term 1",
                            "width_mm": 18,
                            "align": "right",
                        },
                        {
                            "key": "final",
                            "label": "Final",
                            "binding": "final",
                            "group": "Term 2",
                            "width_mm": 18,
                            "align": "right",
                        },
                        {
                            "key": "total",
                            "label": "Total",
                            "computed": {"op": "sum", "of": ["classwork", "test", "final"]},
                            "width_mm": 20,
                            "align": "right",
                            "format": {"number_decimals": 2},
                        },
                        {
                            "key": "average",
                            "label": "Average",
                            "computed": {"op": "average", "of": ["classwork", "test", "final"]},
                            "width_mm": 20,
                            "align": "right",
                            "format": {"number_decimals": 2},
                        },
                        {
                            "key": "rank",
                            "label": "Rank",
                            "computed": {"op": "rank", "by": "total", "descending": True},
                            "width_mm": 14,
                            "align": "center",
                        },
                        {"key": "remark", "label": "Remark", "binding": "remark", "width_mm": 34},
                    ],
                    "summaries": [
                        {"column": "total", "aggregate": "sum", "label": "Class total"},
                        {"column": "average", "aggregate": "average", "label": "Class average"},
                    ],
                },
                "style": {"font_family": ETHIOPIC, "font_size_pt": 9},
            },
            _text(
                "attendance",
                "Attendance: {{student.attendance_present}} present / "
                "{{student.attendance_absent}} absent ({{student.attendance_percent}}%)",
                (12, 168, 186, 6),
                size=9,
                family=ETHIOPIC,
            ),
            _text(
                "promoted",
                "Promoted to {{student.next_grade}}",
                (12, 176, 186, 7),
                size=10,
                family=ETHIOPIC,
                bold=True,
                condition={"op": "eq", "field": "student.status", "value": "promoted"},
            ),
            _text(
                "repeat",
                "Repeat {{student.grade}}",
                (12, 176, 186, 7),
                size=10,
                family=ETHIOPIC,
                bold=True,
                condition={"op": "eq", "field": "student.status", "value": "repeat"},
            ),
            _text(
                "total",
                "Term total {{student.marks.term.total}} / {{student.marks.term.out_of}}",
                (12, 188, 120, 7),
                size=10,
                family=ETHIOPIC,
            ),
            _text(
                "term_grade",
                "{{student.marks.term.grade}}",
                (150, 184, 48, 14),
                size=20,
                bold=True,
                align="center",
            ),
            _text(
                "remark",
                "{{student.remarks}}",
                (12, 198, 186, 8),
                size=9,
                family=ETHIOPIC,
            ),
            _line("signature_line", 120, 250, 70, width=0.3, colour="#9a9a9a"),
            _text("signature", "Principal", (120, 252, 70, 5), size=8, align="center"),
            _text(
                "issued",
                "Issued {{date.issued}}",
                (12, 268, 120, 6),
                size=8,
                family=ETHIOPIC,
                format={"calendar": "both"},
            ),
        ],
        name="Report card",
    )


def _transcript() -> dict[str, Any]:
    return _layout(
        {"size": "A4", "margins_mm": {"top": 14, "right": 14, "bottom": 14, "left": 14}},
        [
            _shape("band", "rect", (0, 0, 210, 24), fill=BRAND),
            _text(
                "school",
                "{{school.name}}",
                (14, 5, 182, 9),
                size=15,
                family=ETHIOPIC,
                bold=True,
                align="center",
                colour="#ffffff",
            ),
            _text(
                "heading",
                "Academic Transcript",
                (14, 15, 182, 6),
                size=9,
                align="center",
                colour="#ffffff",
                spacing=1.2,
            ),
            _text(
                "student",
                "{{student.full_name}}",
                (14, 31, 120, 9),
                size=15,
                family=ETHIOPIC,
                bold=True,
            ),
            _text(
                "identity",
                "Student number {{student.student_number}} · Grade {{student.grade}} — "
                "Section {{student.section}}",
                (14, 41, 150, 6),
                size=9,
                family=ETHIOPIC,
            ),
            _text(
                "year",
                "Academic year {{student.academic_year}}",
                (14, 48, 150, 6),
                size=9,
                family=ETHIOPIC,
            ),
            _text(
                "grid",
                "Subject",
                (14, 62, 60, 5),
                size=8,
                bold=True,
                colour="#6b6b6b",
                condition={"op": "exists", "field": "student.marks.subjects"},
            ),
            {
                "id": "results",
                "type": "table",
                "rect": _rect(14, 68, 182, 120),
                "table": {
                    "source": "student.marks.subjects",
                    "row_height_mm": 7,
                    "columns": [
                        {"key": "subject", "label": "Subject", "binding": "subject", "width_mm": 56},
                        {
                            "key": "total",
                            "label": "Total",
                            "binding": "total",
                            "width_mm": 22,
                            "align": "right",
                            "format": {"number_decimals": 2},
                        },
                        {
                            "key": "out_of",
                            "label": "Out of",
                            "binding": "out_of",
                            "width_mm": 22,
                            "align": "right",
                            "format": {"number_decimals": 2},
                        },
                        {
                            "key": "percent",
                            "label": "Percent",
                            "binding": "percent",
                            "width_mm": 24,
                            "align": "right",
                            "format": {"number_decimals": 2},
                        },
                        {
                            "key": "grade",
                            "label": "Grade",
                            "binding": "grade",
                            "width_mm": 18,
                            "align": "center",
                        },
                        {"key": "remark", "label": "Remark", "binding": "remark", "width_mm": 40},
                    ],
                    "summaries": [
                        {"column": "total", "aggregate": "sum", "label": "Total"},
                        {"column": "percent", "aggregate": "average", "label": "Average"},
                    ],
                },
                "style": {"font_family": ETHIOPIC, "font_size_pt": 9},
            },
            _text(
                "year_total",
                "Year total {{student.marks.year.total}} / {{student.marks.year.out_of}}",
                (14, 194, 120, 7),
                size=10,
                family=ETHIOPIC,
            ),
            _text(
                "year_grade",
                "{{student.marks.year.grade}}",
                (150, 190, 46, 14),
                size=20,
                bold=True,
                align="center",
            ),
            _text(
                "rank",
                "Rank {{student.rank}} of {{student.rank_size}}",
                (14, 204, 120, 6),
                size=9,
                family=ETHIOPIC,
            ),
            _line("signature_line", 120, 252, 70, width=0.3, colour="#9a9a9a"),
            _text("signature", "Registrar", (120, 254, 70, 5), size=8, align="center"),
            _text(
                "issued",
                "Issued {{date.issued}}",
                (14, 272, 120, 6),
                size=8,
                family=ETHIOPIC,
                format={"calendar": "both"},
            ),
            _text(
                "issuer",
                "{{document.number}}",
                (120, 272, 70, 5),
                size=8,
                align="right",
                colour="#777777",
            ),
        ],
        name="Academic transcript",
    )


def _certificate(kind: str) -> dict[str, Any]:
    celebration = kind == "certificate_completion"
    title = "Certificate of Completion" if celebration else "Certificate of Appreciation"
    lead = "has successfully completed" if celebration else "in recognition of outstanding achievement"
    detail = (
        "with a total of {{student.marks.year.percent}}%"
        if celebration
        else "and dedicated service to {{school.name}}"
    )
    recipient = "{{student.full_name}}" if celebration else "{{person.full_name}}"
    elements = [
        _shape("frame", "rect", (8, 8, 281, 194), stroke=ACCENT, stroke_width=0.8),
        _shape("inner_frame", "rect", (11, 11, 275, 188), stroke=ACCENT, stroke_width=0.25),
        _text(
            "school",
            "{{school.name}}",
            (20, 22, 257, 8),
            size=11,
            family=ETHIOPIC,
            align="center",
            spacing=1,
            colour=ACCENT,
        ),
        _text(
            "title",
            title,
            (20, 42, 257, 14),
            size=26,
            bold=True,
            align="center",
            colour=ACCENT,
        ),
        _text("lead", "This is to certify that", (20, 64, 257, 7), size=10, italic=True, align="center"),
        _text(
            "recipient",
            recipient,
            (20, 76, 257, 16),
            size=24,
            family=ETHIOPIC,
            bold=True,
            align="center",
        ),
        _text("detail", lead, (20, 96, 257, 8), size=11, align="center"),
        _text("detail_more", detail, (20, 106, 257, 7), size=9, align="center", colour="#555555"),
        _text(
            "date",
            "{{date.issued}}",
            (20, 150, 110, 6),
            size=9,
            format={"calendar": "both"},
        ),
        _line("signature_line", 150, 152, 90, width=0.3, colour="#9a9a9a"),
        _text("signature", "Principal", (150, 154, 90, 5), size=8, align="center"),
        _shape(
            "seal",
            "ellipse",
            (108, 166, 30, 30),
            stroke=ACCENT,
            stroke_width=0.5,
        ),
        _qr("verify", (255, 168, 22, 22), "{{document.verify_url}}"),
        _barcode("serial", (20, 172, 60, 12), "{{document.number}}"),
    ]
    return _layout(
        {
            "size": "A4",
            "orientation": "landscape",
            "margins_mm": {"top": 15, "right": 15, "bottom": 15, "left": 15},
            "bleed_mm": 3,
            "background_colour": "#fdfaf3",
        },
        elements,
        name=title,
    )


def _id_card() -> dict[str, Any]:
    return _layout(
        {
            "size": "custom",
            "width_mm": 85.6,
            "height_mm": 54,
            "margins_mm": {"top": 0, "right": 0, "bottom": 0, "left": 0},
            "background_colour": PAPER,
        },
        [
            _shape("band", "rect", (0, 0, 85.6, 12), fill=BRAND),
            _text(
                "school",
                "{{school.short_name}}",
                (4, 3, 58, 6),
                size=8,
                family=ETHIOPIC,
                bold=True,
                colour="#ffffff",
            ),
            _text(
                "card_type",
                "STUDENT",
                (62, 4, 20, 4),
                size=6,
                align="right",
                colour="#ffffff",
                spacing=1,
            ),
            _image("photo", (4, 16, 20, 24), "student.photo", alt="Student photograph"),
            _text(
                "name",
                "{{student.full_name}}",
                (27, 16, 54, 7),
                size=11,
                family=ETHIOPIC,
                bold=True,
            ),
            _text(
                "grade",
                "{{student.grade}} — {{student.section}}",
                (27, 24, 54, 5),
                size=8,
                family=ETHIOPIC,
            ),
            _text("number", "ID {{student.number}}", (27, 30, 34, 5), size=8),
            _text(
                "valid",
                "Valid {{date.expires}}",
                (27, 36, 34, 5),
                size=7,
                format={"calendar": "gc"},
            ),
            _qr("verify", (63, 34, 18, 18), "{{document.verify_url}}"),
            _shape("footer", "rect", (0, 50, 85.6, 4), fill=ACCENT),
        ],
        name="Student ID card",
    )


def _admission_letter() -> dict[str, Any]:
    return _layout(
        {"size": "A4", "margins_mm": {"top": 15, "right": 15, "bottom": 15, "left": 15}},
        [
            _text(
                "school",
                "{{school.name}}",
                (110, 14, 85, 8),
                size=12,
                family=ETHIOPIC,
                bold=True,
                align="right",
            ),
            _text(
                "address",
                "{{school.address}}",
                (110, 23, 85, 8),
                size=8,
                align="right",
                colour="#555555",
            ),
            _text(
                "date",
                "{{date.issued}}",
                (15, 14, 80, 6),
                size=9,
                format={"calendar": "both"},
            ),
            _line("rule", 15, 38, 180, width=0.5),
            _text("title", "Letter of Admission", (15, 46, 180, 10), size=16, bold=True),
            _text(
                "salutation",
                "Dear {{student.guardian_name}},",
                (15, 62, 180, 6),
                size=10,
                family=ETHIOPIC,
            ),
            _text(
                "body",
                "We are pleased to offer {{student.full_name}} a place in "
                "{{student.grade}} at {{school.name}} for the {{academic_year.name}} "
                "academic year. This offer is made on the basis of the entrance "
                "assessment and the documents you submitted.",
                (15, 72, 180, 36),
                size=10,
                family=ETHIOPIC,
                wrap=True,
            ),
            _text(
                "next_steps",
                "Please report to the registrar's office with this letter and the "
                "required documents before {{date.report_by}}. The first day of "
                "classes is {{date.starts}}.",
                (15, 112, 180, 30),
                size=10,
                family=ETHIOPIC,
                wrap=True,
                format={"calendar": "both"},
            ),
            _text("closing", "Sincerely,", (15, 158, 90, 6), size=10),
            _line("signature_line", 15, 184, 60, width=0.3, colour="#9a9a9a"),
            _text("signature", "Registrar", (15, 186, 60, 5), size=8),
            _text(
                "issuer",
                "{{document.number}}",
                (15, 268, 80, 5),
                size=8,
                colour="#777777",
            ),
            _qr("verify", (255, 20, 22, 22), "{{document.verify_url}}"),
        ],
        name="Admission letter",
    )


def _receipt() -> dict[str, Any]:
    return _layout(
        {"size": "A5", "margins_mm": {"top": 10, "right": 10, "bottom": 10, "left": 10}},
        [
            _shape("band", "rect", (0, 0, 148, 20), fill=BRAND),
            _text(
                "school",
                "{{school.name}}",
                (10, 5, 90, 7),
                size=12,
                family=ETHIOPIC,
                bold=True,
                colour="#ffffff",
            ),
            _text(
                "heading",
                "Payment Receipt",
                (10, 12, 90, 5),
                size=8,
                colour="#ffffff",
                spacing=1,
            ),
            _text("number", "No. {{document.number}}", (10, 26, 70, 5), size=9),
            _text(
                "date",
                "{{date.issued}}",
                (88, 26, 50, 5),
                size=9,
                align="right",
                format={"calendar": "ec"},
            ),
            _text(
                "payer",
                "Received from {{student.full_name}}",
                (10, 34, 128, 6),
                size=10,
                family=ETHIOPIC,
            ),
            {
                "id": "lines",
                "type": "table",
                "rect": _rect(10, 44, 128, 64),
                "table": {
                    "source": "fees.receipt_lines",
                    "row_height_mm": 7,
                    "columns": [
                        {
                            "key": "description",
                            "label": "Description",
                            "binding": "description",
                            "width_mm": 80,
                        },
                        {
                            "key": "amount",
                            "label": "Amount",
                            "binding": "amount",
                            "width_mm": 48,
                            "align": "right",
                            "format": {"money": "etb", "number_decimals": 2},
                        },
                    ],
                },
                "style": {"font_family": ETHIOPIC, "font_size_pt": 9},
            },
            _line("total_rule", 10, 114, 128, width=0.3, colour="#9a9a9a"),
            _text(
                "total",
                "Total {{fees.amount}}",
                (10, 116, 128, 8),
                size=12,
                bold=True,
                align="right",
                format={"money": "etb", "number_decimals": 2},
            ),
            _text(
                "method",
                "Paid by {{payment.method}}",
                (10, 128, 128, 6),
                size=9,
                family=ETHIOPIC,
            ),
            _text(
                "accountant",
                "Received by {{staff.full_name}}",
                (10, 136, 90, 6),
                size=8,
                family=ETHIOPIC,
                colour="#555555",
            ),
            _text("thanks", "Thank you.", (10, 150, 80, 6), size=8, italic=True),
            _qr("verify", (118, 148, 20, 20), "{{document.verify_url}}"),
        ],
        name="Payment receipt",
    )


def _experience_letter() -> dict[str, Any]:
    return _layout(
        {"size": "A4", "margins_mm": {"top": 15, "right": 15, "bottom": 15, "left": 15}},
        [
            _text(
                "school",
                "{{school.name}}",
                (15, 16, 180, 8),
                size=12,
                family=ETHIOPIC,
                bold=True,
                align="center",
            ),
            _text(
                "address",
                "{{school.address}}",
                (15, 25, 180, 5),
                size=8,
                align="center",
                colour="#555555",
            ),
            _line("rule", 15, 36, 180, width=0.4),
            _text(
                "title",
                "Certificate of Experience",
                (15, 46, 180, 10),
                size=16,
                bold=True,
                align="center",
            ),
            _text(
                "body",
                "This is to certify that {{staff.full_name}} has been employed at "
                "{{school.name}} as {{staff.position}} from {{staff.start_date}} to "
                "{{staff.end_date}}.",
                (15, 68, 180, 40),
                size=10,
                family=ETHIOPIC,
                wrap=True,
                format={"calendar": "both"},
            ),
            _text(
                "body_more",
                "During this period {{staff.full_name}} carried out the duties of the "
                "position diligently and professionally. We wish them success in their "
                "future work.",
                (15, 116, 180, 30),
                size=10,
                family=ETHIOPIC,
                wrap=True,
            ),
            _text(
                "date",
                "{{date.issued}}",
                (15, 168, 90, 6),
                size=9,
                format={"calendar": "both"},
            ),
            _line("signature_line", 120, 176, 70, width=0.3, colour="#9a9a9a"),
            _text("signature", "Director", (120, 178, 70, 5), size=8, align="center"),
            _shape("stamp", "ellipse", (22, 176, 26, 26), stroke=ACCENT, stroke_width=0.4),
            _text(
                "issuer",
                "{{document.number}}",
                (120, 270, 70, 5),
                size=8,
                align="right",
                colour="#777777",
            ),
        ],
        name="Experience letter",
    )


STARTERS: tuple[Starter, ...] = (
    Starter(
        key="report_card",
        doc_type="report_card",
        name_key="documents.starter.report_card.name",
        description_key="documents.starter.report_card.description",
        layout=_report_card(),
    ),
    Starter(
        key="transcript",
        doc_type="transcript",
        name_key="documents.starter.transcript.name",
        description_key="documents.starter.transcript.description",
        layout=_transcript(),
    ),
    Starter(
        key="certificate_completion",
        doc_type="certificate_completion",
        name_key="documents.starter.certificate_completion.name",
        description_key="documents.starter.certificate_completion.description",
        layout=_certificate("certificate_completion"),
    ),
    Starter(
        key="certificate_appreciation",
        doc_type="certificate_appreciation",
        name_key="documents.starter.certificate_appreciation.name",
        description_key="documents.starter.certificate_appreciation.description",
        layout=_certificate("certificate_appreciation"),
    ),
    Starter(
        key="id_card",
        doc_type="id_card",
        name_key="documents.starter.id_card.name",
        description_key="documents.starter.id_card.description",
        layout=_id_card(),
    ),
    Starter(
        key="admission_letter",
        doc_type="admission_letter",
        name_key="documents.starter.admission_letter.name",
        description_key="documents.starter.admission_letter.description",
        layout=_admission_letter(),
    ),
    Starter(
        key="receipt",
        doc_type="receipt",
        name_key="documents.starter.receipt.name",
        description_key="documents.starter.receipt.description",
        layout=_receipt(),
    ),
    Starter(
        key="experience_letter",
        doc_type="experience_letter",
        name_key="documents.starter.experience_letter.name",
        description_key="documents.starter.experience_letter.description",
        layout=_experience_letter(),
    ),
)

STARTERS_BY_KEY: dict[str, Starter] = {starter.key: starter for starter in STARTERS}


def starter_view(starter: Starter) -> dict[str, Any]:
    """The library entry the canvas shows before creating anything."""
    return {
        "key": starter.key,
        "doc_type": starter.doc_type,
        "name_key": starter.name_key,
        "description_key": starter.description_key,
        "layout": starter.layout,
    }


__all__ = ["STARTERS", "STARTERS_BY_KEY", "Starter", "starter_view"]
