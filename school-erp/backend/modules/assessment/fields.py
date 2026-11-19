"""Assessment document fields for Document Studio (P4-17).

Report cards bind a published student result, so every field here describes a
value that already came from a ``ResultSnapshot``. The keys are stable: a
template saved today still resolves after a grade scale or structure changes,
because the snapshot carries its own scale and structure versions.
"""

from __future__ import annotations

from core.documents.fields import DocumentField

FIELDS: tuple[DocumentField, ...] = (
    DocumentField(
        "student.marks.term.total",
        "assessment.field.marks_term_total",
        "decimal",
        sample="35.69",
    ),
    DocumentField(
        "student.marks.term.out_of",
        "assessment.field.marks_term_out_of",
        "decimal",
        sample="50",
    ),
    DocumentField(
        "student.marks.term.percent",
        "assessment.field.marks_term_percent",
        "decimal",
        sample="71.38",
    ),
    DocumentField(
        "student.marks.term.grade",
        "assessment.field.marks_term_grade",
        "text",
        sample="C+",
    ),
    DocumentField(
        "student.marks.term.remark",
        "assessment.field.marks_term_remark",
        "text",
        sample="Good",
    ),
    DocumentField(
        "student.marks.term.gpa",
        "assessment.field.marks_term_gpa",
        "decimal",
        sample="2.5",
    ),
    DocumentField(
        "student.marks.term.pass",
        "assessment.field.marks_term_pass",
        "boolean",
        sample=True,
    ),
    DocumentField(
        "student.marks.year.total",
        "assessment.field.marks_year_total",
        "decimal",
        sample="72.4",
    ),
    DocumentField(
        "student.marks.year.out_of",
        "assessment.field.marks_year_out_of",
        "decimal",
        sample="100",
    ),
    DocumentField(
        "student.marks.year.percent",
        "assessment.field.marks_year_percent",
        "decimal",
        sample="72.4",
    ),
    DocumentField(
        "student.marks.year.grade",
        "assessment.field.marks_year_grade",
        "text",
        sample="B",
    ),
    DocumentField(
        "student.marks.subjects",
        "assessment.field.marks_subjects",
        "table",
        sample=[
            {
                "subject": "Mathematics",
                "classwork": "8.5",
                "test": "15",
                "final": "60.25",
                "total": "83.75",
                "out_of": "100",
                "percent": "83.75",
                "grade": "A",
                "remark": "Excellent",
                "rank": "1",
            },
            {
                "subject": "English",
                "classwork": "7",
                "test": "12",
                "final": "51",
                "total": "70",
                "out_of": "100",
                "percent": "70",
                "grade": "B",
                "remark": "Good",
                "rank": "2",
            },
            {
                "subject": "Science",
                "classwork": "8",
                "test": "14",
                "final": "55.5",
                "total": "77.5",
                "out_of": "100",
                "percent": "77.5",
                "grade": "B+",
                "remark": "Very good",
                "rank": "2",
            },
        ],
    ),
    DocumentField(
        "student.rank",
        "assessment.field.rank",
        "integer",
        sample=1,
    ),
    DocumentField(
        "student.rank_size",
        "assessment.field.rank_size",
        "integer",
        sample=30,
    ),
)


__all__ = ["FIELDS"]
