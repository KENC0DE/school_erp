"""Grade scales, half-open bands and assignment resolution (P4-02).

Bands are stored as half-open ranges ``[min_value, max_value)``. The top band is
closed at the scale's ``upper_bound``. A scale must cover its whole range with
no gap and no overlap, which makes every mark map to exactly one label.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from modules.assessment.engine import Number, RoundingMode, as_decimal, round_mark


class ScaleType(StrEnum):
    NUMERIC_BANDS = "numeric_bands"
    DESCRIPTIVE = "descriptive"


class ScaleContext(StrEnum):
    ASSESSMENT = "assessment"
    SUBJECT = "subject"
    LEVEL = "level"
    STAGE = "stage"
    DEFAULT = "default"


@dataclass(frozen=True)
class Band:
    """One grade band; ``max_value`` is exclusive except for the top band."""

    min_value: Number
    max_value: Number
    label: str
    remark: str | None = None
    gpa_points: Number | None = None
    is_pass: bool = True
    color: str | None = None

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise ValueError("band label is required")
        if as_decimal(self.min_value, name="min_value") >= as_decimal(self.max_value, name="max_value"):
            raise ValueError("band min_value must be less than max_value")
        if self.gpa_points is not None and as_decimal(self.gpa_points, name="gpa_points") < 0:
            raise ValueError("gpa_points cannot be negative")


@dataclass(frozen=True)
class GradeScale:
    name: str
    bands: Sequence[Band]
    type: ScaleType = ScaleType.NUMERIC_BANDS
    version: int = 1
    is_default: bool = False
    lower_bound: Number = 0
    upper_bound: Number = 100
    rounding: RoundingMode = RoundingMode.HALF_UP
    precision: int = 2
    effective_from: date | None = None
    effective_to: date | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("scale name is required")
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise TypeError("version must be an integer")
        if self.version < 1:
            raise ValueError("version must be at least 1")
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValueError("effective_from cannot be after effective_to")

    def is_effective(self, at: date | None) -> bool:
        if at is None:
            return True
        if self.effective_from and at < self.effective_from:
            return False
        if self.effective_to and at > self.effective_to:
            return False
        return True


@dataclass(frozen=True)
class GradeResult:
    value: Number
    label: str
    band: Band
    scale_name: str
    scale_version: int
    gpa_points: Number | None = None
    is_pass: bool = True
    remark: str | None = None
    color: str | None = None


@dataclass(frozen=True)
class ScaleAssignment:
    """Attach a scale version to one context (assessment, subject, …)."""

    context: ScaleContext
    scale: GradeScale
    key: str | None = None

    def __post_init__(self) -> None:
        if self.context is ScaleContext.DEFAULT:
            if self.key is not None:
                raise ValueError("the default assignment cannot have a key")
        elif not self.key or not self.key.strip():
            raise ValueError(f"{self.context.value} assignments need a key")


def validate_scale(scale: GradeScale) -> GradeScale:
    """Validate coverage, ordering and band values; return the scale."""
    if not scale.bands:
        raise ValueError("a grade scale needs at least one band")

    lower = as_decimal(scale.lower_bound, name="lower_bound")
    upper = as_decimal(scale.upper_bound, name="upper_bound")
    if lower >= upper:
        raise ValueError("lower_bound must be less than upper_bound")

    mins = [as_decimal(band.min_value, name="min_value") for band in scale.bands]
    if mins != sorted(mins):
        raise ValueError("bands must be sorted by min_value")
    if len(set(mins)) != len(mins):
        raise ValueError("bands cannot share the same min_value")

    first = as_decimal(scale.bands[0].min_value, name="min_value")
    if first != lower:
        raise ValueError("the first band must start at lower_bound")

    previous_max = None
    for band in scale.bands:
        band_min = as_decimal(band.min_value, name="min_value")
        band_max = as_decimal(band.max_value, name="max_value")
        if band_max > upper:
            raise ValueError("a band cannot extend past upper_bound")
        if previous_max is None:
            if band_min != lower:
                raise ValueError("the first band must start at lower_bound")
        elif band_min != previous_max:
            if band_min < previous_max:
                raise ValueError("bands overlap")
            raise ValueError("bands leave a gap")
        previous_max = band_max

    if previous_max != upper:
        raise ValueError("the last band must end at upper_bound")
    return scale


def resolve_band(scale: GradeScale, value: Number) -> Band:
    """Resolve a mark to exactly one band using half-open ranges."""
    validate_scale(scale)
    number = as_decimal(value)
    lower = as_decimal(scale.lower_bound, name="lower_bound")
    upper = as_decimal(scale.upper_bound, name="upper_bound")
    if number < lower or number > upper:
        raise ValueError("value is outside the grade scale range")

    for index, band in enumerate(scale.bands):
        band_min = as_decimal(band.min_value, name="min_value")
        band_max = as_decimal(band.max_value, name="max_value")
        is_top = index == len(scale.bands) - 1
        if band_min <= number < band_max or (is_top and number == band_max):
            return band
    raise ValueError("value did not match any band")  # defensive; validated above


def grade_for(scale: GradeScale, value: Number) -> GradeResult:
    """Resolve a mark and return the full label record."""
    band = resolve_band(scale, value)
    return GradeResult(
        value=value,
        label=band.label,
        band=band,
        scale_name=scale.name,
        scale_version=scale.version,
        gpa_points=band.gpa_points,
        is_pass=band.is_pass,
        remark=band.remark,
        color=band.color,
    )


def display_value(scale: GradeScale, value: Number) -> str:
    """Format a mark for display; resolution itself always uses the exact value."""
    rounded = round_mark(value, precision=scale.precision, rounding=scale.rounding)
    return f"{rounded:f}"


def _latest(assignments: Sequence[ScaleAssignment]) -> GradeScale:
    ordered = sorted(
        assignments,
        key=lambda item: (
            item.scale.effective_from or date.min,
            item.scale.version,
            item.scale.name,
        ),
    )
    latest = ordered[-1].scale
    tied = [
        item.scale
        for item in ordered
        if item.scale.effective_from == latest.effective_from
        and item.scale.version == latest.version
        and item.scale.name != latest.name
    ]
    if tied:
        raise ValueError("ambiguous grade scale assignment for this context and date")
    return latest


def resolve_scale(
    assignments: Sequence[ScaleAssignment],
    *,
    assessment_id: str | None = None,
    subject_id: str | None = None,
    level_id: str | None = None,
    stage_id: str | None = None,
    at: date | None = None,
) -> GradeScale | None:
    """Pick the most specific effective scale: assessment > subject > level > stage > default."""
    requested: dict[ScaleContext, str | None] = {
        ScaleContext.ASSESSMENT: assessment_id,
        ScaleContext.SUBJECT: subject_id,
        ScaleContext.LEVEL: level_id,
        ScaleContext.STAGE: stage_id,
    }
    for context in (
        ScaleContext.ASSESSMENT,
        ScaleContext.SUBJECT,
        ScaleContext.LEVEL,
        ScaleContext.STAGE,
    ):
        key = requested[context]
        if key is None:
            continue
        matches = [
            item
            for item in assignments
            if item.context is context and item.key == key and item.scale.is_effective(at)
        ]
        if matches:
            return _latest(matches)

    defaults = [
        item for item in assignments if item.context is ScaleContext.DEFAULT and item.scale.is_effective(at)
    ]
    return _latest(defaults) if defaults else None


__all__ = [
    "Band",
    "GradeResult",
    "GradeScale",
    "ScaleAssignment",
    "ScaleContext",
    "ScaleType",
    "display_value",
    "grade_for",
    "resolve_band",
    "resolve_scale",
    "validate_scale",
]
