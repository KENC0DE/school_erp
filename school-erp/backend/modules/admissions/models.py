"""Student admissions: applications, guardians, decisions and conversion (ARCH §9.2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from core.db.base import Base, BusinessModel, JSONType, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import (
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

ADMISSION_STATUSES: tuple[str, ...] = (
    "applied",
    "reviewed",
    "test",
    "offered",
    "accepted",
    "enrolled",
    "rejected",
    "withdrawn",
)

# The decision workflow. ``enrolled`` is reached only by converting an accepted
# application, so it is deliberately absent from every transition list.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "applied": ("reviewed", "rejected", "withdrawn"),
    "reviewed": ("test", "offered", "rejected", "withdrawn"),
    "test": ("offered", "rejected", "withdrawn"),
    "offered": ("accepted", "rejected", "withdrawn"),
    "accepted": ("withdrawn",),
    "enrolled": (),
    "rejected": (),
    "withdrawn": (),
}


class AdmissionApplication(BusinessModel):
    """One application for a place in an academic year and grade level."""

    __tablename__ = "admission_applications"
    __table_args__ = (
        Index(
            "uq_admission_applications_number_live",
            "application_number",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_admission_applications_person_year_live",
            "person_id",
            "year_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_admission_applications_status", "status"),
        Index("ix_admission_applications_year_level", "year_id", "level_id"),
    )

    person_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("persons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    application_number: Mapped[str] = mapped_column(String(40), nullable=False)
    year_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    level_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    section_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="applied")
    entrance_test_score: Mapped[int | None] = mapped_column(Integer)
    decision_notes: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="SET NULL"),
    )
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_on: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="office")
    notes: Mapped[str | None] = mapped_column(Text)
    custom: Mapped[dict | None] = mapped_column(JSONType)


class AdmissionGuardian(BusinessModel):
    """A guardian named on an application, optionally given an account."""

    __tablename__ = "admission_guardians"
    __table_args__ = (
        Index(
            "uq_admission_guardians_application_person_live",
            "application_id",
            "person_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_admission_guardians_person", "person_id"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admission_applications.id", ondelete="CASCADE"),
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
    wants_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    account_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)


class AdmissionNumberSequence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The last application number issued for one numbering scope.

    Like the student sequence this is a counter, not a business record: it is
    never soft-deleted, because allocation may leave a gap but must never issue
    the same number twice.
    """

    __tablename__ = "admission_number_sequences"
    __table_args__ = (UniqueConstraint("scope", name="uq_admission_number_sequences_scope"),)

    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)


__all__ = [
    "ADMISSION_STATUSES",
    "TRANSITIONS",
    "AdmissionApplication",
    "AdmissionGuardian",
    "AdmissionNumberSequence",
]
