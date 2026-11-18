"""HTTP and action schemas for assessment structures and marks.

Marks cross the API as decimal strings ("8.5") rather than JSON numbers, so a
client can never introduce a binary rounding error. Inputs also accept an
integer or a numeric string and are parsed to :class:`~decimal.Decimal`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

ScopeType = Literal["school", "stage", "level", "subject"]
Aggregation = Literal["average", "weighted_average", "best_n", "sum_capped", "latest"]
YearMode = Literal["average", "sum", "weighted_average"]
Rounding = Literal["half_up", "half_even", "half_down", "up", "down", "ceiling", "floor"]
ScoreStatus = Literal["present", "absent", "excused", "exempt", "not_taken"]
AssessmentStatus = Literal["active", "archived"]

Mark = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=6)]
PositiveMark = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=6)]


class ComponentInput(BaseModel):
    """One component of a mark structure, sent by the structure editor."""

    id: uuid.UUID | None = None
    key: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    max_points: Mark = Field(gt=0)
    aggregation: Aggregation = "average"
    absent_counts_as_zero: bool = False
    best_n: int | None = Field(default=None, ge=1, le=100)
    cap: Mark | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool = True

    @model_validator(mode="after")
    def _mode_arguments(self) -> ComponentInput:
        if self.aggregation == "best_n" and self.best_n is None:
            raise ValueError("best_n aggregation needs a count")
        if self.aggregation != "best_n" and self.best_n is not None:
            raise ValueError("best_n only applies to best_n aggregation")
        if self.aggregation == "sum_capped" and self.cap is None:
            raise ValueError("sum_capped aggregation needs a cap")
        if self.aggregation != "sum_capped" and self.cap is not None:
            raise ValueError("cap only applies to sum_capped aggregation")
        return self


class ComponentOut(BaseModel):
    id: str
    key: str
    name: str
    name_am: str | None = None
    max_points: str
    aggregation: str
    absent_counts_as_zero: bool
    best_n: int | None = None
    cap: str | None = None
    sort_order: int
    is_active: bool
    row_version: int


class StructureCreate(BaseModel):
    year_id: uuid.UUID
    scope_type: ScopeType = "school"
    level_id: uuid.UUID | None = None
    stage_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    term_system: str | None = Field(default=None, max_length=20)
    year_mode: YearMode = "average"
    year_weights: list[Mark] | None = None
    precision: int = Field(default=2, ge=0, le=6)
    rounding: Rounding = "half_up"
    intended_total: Mark | None = Decimal(100)
    descriptive_mode: bool = False
    notes: str | None = Field(default=None, max_length=1000)
    components: list[ComponentInput] = Field(min_length=1)

    @model_validator(mode="after")
    def _scope(self) -> StructureCreate:
        _check_scope(self)
        _check_year_mode(self.year_mode, self.year_weights)
        return self


class StructureUpdate(BaseModel):
    row_version: int = Field(ge=1)
    scope_type: ScopeType | None = None
    level_id: uuid.UUID | None = None
    stage_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    name_am: str | None = Field(default=None, max_length=120)
    year_mode: YearMode | None = None
    year_weights: list[Mark] | None = None
    precision: int | None = Field(default=None, ge=0, le=6)
    rounding: Rounding | None = None
    intended_total: Mark | None = None
    descriptive_mode: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)
    reason: str | None = Field(default=None, max_length=500)
    components: list[ComponentInput] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _scope_fields(self) -> StructureUpdate:
        if self.scope_type is not None:
            _check_scope(self)
        if self.year_mode is not None:
            _check_year_mode(self.year_mode, self.year_weights)
        return self


class StructureOut(BaseModel):
    id: str
    year_id: str
    year_code: str
    scope_type: str
    scope_key: str
    level_id: str | None = None
    level_name: str | None = None
    stage_id: str | None = None
    stage_name: str | None = None
    subject_id: str | None = None
    subject_name: str | None = None
    name: str
    name_am: str | None = None
    term_system: str
    year_mode: str
    year_weights: list[str] | None = None
    precision: int
    rounding: str
    intended_total: str | None = None
    total: str
    total_matches: bool
    descriptive_mode: bool
    version: int
    is_active: bool
    row_version: int
    components: list[ComponentOut] = Field(default_factory=list)


class StructureQuery(BaseModel):
    year_id: uuid.UUID | None = None
    scope_type: ScopeType | None = None
    level_id: uuid.UUID | None = None
    stage_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    limit: int = Field(default=25, ge=1, le=200)
    cursor: str | None = Field(default=None, max_length=1000)
    sort: str | None = Field(default=None, max_length=60)
    order: Literal["asc", "desc"] = "desc"


class StructureList(BaseModel):
    items: list[StructureOut]
    next_cursor: str | None = None
    total: int | None = None


class StructureImpactRequest(BaseModel):
    """Proposed component maxima for a dry-run impact calculation."""

    components: list[ComponentInput] | None = None


class ImpactSample(BaseModel):
    score_id: str
    student_id: str
    raw: str | None = None
    out_of: str
    before: str | None = None
    after: str | None = None


class StructureImpact(BaseModel):
    structure_id: str
    assessments: int
    scores: int
    students: int
    changed: int
    recalculation_required: bool
    total_before: str
    total_after: str
    samples: list[ImpactSample] = Field(default_factory=list)


class RecalculationResult(BaseModel):
    structure_id: str
    assessments: int
    scores: int
    changed: int
    job_id: str | None = None


class StructureUpdateResult(BaseModel):
    structure: StructureOut
    recalculation_job_id: str | None = None
    changed_scores: int = 0


class AssessmentCreate(BaseModel):
    """One test, quiz or exam inside a structure component."""

    year_id: uuid.UUID
    term_id: uuid.UUID
    section_id: uuid.UUID
    subject_id: uuid.UUID
    structure_id: uuid.UUID | None = None
    component_key: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    title: str = Field(min_length=1, max_length=160)
    title_am: str | None = Field(default=None, max_length=160)
    assessment_date: date
    out_of: PositiveMark
    weight: PositiveMark | None = None
    allow_bonus: bool = False
    notes: str | None = Field(default=None, max_length=1000)


class AssessmentUpdate(BaseModel):
    row_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    title_am: str | None = Field(default=None, max_length=160)
    assessment_date: date | None = None
    # ``out_of`` may only change while no student has a score: the value is
    # copied onto every score, so editing it later would reinterpret history.
    out_of: PositiveMark | None = None
    weight: PositiveMark | None = None
    allow_bonus: bool | None = None
    status: AssessmentStatus | None = None
    notes: str | None = Field(default=None, max_length=1000)
    reason: str | None = Field(default=None, max_length=500)


class AssessmentOut(BaseModel):
    id: str
    year_id: str
    year_code: str
    term_id: str
    term_name: str
    section_id: str
    section_code: str
    level_id: str
    level_name: str
    subject_id: str
    subject_name: str
    structure_id: str | None = None
    component_id: str
    component_key: str
    component_name: str
    component_max_points: str
    title: str
    title_am: str | None = None
    assessment_date: date
    out_of: str
    weight: str | None = None
    allow_bonus: bool
    status: str
    notes: str | None = None
    scores: int
    entered: int
    row_version: int


class AssessmentQuery(BaseModel):
    year_id: uuid.UUID | None = None
    term_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    component_id: uuid.UUID | None = None
    status: AssessmentStatus | None = None
    limit: int = Field(default=25, ge=1, le=200)
    cursor: str | None = Field(default=None, max_length=1000)
    sort: str | None = Field(default=None, max_length=60)
    order: Literal["asc", "desc"] = "desc"


class AssessmentList(BaseModel):
    items: list[AssessmentOut]
    next_cursor: str | None = None
    total: int | None = None


class ScoreInput(BaseModel):
    """One student's raw score in a bulk entry request."""

    student_id: uuid.UUID
    raw_score: Mark | None = None
    status: ScoreStatus = "present"
    note: str | None = Field(default=None, max_length=500)
    # Optional optimistic-concurrency guard for a row the grid already read.
    row_version: int | None = Field(default=None, ge=1)


class ScoreBulkInput(BaseModel):
    items: list[ScoreInput] = Field(min_length=1, max_length=500)
    reason: str | None = Field(default=None, max_length=500)


class ScoreOut(BaseModel):
    score_id: str | None = None
    student_id: str
    student_number: str
    student_name: str
    student_name_am: str | None = None
    roll_number: str | None = None
    enrolled: bool = True
    raw_score: str | None = None
    out_of: str
    status: str
    converted: str | None = None
    note: str | None = None
    row_version: int | None = None
    entered_at: datetime | None = None


class ScoreStats(BaseModel):
    total: int
    entered: int
    missing: int
    present: int
    absent: int
    excused: int
    exempt: int
    not_taken: int
    out_of: str
    component_max_points: str
    average_converted: str | None = None
    average_percent: str | None = None
    highest_converted: str | None = None
    lowest_converted: str | None = None


class ScoreSheet(BaseModel):
    assessment_id: str
    title: str
    component_key: str
    component_max_points: str
    out_of: str
    allow_bonus: bool
    editable: bool
    items: list[ScoreOut] = Field(default_factory=list)
    stats: ScoreStats


class ScoreBulkResult(BaseModel):
    sheet: ScoreSheet
    created: int
    updated: int
    unchanged: int


def _check_scope(payload: StructureCreate | StructureUpdate) -> None:
    targets = {
        "level": payload.level_id,
        "stage": payload.stage_id,
        "subject": payload.subject_id,
    }
    chosen = [name for name, value in targets.items() if value is not None]
    if payload.scope_type == "school":
        if chosen:
            raise ValueError("a school-wide structure cannot name a level, stage or subject")
        return
    if chosen != [payload.scope_type]:
        raise ValueError(f"a {payload.scope_type}-scoped structure needs exactly that target")


def _check_year_mode(mode: str, weights: list[Decimal] | None) -> None:
    if mode == "weighted_average" and not weights:
        raise ValueError("weighted_average needs one weight per term")
    if mode != "weighted_average" and weights:
        raise ValueError("year weights only apply to weighted_average")


__all__ = [
    "Aggregation",
    "AssessmentCreate",
    "AssessmentList",
    "AssessmentOut",
    "AssessmentQuery",
    "AssessmentStatus",
    "AssessmentUpdate",
    "ComponentInput",
    "ComponentOut",
    "ImpactSample",
    "Mark",
    "PositiveMark",
    "RecalculationResult",
    "Rounding",
    "ScopeType",
    "ScoreBulkInput",
    "ScoreBulkResult",
    "ScoreInput",
    "ScoreOut",
    "ScoreSheet",
    "ScoreStats",
    "ScoreStatus",
    "StructureCreate",
    "StructureImpact",
    "StructureImpactRequest",
    "StructureList",
    "StructureOut",
    "StructureQuery",
    "StructureUpdate",
    "StructureUpdateResult",
    "YearMode",
]
