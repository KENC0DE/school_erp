"""Assessment data model: structures, marks, grade rules and results (ARCH §9.5).

Marks are exact decimals. They are stored as integer micro-units in a BIGINT
(``Mark`` below), never as a SQL float, so a binary rounding error cannot enter
a raw score, a converted value or a grade boundary. Services and the pure engine
keep working with ``Decimal``; this module is the only place that knows about
the storage representation.

Every mutable table is a :class:`~core.db.base.BusinessModel`: soft deletes,
row versions and actor columns come for free, and live-row unique indexes use
partial indexes so a deleted record never blocks its replacement.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from core.db.base import BusinessModel, JSONType
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from modules.assessment.engine import Number, as_decimal

LIVE_INDEX = {
    "sqlite_where": text("deleted_at IS NULL"),
    "postgresql_where": text("deleted_at IS NULL"),
}

# Six decimal places is the engine's MAX_PRECISION, so one micro-unit is the
# smallest value any rule can produce.
MARK_SCALE = 1_000_000
MARK_QUANTUM = Decimal("0.000001")


class Mark(TypeDecorator[Decimal]):
    """Exact decimal marks stored as signed integer micro-units."""

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value: Number | None, dialect: object) -> int | None:
        if value is None:
            return None
        number = as_decimal(value, name="mark")
        quantized = number.quantize(MARK_QUANTUM, rounding=ROUND_HALF_UP)
        return int(quantized * MARK_SCALE)

    def process_result_value(self, value: int | None, dialect: object) -> Decimal | None:
        if value is None:
            return None
        return (Decimal(int(value)) / MARK_SCALE).quantize(MARK_QUANTUM)


class AssessmentStructure(BusinessModel):
    """The mark structure a year uses for one scope.

    A structure is chosen per school, stage, level or subject. ``scope_key`` is
    the deterministic key used by a unique live index (``school``,
    ``stage:<id>``, ``level:<id>``, ``subject:<id>``), because SQL unique
    indexes treat NULLs as distinct and the nullable FK columns alone cannot
    prevent a duplicate school-wide structure.
    """

    __tablename__ = "assessment_structures"
    __table_args__ = (
        Index(
            "uq_assessment_structures_year_scope_live",
            "year_id",
            "scope_key",
            unique=True,
            **LIVE_INDEX,
        ),
        Index("ix_assessment_structures_year_type", "year_id", "scope_type"),
        Index("ix_assessment_structures_level", "level_id"),
        Index("ix_assessment_structures_stage", "stage_id"),
        Index("ix_assessment_structures_subject", "subject_id"),
    )

    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, default="school")
    scope_key: Mapped[str] = mapped_column(String(80), nullable=False)
    level_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_grade_levels.id", ondelete="SET NULL"),
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_stages.id", ondelete="SET NULL"),
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_subjects.id", ondelete="SET NULL"),
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(120))
    # Snapshot of the year's term system; changing the setting later must not
    # rewrite a year that already carries marks.
    term_system: Mapped[str] = mapped_column(String(20), nullable=False)
    year_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="average")
    # Weights for ``weighted_average`` are decimal strings, never floats.
    year_weights: Mapped[list[str] | None] = mapped_column(JSONType)
    precision: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    rounding: Mapped[str] = mapped_column(String(20), nullable=False, default="half_up")
    intended_total: Mapped[Decimal | None] = mapped_column(Mark)
    descriptive_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)


class AssessmentComponent(BusinessModel):
    """One weighted part of a structure, such as quizzes or the final exam."""

    __tablename__ = "assessment_components"
    __table_args__ = (
        Index(
            "uq_assessment_components_structure_key_live",
            "structure_id",
            "key",
            unique=True,
            **LIVE_INDEX,
        ),
        Index("ix_assessment_components_structure_sort", "structure_id", "sort_order"),
    )

    structure_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_structures.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(120))
    max_points: Mapped[Decimal] = mapped_column(Mark, nullable=False)
    aggregation: Mapped[str] = mapped_column(String(20), nullable=False, default="average")
    absent_counts_as_zero: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    best_n: Mapped[int | None] = mapped_column(Integer)
    cap: Mapped[Decimal | None] = mapped_column(Mark)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)


class GradeScale(BusinessModel):
    """A named set of bands, versioned so a published result stays reproducible."""

    __tablename__ = "assessment_grade_scales"
    __table_args__ = (
        Index(
            "uq_assessment_grade_scales_name_version_live",
            "name",
            "version",
            unique=True,
            **LIVE_INDEX,
        ),
        # Exactly one live default scale. Partial indexes are supported by both
        # SQLite and PostgreSQL.
        Index(
            "uq_assessment_grade_scales_default_live",
            "is_default",
            unique=True,
            sqlite_where=text("is_default = 1 AND deleted_at IS NULL"),
            postgresql_where=text("is_default = TRUE AND deleted_at IS NULL"),
        ),
        Index("ix_assessment_grade_scales_effective", "effective_from", "effective_to"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="numeric_bands")
    description: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lower_bound: Mapped[Decimal] = mapped_column(Mark, nullable=False, default=Decimal(0))
    upper_bound: Mapped[Decimal] = mapped_column(Mark, nullable=False, default=Decimal(100))
    precision: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    rounding: Mapped[str] = mapped_column(String(20), nullable=False, default="half_up")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)


class GradeBand(BusinessModel):
    """One half-open grade band ``[min_value, max_value)``; the top one closes."""

    __tablename__ = "assessment_grade_bands"
    __table_args__ = (
        Index(
            "uq_assessment_grade_bands_scale_min_live",
            "scale_id",
            "min_value",
            unique=True,
            **LIVE_INDEX,
        ),
        Index("ix_assessment_grade_bands_scale_sort", "scale_id", "sort_order"),
    )

    scale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_grade_scales.id", ondelete="CASCADE"),
        nullable=False,
    )
    min_value: Mapped[Decimal] = mapped_column(Mark, nullable=False)
    max_value: Mapped[Decimal] = mapped_column(Mark, nullable=False)
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))
    gpa_points: Mapped[Decimal | None] = mapped_column(Mark)
    is_pass: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    color: Mapped[str | None] = mapped_column(String(30))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Assessment(BusinessModel):
    """One test, quiz or exam a teacher creates for a section and subject."""

    __tablename__ = "assessment_assessments"
    __table_args__ = (
        Index(
            "ix_assessment_assessments_scope_date",
            "year_id",
            "term_id",
            "section_id",
            "subject_id",
            "assessment_date",
        ),
        Index("ix_assessment_assessments_component", "component_id"),
        Index("ix_assessment_assessments_subject", "subject_id"),
    )

    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_terms.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    structure_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_structures.id", ondelete="SET NULL"),
    )
    component_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_components.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    title_am: Mapped[str | None] = mapped_column(String(160))
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False)
    # ``out_of`` is copied onto every score so a later edit to the assessment
    # cannot silently reinterpret historical raw values.
    out_of: Mapped[Decimal] = mapped_column(Mark, nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Mark)
    allow_bonus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text)


class Score(BusinessModel):
    """A raw score for one student on one assessment; ``converted`` is derived."""

    __tablename__ = "assessment_scores"
    __table_args__ = (
        Index(
            "uq_assessment_scores_assessment_student_live",
            "assessment_id",
            "student_id",
            unique=True,
            **LIVE_INDEX,
        ),
        Index("ix_assessment_scores_student", "student_id"),
        Index("ix_assessment_scores_assessment_status", "assessment_id", "status"),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    raw_score: Mapped[Decimal | None] = mapped_column(Mark)
    out_of: Mapped[Decimal] = mapped_column(Mark, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="present")
    converted: Mapped[Decimal | None] = mapped_column(Mark)
    note: Mapped[str | None] = mapped_column(String(500))
    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    entered_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class CorrectionRequest(BusinessModel):
    """A post-lock change request carrying the old and proposed values."""

    __tablename__ = "assessment_correction_requests"
    __table_args__ = (
        Index("ix_assessment_correction_requests_status", "status"),
        Index("ix_assessment_correction_requests_score", "score_id"),
        Index("ix_assessment_correction_requests_scope", "year_id", "term_id", "section_id"),
    )

    score_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_scores.id", ondelete="CASCADE"),
        nullable=False,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_terms.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    old_raw: Mapped[Decimal | None] = mapped_column(Mark)
    new_raw: Mapped[Decimal | None] = mapped_column(Mark)
    old_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str | None] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decision_note: Mapped[str | None] = mapped_column(String(500))


class ScoreRevision(BusinessModel):
    """An append-only record of every applied score change.

    The audit log already records the action; this table keeps the before and
    after values in one place so a report card reprint can explain a change
    without parsing audit payloads. Revisions are never edited or deleted by
    the application.
    """

    __tablename__ = "assessment_score_revisions"
    __table_args__ = (
        Index("ix_assessment_score_revisions_score", "score_id", "changed_at"),
        Index("ix_assessment_score_revisions_student", "student_id", "changed_at"),
        Index("ix_assessment_score_revisions_request", "correction_request_id"),
    )

    score_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_scores.id", ondelete="CASCADE"),
        nullable=False,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    correction_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_correction_requests.id", ondelete="SET NULL"),
    )
    old_raw: Mapped[Decimal | None] = mapped_column(Mark)
    new_raw: Mapped[Decimal | None] = mapped_column(Mark)
    old_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str | None] = mapped_column(String(20))
    old_converted: Mapped[Decimal | None] = mapped_column(Mark)
    new_converted: Mapped[Decimal | None] = mapped_column(Mark)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="entry")
    reason: Mapped[str | None] = mapped_column(String(500))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class ScaleAssignment(BusinessModel):
    """Attach a grade scale to one context; the most specific context wins."""

    __tablename__ = "assessment_scale_assignments"
    __table_args__ = (
        Index(
            "uq_assessment_scale_assignments_scope_live",
            "scope_key",
            "scale_id",
            unique=True,
            **LIVE_INDEX,
        ),
        Index("ix_assessment_scale_assignments_context", "context", "scope_key"),
    )

    scale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_grade_scales.id", ondelete="CASCADE"),
        nullable=False,
    )
    context: Mapped[str] = mapped_column(String(20), nullable=False)
    # "default" or "<context>:<uuid>"; deterministic so the unique live index
    # works even though default assignments have no target id.
    scope_key: Mapped[str] = mapped_column(String(80), nullable=False)
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_assessments.id", ondelete="CASCADE"),
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_subjects.id", ondelete="CASCADE"),
    )
    level_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_grade_levels.id", ondelete="CASCADE"),
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_stages.id", ondelete="CASCADE"),
    )
    notes: Mapped[str | None] = mapped_column(Text)


class TermResult(BusinessModel):
    """A computed subject result for one student in one term.

    Raw marks are never modified by a recalculation; this row is replaced or
    refreshed from them. ``scale_version`` records which grade rules produced
    ``grade_label`` so a later scale edit cannot rewrite history silently.
    """

    __tablename__ = "assessment_term_results"
    __table_args__ = (
        Index(
            "uq_assessment_term_results_scope_live",
            "year_id",
            "term_id",
            "section_id",
            "subject_id",
            "student_id",
            unique=True,
            **LIVE_INDEX,
        ),
        Index("ix_assessment_term_results_student", "student_id", "year_id"),
        Index("ix_assessment_term_results_section_term", "section_id", "term_id"),
        Index("ix_assessment_term_results_status", "status"),
    )

    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_terms.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    structure_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_structures.id", ondelete="SET NULL"),
    )
    structure_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scale_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_grade_scales.id", ondelete="SET NULL"),
    )
    scale_version: Mapped[int | None] = mapped_column(Integer)
    total: Mapped[Decimal] = mapped_column(Mark, nullable=False)
    out_of: Mapped[Decimal] = mapped_column(Mark, nullable=False)
    percent: Mapped[Decimal] = mapped_column(Mark, nullable=False)
    grade_label: Mapped[str | None] = mapped_column(String(40))
    grade_remark: Mapped[str | None] = mapped_column(String(255))
    gpa_points: Mapped[Decimal | None] = mapped_column(Mark)
    is_pass: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rank: Mapped[int | None] = mapped_column(Integer)
    rank_size: Mapped[int | None] = mapped_column(Integer)
    # Mirrors the submission's state so a parent read can filter published
    # rows without a multi-table join; P4-08 keeps it in step.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ResultSnapshot(BusinessModel):
    """An immutable published payload, including the rules that produced it."""

    __tablename__ = "assessment_result_snapshots"
    __table_args__ = (
        Index("ix_assessment_result_snapshots_scope", "year_id", "term_id"),
        Index("ix_assessment_result_snapshots_section", "section_id"),
        Index("ix_assessment_result_snapshots_student", "student_id"),
        Index("ix_assessment_result_snapshots_published", "published_at"),
    )

    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_terms.id", ondelete="CASCADE"),
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_sections.id", ondelete="CASCADE"),
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="term")
    structure_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_structures.id", ondelete="SET NULL"),
    )
    structure_version: Mapped[int | None] = mapped_column(Integer)
    scale_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_grade_scales.id", ondelete="SET NULL"),
    )
    scale_version: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONType, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(String(500))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assessment_result_snapshots.id", ondelete="SET NULL"),
    )


class MarkingWindow(BusinessModel):
    """When teachers may enter or change marks for a term and level/section."""

    __tablename__ = "assessment_marking_windows"
    __table_args__ = (
        Index("ix_assessment_marking_windows_term", "year_id", "term_id", "closes_at"),
        Index("ix_assessment_marking_windows_scope", "scope_key"),
    )

    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_terms.id", ondelete="CASCADE"),
        nullable=False,
    )
    level_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_grade_levels.id", ondelete="CASCADE"),
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_sections.id", ondelete="CASCADE"),
    )
    # "all" or "<level|section>:<uuid>"; windows do not need a unique key
    # because a term can be reopened for a second entry period.
    scope_key: Mapped[str] = mapped_column(String(80), nullable=False, default="all")
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(String(500))


class Submission(BusinessModel):
    """The per-subject mark workflow: draft → submitted → approved → published → locked."""

    __tablename__ = "assessment_submissions"
    __table_args__ = (
        Index(
            "uq_assessment_submissions_scope_live",
            "year_id",
            "term_id",
            "section_id",
            "subject_id",
            unique=True,
            **LIVE_INDEX,
        ),
        Index("ix_assessment_submissions_status", "status"),
        Index("ix_assessment_submissions_section_term", "section_id", "term_id"),
    )

    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_terms.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(String(500))


__all__ = [
    "MARK_QUANTUM",
    "MARK_SCALE",
    "Assessment",
    "AssessmentComponent",
    "AssessmentStructure",
    "CorrectionRequest",
    "GradeBand",
    "GradeScale",
    "Mark",
    "MarkingWindow",
    "ResultSnapshot",
    "ScaleAssignment",
    "Score",
    "ScoreRevision",
    "Submission",
    "TermResult",
]
