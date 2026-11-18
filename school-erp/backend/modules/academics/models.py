"""Academics catalog: grade levels, stages and their grouping (ARCH §9.1).

Scope is stored as a small integer per level (0 = kindergarten, 1–12 = grades)
so the existing ``academic_scope.first_level``/``last_level`` settings keep
their published meaning. A school narrows its scope in core settings; every
list endpoint in this module filters against it.
"""

from __future__ import annotations

import uuid
from datetime import date

from core.db.base import Base, BusinessModel
from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column


class GradeLevel(BusinessModel):
    __tablename__ = "academics_grade_levels"
    __table_args__ = (
        # A code stays unique among live rows; a deleted level's code can be
        # reused without hard-deleting its history.
        Index(
            "uq_academics_grade_levels_code_live",
            "code",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_academics_grade_levels_sort_order", "sort_order"),
    )

    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(80))
    # 0 = kindergarten (KG1–KG3); 1..12 = the matching grade.
    scope_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Shipped starter entries stay flagged until the school confirms them.
    is_starter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Stage(BusinessModel):
    __tablename__ = "academics_stages"
    __table_args__ = (
        Index(
            "uq_academics_stages_code_live",
            "code",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_academics_stages_sort_order", "sort_order"),
    )

    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_starter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AcademicYear(BusinessModel):
    """A school year. Dates are stored in GC and displayed in EC or GC.

    ``term_system`` is a snapshot: changing the school setting later does not
    rewrite years that already carry results.
    """

    __tablename__ = "academics_academic_years"
    __table_args__ = (
        Index(
            "uq_academics_academic_years_code_live",
            "code",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_academics_academic_years_start_date", "start_date"),
    )

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    term_system: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # The curriculum applied from this year forward, if any.
    curriculum_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_curriculum_profiles.id", ondelete="SET NULL"),
    )


class Term(BusinessModel):
    """One semester or quarter inside an academic year.

    The number of terms is fixed at year creation so year-result rules stay
    addressable. Names and dates stay editable until the year is closed.
    """

    __tablename__ = "academics_terms"
    __table_args__ = (
        Index(
            "uq_academics_terms_year_number_live",
            "year_id",
            "number",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_academics_terms_year_start", "year_id", "start_date"),
    )

    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")


class Subject(BusinessModel):
    """A subject the school teaches. Assignment to levels carries credit."""

    __tablename__ = "academics_subjects"
    __table_args__ = (
        Index(
            "uq_academics_subjects_code_live",
            "code",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_academics_subjects_sort_order", "sort_order"),
    )

    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LevelSubject(Base):
    """Which subjects a grade level offers, with an integer credit/weight."""

    __tablename__ = "academics_level_subjects"

    level_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_grade_levels.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    credit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SubjectGroup(BusinessModel):
    """A named group of subjects (for example electives or a stream)."""

    __tablename__ = "academics_subject_groups"
    __table_args__ = (
        Index(
            "uq_academics_subject_groups_code_live",
            "code",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_academics_subject_groups_sort_order", "sort_order"),
    )

    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SubjectGroupMember(Base):
    __tablename__ = "academics_subject_group_members"

    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_subject_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Section(BusinessModel):
    """A class group for one level in one academic year."""

    __tablename__ = "academics_sections"
    __table_args__ = (
        Index(
            "uq_academics_sections_year_level_code_live",
            "year_id",
            "level_id",
            "code",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_academics_sections_year_level", "year_id", "level_id"),
    )

    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    level_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_grade_levels.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str | None] = mapped_column(String(120))
    name_am: Mapped[str | None] = mapped_column(String(120))
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    homeroom_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CurriculumProfile(BusinessModel):
    """A reusable curriculum bundle: term system plus subjects per level.

    Shipped profiles are starter data (``is_starter=True``,
    ``is_verified=False``) and stay fully editable; a school can duplicate one
    and change the copy. Mark structures, grade scales and promotion rules are
    added to the bundle in their own phases.
    """

    __tablename__ = "academics_curriculum_profiles"
    __table_args__ = (
        Index(
            "uq_academics_curriculum_profiles_code_live",
            "code",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_academics_curriculum_profiles_sort_order", "sort_order"),
    )

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(500))
    term_system: Mapped[str] = mapped_column(String(20), nullable=False, default="semester")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_starter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CurriculumLevelSubject(Base):
    """A subject a curriculum profile offers at a level, with its credit."""

    __tablename__ = "academics_curriculum_level_subjects"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_curriculum_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    level_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_grade_levels.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    credit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class StageLevel(Base):
    """Ordered membership: which grade levels belong to a stage."""

    __tablename__ = "academics_stage_levels"

    stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_stages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    level_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_grade_levels.id", ondelete="CASCADE"),
        primary_key=True,
    )


__all__ = [
    "AcademicYear",
    "CurriculumLevelSubject",
    "CurriculumProfile",
    "GradeLevel",
    "LevelSubject",
    "Section",
    "Stage",
    "StageLevel",
    "Subject",
    "SubjectGroup",
    "SubjectGroupMember",
    "Term",
]
