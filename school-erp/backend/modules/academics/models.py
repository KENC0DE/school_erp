"""Academics catalog: grade levels, stages and their grouping (ARCH §9.1).

Scope is stored as a small integer per level (0 = kindergarten, 1–12 = grades)
so the existing ``academic_scope.first_level``/``last_level`` settings keep
their published meaning. A school narrows its scope in core settings; every
list endpoint in this module filters against it.
"""

from __future__ import annotations

import uuid

from core.db.base import Base, BusinessModel
from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Uuid, text
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


__all__ = ["GradeLevel", "Stage", "StageLevel"]
