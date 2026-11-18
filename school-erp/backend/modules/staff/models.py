"""Staff and HR records: profiles on persons, departments, positions and contracts (ARCH §9.3)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from core.db.base import Base, BusinessModel, JSONType, TimestampMixin, UUIDPrimaryKeyMixin
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
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

LIVE_INDEX = {
    "sqlite_where": text("deleted_at IS NULL"),
    "postgresql_where": text("deleted_at IS NULL"),
}


class StaffDepartment(BusinessModel):
    """A school department. Deactivate instead of deleting a department in use."""

    __tablename__ = "staff_departments"
    __table_args__ = (
        Index("uq_staff_departments_code_live", "code", unique=True, **LIVE_INDEX),
        Index("ix_staff_departments_sort_order", "sort_order"),
    )

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(120))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_departments.id", ondelete="RESTRICT"),
    )
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StaffPosition(BusinessModel):
    """A post inside a department, such as "Grade 5 Mathematics Teacher"."""

    __tablename__ = "staff_positions"
    __table_args__ = (
        Index("uq_staff_positions_code_live", "code", unique=True, **LIVE_INDEX),
        Index("ix_staff_positions_department", "department_id"),
        Index("ix_staff_positions_sort_order", "sort_order"),
    )

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(120))
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_departments.id", ondelete="RESTRICT"),
    )
    is_teaching: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StaffProfile(BusinessModel):
    """The staff-specific part of a shared person record."""

    __tablename__ = "staff_profiles"
    __table_args__ = (
        Index("uq_staff_profiles_number_live", "staff_number", unique=True, **LIVE_INDEX),
        Index("uq_staff_profiles_person_live", "person_id", unique=True, **LIVE_INDEX),
        Index("uq_staff_profiles_user_live", "user_id", unique=True, **LIVE_INDEX),
        Index("ix_staff_profiles_status", "status"),
        Index("ix_staff_profiles_department", "department_id"),
        Index("ix_staff_profiles_position", "position_id"),
    )

    person_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("persons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    staff_number: Mapped[str] = mapped_column(String(40), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_departments.id", ondelete="RESTRICT"),
    )
    position_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_positions.id", ondelete="RESTRICT"),
    )
    hire_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    custom: Mapped[dict | None] = mapped_column(JSONType)


class StaffContract(BusinessModel):
    """An employment contract. Money is stored in integer santim, never a float."""

    __tablename__ = "staff_contracts"
    __table_args__ = (
        Index("ix_staff_contracts_staff", "staff_id"),
        Index("ix_staff_contracts_status", "status"),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False, default="permanent")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    salary_santim: Mapped[int | None] = mapped_column(BigInteger)
    notes: Mapped[str | None] = mapped_column(Text)


class StaffQualification(BusinessModel):
    """Education, training, certification or prior experience."""

    __tablename__ = "staff_qualifications"
    __table_args__ = (Index("ix_staff_qualifications_staff", "staff_id"),)

    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="education")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(200))
    field_of_study: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    result: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)


class StaffTeachingAssignment(BusinessModel):
    """A teacher's subject in a section for one academic year."""

    __tablename__ = "staff_teaching_assignments"
    __table_args__ = (
        Index(
            "uq_staff_teaching_assignment_live",
            "staff_id",
            "year_id",
            "section_id",
            "subject_id",
            unique=True,
            **LIVE_INDEX,
        ),
        Index("ix_staff_teaching_assignment_year", "year_id"),
        Index("ix_staff_teaching_assignment_section", "section_id"),
        Index("ix_staff_teaching_assignment_subject", "subject_id"),
        Index("ix_staff_teaching_assignment_staff", "staff_id"),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
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
    notes: Mapped[str | None] = mapped_column(Text)


class StaffLeaveType(BusinessModel):
    """A kind of leave, with its yearly entitlement expressed in half-days."""

    __tablename__ = "staff_leave_types"
    __table_args__ = (
        Index("uq_staff_leave_types_code_live", "code", unique=True, **LIVE_INDEX),
        Index("ix_staff_leave_types_sort_order", "sort_order"),
    )

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_am: Mapped[str | None] = mapped_column(String(120))
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    annual_entitlement_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    counts_against_balance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)


class StaffLeaveBalance(BusinessModel):
    """One staff member's leave entitlement for one type and academic year."""

    __tablename__ = "staff_leave_balances"
    __table_args__ = (
        Index(
            "uq_staff_leave_balance_live",
            "staff_id",
            "year_id",
            "leave_type_id",
            unique=True,
            **LIVE_INDEX,
        ),
        Index("ix_staff_leave_balances_staff", "staff_id"),
        Index("ix_staff_leave_balances_year", "year_id"),
        Index("ix_staff_leave_balances_type", "leave_type_id"),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_leave_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entitled_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    carried_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    adjustment_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)


class StaffLeaveRequest(BusinessModel):
    """A dated leave request and its approval state.

    ``days_units`` counts half-days so a half-day request never needs a float:
    a full day is two units and a half day is one.
    """

    __tablename__ = "staff_leave_requests"
    __table_args__ = (
        Index("ix_staff_leave_requests_staff", "staff_id"),
        Index("ix_staff_leave_requests_year", "year_id"),
        Index("ix_staff_leave_requests_type", "leave_type_id"),
        Index("ix_staff_leave_requests_status", "status"),
        Index("ix_staff_leave_requests_dates", "start_date", "end_date"),
    )

    staff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    year_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("staff_leave_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_half_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    days_units: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    decision_note: Mapped[str | None] = mapped_column(Text)


class StaffNumberSequence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The last staff number issued for one numbering scope (atomic counter)."""

    __tablename__ = "staff_number_sequences"
    __table_args__ = (UniqueConstraint("scope", name="uq_staff_number_sequences_scope"),)

    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)


__all__ = [
    "StaffContract",
    "StaffDepartment",
    "StaffLeaveBalance",
    "StaffLeaveRequest",
    "StaffLeaveType",
    "StaffNumberSequence",
    "StaffPosition",
    "StaffProfile",
    "StaffQualification",
    "StaffTeachingAssignment",
]
