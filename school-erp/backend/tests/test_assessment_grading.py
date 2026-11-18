"""P4-02: grade bands, boundary resolution, descriptive scales and assignments."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from modules.assessment.grading import (
    Band,
    GradeScale,
    ScaleAssignment,
    ScaleContext,
    ScaleType,
    display_value,
    grade_for,
    resolve_band,
    resolve_scale,
    validate_scale,
)


def default_scale(
    *,
    name: str = "Default",
    version: int = 1,
    type: ScaleType = ScaleType.NUMERIC_BANDS,
    effective_from: date | None = None,
    effective_to: date | None = None,
) -> GradeScale:
    return GradeScale(
        name=name,
        version=version,
        type=type,
        effective_from=effective_from,
        effective_to=effective_to,
        bands=(
            Band(0, 75, "D", gpa_points=1, is_pass=False, color="danger"),
            Band(75, 85, "C+", gpa_points=Decimal("2.5"), remark="Satisfactory", color="warning"),
            Band(85, 90, "A", gpa_points=Decimal("3.75")),
            Band(90, 100, "A+", gpa_points=4),
        ),
    )


def test_half_open_band_boundaries_are_exact():
    scale = default_scale()
    assert resolve_band(scale, Decimal("0")).label == "D"
    assert resolve_band(scale, Decimal("74.99")).label == "D"
    assert resolve_band(scale, Decimal("75")).label == "C+"
    assert resolve_band(scale, Decimal("84.999")).label == "C+"
    assert resolve_band(scale, Decimal("85")).label == "A"
    assert resolve_band(scale, Decimal("89.99")).label == "A"
    assert resolve_band(scale, Decimal("90")).label == "A+"
    assert resolve_band(scale, Decimal("100")).label == "A+"


def test_values_outside_the_scale_are_rejected():
    scale = default_scale()
    with pytest.raises(ValueError, match="outside"):
        resolve_band(scale, Decimal("-0.01"))
    with pytest.raises(ValueError, match="outside"):
        resolve_band(scale, Decimal("100.01"))


def test_grade_result_carries_label_metadata():
    result = grade_for(default_scale(), Decimal("80"))
    assert result.label == "C+"
    assert result.gpa_points == Decimal("2.5")
    assert result.is_pass is True
    assert result.remark == "Satisfactory"
    assert result.color == "warning"
    assert result.scale_name == "Default"
    assert result.scale_version == 1

    failed = grade_for(default_scale(), Decimal("10"))
    assert failed.label == "D"
    assert failed.is_pass is False


def test_display_rounding_never_changes_the_resolved_band():
    scale = GradeScale(
        name="Default",
        precision=1,
        bands=(
            Band(0, 75, "D"),
            Band(75, 100, "C+"),
        ),
    )
    assert display_value(scale, Decimal("74.99")) == "75.0"
    assert grade_for(scale, Decimal("74.99")).label == "D"


def test_descriptive_scales_still_resolve_through_thresholds():
    scale = default_scale(type=ScaleType.DESCRIPTIVE, name="Lower primary")
    assert grade_for(scale, Decimal("49.9")).label == "D"
    assert grade_for(scale, Decimal("50")).label == "D"
    assert grade_for(scale, Decimal("75")).label == "C+"
    assert scale.type is ScaleType.DESCRIPTIVE


def test_validate_scale_rejects_empty_unsorted_gappy_and_overlapping_bands():
    with pytest.raises(ValueError, match="at least one band"):
        validate_scale(GradeScale(name="Empty", bands=()))

    with pytest.raises(ValueError, match="sorted"):
        validate_scale(
            GradeScale(
                name="Unsorted",
                bands=(Band(75, 100, "B"), Band(0, 75, "A")),
            )
        )

    with pytest.raises(ValueError, match="first band"):
        validate_scale(
            GradeScale(
                name="Late start",
                bands=(Band(5, 100, "A"),),
            )
        )

    with pytest.raises(ValueError, match="last band"):
        validate_scale(
            GradeScale(
                name="Short",
                bands=(Band(0, 90, "A"),),
            )
        )

    with pytest.raises(ValueError, match="gap"):
        validate_scale(
            GradeScale(
                name="Gap",
                bands=(Band(0, 70, "A"), Band(75, 100, "B")),
            )
        )

    with pytest.raises(ValueError, match="overlap"):
        validate_scale(
            GradeScale(
                name="Overlap",
                bands=(Band(0, 80, "A"), Band(70, 100, "B")),
            )
        )


def test_validate_scale_rejects_bad_limits_and_band_values():
    with pytest.raises(ValueError, match="lower_bound"):
        validate_scale(
            GradeScale(
                name="Bad range",
                lower_bound=100,
                upper_bound=0,
                bands=(Band(0, 100, "A"),),
            )
        )

    with pytest.raises(ValueError, match="past upper_bound"):
        validate_scale(
            GradeScale(
                name="Too high",
                upper_bound=90,
                bands=(Band(0, 100, "A"),),
            )
        )

    with pytest.raises(ValueError, match="less than max_value"):
        Band(80, 80, "A")

    with pytest.raises(ValueError, match="gpa_points"):
        Band(0, 100, "A", gpa_points=-1)

    with pytest.raises(ValueError, match="label"):
        Band(0, 100, " ")


def test_scale_versions_and_effective_dates():
    v1 = default_scale(name="Default", version=1, effective_from=date(2024, 1, 1))
    v2 = default_scale(name="Default", version=2, effective_from=date(2025, 9, 1))

    assert v1.is_effective(date(2023, 12, 31)) is False
    assert v1.is_effective(date(2024, 1, 1)) is True
    assert v2.is_effective(date(2025, 9, 1)) is True
    assert v1.is_effective(None) is True


def test_assignments_pick_the_most_specific_context():
    assessment = default_scale(name="Assessment", version=3)
    subject = default_scale(name="Subject", version=2)
    level = default_scale(name="Level", version=1)
    stage = default_scale(name="Stage", version=1)
    fallback = default_scale(name="School default", version=1)

    assignments = (
        ScaleAssignment(ScaleContext.DEFAULT, fallback),
        ScaleAssignment(ScaleContext.STAGE, stage, key="stage-1"),
        ScaleAssignment(ScaleContext.LEVEL, level, key="level-1"),
        ScaleAssignment(ScaleContext.SUBJECT, subject, key="subject-1"),
        ScaleAssignment(ScaleContext.ASSESSMENT, assessment, key="assessment-1"),
    )

    assert (
        resolve_scale(
            assignments,
            assessment_id="assessment-1",
            subject_id="subject-1",
            level_id="level-1",
            stage_id="stage-1",
        ).name
        == "Assessment"
    )
    assert (
        resolve_scale(
            assignments,
            subject_id="subject-1",
            level_id="level-1",
            stage_id="stage-1",
        ).name
        == "Subject"
    )
    assert resolve_scale(assignments, level_id="level-1", stage_id="stage-1").name == "Level"
    assert resolve_scale(assignments, stage_id="stage-1").name == "Stage"
    assert resolve_scale(assignments).name == "School default"
    assert resolve_scale(assignments, assessment_id="other").name == "School default"
    assert resolve_scale(()) is None


def test_assignments_skip_inactive_scales_and_pick_the_latest_version():
    v1 = default_scale(name="Subject", version=1, effective_from=date(2024, 1, 1))
    v2 = default_scale(name="Subject", version=2, effective_from=date(2025, 1, 1))
    fallback = default_scale(name="Default", version=1)

    assignments = (
        ScaleAssignment(ScaleContext.SUBJECT, v1, key="subject-1"),
        ScaleAssignment(ScaleContext.SUBJECT, v2, key="subject-1"),
        ScaleAssignment(ScaleContext.DEFAULT, fallback),
    )

    assert resolve_scale(assignments, subject_id="subject-1", at=date(2024, 6, 1)).version == 1
    assert resolve_scale(assignments, subject_id="subject-1", at=date(2025, 6, 1)).version == 2
    assert resolve_scale(assignments, subject_id="subject-1", at=date(2023, 6, 1)).name == "Default"


def test_ambiguous_assignments_and_bad_assignment_keys_are_rejected():
    first = default_scale(name="First", version=1, effective_from=date(2024, 1, 1))
    second = default_scale(name="Second", version=1, effective_from=date(2024, 1, 1))
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_scale(
            (
                ScaleAssignment(ScaleContext.SUBJECT, first, key="subject-1"),
                ScaleAssignment(ScaleContext.SUBJECT, second, key="subject-1"),
            ),
            subject_id="subject-1",
            at=date(2024, 6, 1),
        )

    with pytest.raises(ValueError, match="default assignment"):
        ScaleAssignment(ScaleContext.DEFAULT, first, key="nope")
    with pytest.raises(ValueError, match="need a key"):
        ScaleAssignment(ScaleContext.SUBJECT, first)
