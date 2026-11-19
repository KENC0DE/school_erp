"""Attendance sessions and per-student records (ARCH §9.4).

A school works in one mode: ``daily`` (one session per section per day) or
``per_period`` (one session per lesson, later driven by the timetable module).
Statuses are present, absent, late and excused; a session is seeded with every
enrolled student marked present so a teacher only changes exceptions.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from core.db.base import BusinessModel
from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

LIVE_INDEX = {
    "sqlite_where": text("deleted_at IS NULL"),
    "postgresql_where": text("deleted_at IS NULL"),
}


class AttendanceSession(BusinessModel):
    """One attendance register: a section, a date and (per period) a lesson."""

    __tablename__ = "attendance_sessions"
    __table_args__ = (
        Index(
            "uq_attendance_sessions_scope_live",
            "year_id",
            "section_id",
            "date",
            "mode",
            "period",
            unique=True,
            **LIVE_INDEX,
        ),
        Index("ix_attendance_sessions_section_date", "section_id", "date"),
        Index("ix_attendance_sessions_year_date", "year_id", "date"),
        Index("ix_attendance_sessions_status", "status"),
    )

    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="RESTRICT"),
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_sections.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # GC date; the UI shows the school's preferred calendar.
    date: Mapped[date] = mapped_column(Date, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    # 1-based lesson number. Null in daily mode; required in per-period mode.
    period: Mapped[int | None] = mapped_column(Integer)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_subjects.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    notes: Mapped[str | None] = mapped_column(Text)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_changed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )


class AttendanceRecord(BusinessModel):
    """One student's status in one session. At most one live row per student."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        Index(
            "uq_attendance_records_session_student_live",
            "session_id",
            "student_id",
            unique=True,
            **LIVE_INDEX,
        ),
        Index("ix_attendance_records_student", "student_id"),
        Index("ix_attendance_records_session_status", "session_id", "status"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="present")
    reason: Mapped[str | None] = mapped_column(String(500))
    late_minutes: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )


__all__ = ["AttendanceRecord", "AttendanceSession"]
