"""Student records: profile, enrollment, guardians and medical data (ARCH §9.2)."""

from __future__ import annotations

import uuid
from datetime import date

from core.db.base import Base, BusinessModel, JSONType, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column


class StudentProfile(BusinessModel):
    """The student-specific part of a shared person record."""

    __tablename__ = "student_profiles"
    __table_args__ = (
        Index(
            "uq_student_profiles_number_live",
            "student_number",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_student_profiles_person_live",
            "person_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_student_profiles_status", "status"),
    )

    person_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("persons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    student_number: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="applicant")
    admission_date: Mapped[date | None] = mapped_column(Date)
    exit_date: Mapped[date | None] = mapped_column(Date)
    exit_reason: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    custom: Mapped[dict | None] = mapped_column(JSONType)


class StudentEnrollment(BusinessModel):
    """One student's placement in an academic year, level and section."""

    __tablename__ = "student_enrollments"
    __table_args__ = (
        Index(
            "uq_student_enrollments_student_year_live",
            "student_id",
            "year_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_student_enrollments_year_level_section", "year_id", "level_id", "section_id"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    year_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    level_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    section_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    roll_number: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text)


class StudentGuardian(BusinessModel):
    """Many-to-many link between a student and a guardian person."""

    __tablename__ = "student_guardians"
    __table_args__ = (
        Index(
            "uq_student_guardians_student_person_live",
            "student_id",
            "person_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_student_guardians_person", "person_id"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("persons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    relationship: Mapped[str] = mapped_column(String(40), nullable=False, default="guardian")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_pickup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)


class StudentMedicalRecord(BusinessModel):
    """Sensitive health information, guarded by dedicated permissions."""

    __tablename__ = "student_medical_records"
    __table_args__ = (
        Index(
            "uq_student_medical_records_student_live",
            "student_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    blood_type: Mapped[str | None] = mapped_column(String(10))
    allergies: Mapped[str | None] = mapped_column(Text)
    chronic_conditions: Mapped[str | None] = mapped_column(Text)
    medications: Mapped[str | None] = mapped_column(Text)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(160))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    consent_to_treat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class StudentNumberSequence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The last student number issued for one numbering scope.

    This is a counter, not a business record: allocation is atomic and is not
    soft-deleted, because a rollback may leave a gap but must never reuse a
    number. The student registration itself is audited with the final number.
    """

    __tablename__ = "student_number_sequences"
    __table_args__ = (UniqueConstraint("scope", name="uq_student_number_sequences_scope"),)

    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)


__all__ = [
    "StudentEnrollment",
    "StudentGuardian",
    "StudentMedicalRecord",
    "StudentNumberSequence",
    "StudentProfile",
]
