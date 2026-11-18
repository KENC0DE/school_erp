"""Schemas for attendance sessions, records and the daily roster."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AttendanceMode = Literal["daily", "per_period"]
SessionStatus = Literal["open", "submitted", "locked"]
RecordStatus = Literal["present", "absent", "late", "excused"]

MODES: tuple[str, ...] = ("daily", "per_period")
SESSION_STATUSES: tuple[str, ...] = ("open", "submitted", "locked")
RECORD_STATUSES: tuple[str, ...] = ("present", "absent", "late", "excused")


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year_id: uuid.UUID
    section_id: uuid.UUID
    date: date
    mode: AttendanceMode | None = None
    period: int | None = Field(default=None, ge=1, le=20)
    subject_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    seed_records: bool = True

    @model_validator(mode="after")
    def _period_matches_mode(self) -> SessionCreate:
        if self.mode == "daily" and self.period is not None:
            raise ValueError("A daily register cannot carry a lesson number")
        if self.mode == "per_period" and self.period is None:
            raise ValueError("A per-period register needs a lesson number")
        return self


class SessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: str | None = Field(default=None, max_length=2000)
    row_version: int = Field(ge=1)


class SessionQuery(BaseModel):
    year_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    from_date: date | None = None
    to_date: date | None = None
    status: SessionStatus | None = None
    limit: int = Field(default=25, ge=1, le=200)
    cursor: str | None = Field(default=None, max_length=1000)
    sort: str | None = Field(default=None, max_length=60)
    order: Literal["asc", "desc"] = "desc"


class RecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: uuid.UUID
    status: RecordStatus = "present"
    reason: str | None = Field(default=None, max_length=500)
    late_minutes: int | None = Field(default=None, ge=0, le=600)
    note: str | None = Field(default=None, max_length=2000)
    # Optional optimistic check for offline sync (P12). A missing value means
    # "last writer wins" for this student and session, which is safe because the
    # natural key keeps exactly one row.
    row_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _late_minutes_only_for_late(self) -> RecordInput:
        if self.late_minutes is not None and self.status != "late":
            raise ValueError("Late minutes only apply to a late entry")
        return self


class BulkRecordsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RecordInput] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _unique_students(self) -> BulkRecordsInput:
        seen = [str(item.student_id) for item in self.items]
        if len(seen) != len(set(seen)):
            raise ValueError("A student appears twice in the same entry")
        return self


class RecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RecordStatus | None = None
    reason: str | None = Field(default=None, max_length=500)
    late_minutes: int | None = Field(default=None, ge=0, le=600)
    note: str | None = Field(default=None, max_length=2000)
    row_version: int = Field(ge=1)

    @model_validator(mode="after")
    def _late_minutes_only_for_late(self) -> RecordUpdate:
        if self.late_minutes is not None and self.status not in (None, "late"):
            raise ValueError("Late minutes only apply to a late entry")
        return self


class RecordOut(BaseModel):
    id: str
    session_id: str
    student_id: str
    student_number: str
    student_name: str
    student_name_am: str | None = None
    roll_number: str | None = None
    status: RecordStatus
    reason: str | None = None
    late_minutes: int | None = None
    note: str | None = None
    recorded_at: datetime
    recorded_by: str | None = None
    recorded_by_name: str | None = None
    row_version: int


class SessionCounts(BaseModel):
    total: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0


class RosterEntry(BaseModel):
    student_id: str
    student_number: str
    full_name: str
    roll_number: str | None = None
    status: RecordStatus | None = None
    record_id: str | None = None


class SessionOut(BaseModel):
    id: str
    year_id: str
    year_code: str
    section_id: str
    section_code: str
    section_name: str | None = None
    level_id: str
    level_code: str
    level_name: str
    date: date
    mode: AttendanceMode
    period: int | None = None
    subject_id: str | None = None
    subject_code: str | None = None
    subject_name: str | None = None
    status: SessionStatus
    notes: str | None = None
    counts: SessionCounts
    status_changed_at: datetime | None = None
    status_changed_by: str | None = None
    status_changed_by_name: str | None = None
    row_version: int


class SessionDetail(SessionOut):
    records: list[RecordOut] = Field(default_factory=list)
    roster: list[RosterEntry] = Field(default_factory=list)


class SessionList(BaseModel):
    items: list[SessionOut]
    next_cursor: str | None = None
    total: int


class AttendanceReportQuery(BaseModel):
    from_date: date
    to_date: date
    year_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None
    threshold: int = Field(default=85, ge=0, le=100)
    below_only: bool = False
    limit: int = Field(default=500, ge=1, le=2000)


class StudentAttendanceReportRow(BaseModel):
    student_id: str
    student_number: str
    student_name: str
    student_name_am: str | None = None
    year_id: str
    year_code: str
    section_id: str
    section_code: str
    section_name: str | None = None
    total_records: int
    present: int
    absent: int
    late: int
    excused: int
    attended: int
    rate_percent: int
    below_threshold: bool


class SectionAttendanceReportRow(BaseModel):
    year_id: str
    year_code: str
    section_id: str
    section_code: str
    section_name: str | None = None
    level_id: str
    level_code: str
    level_name: str
    student_count: int
    session_count: int
    total_records: int
    present: int
    absent: int
    late: int
    excused: int
    attended: int
    rate_percent: int
    below_threshold: bool


class StudentAttendanceReport(BaseModel):
    from_date: date
    to_date: date
    threshold: int
    below_only: bool
    total: int
    items: list[StudentAttendanceReportRow]


class SectionAttendanceReport(BaseModel):
    from_date: date
    to_date: date
    threshold: int
    below_only: bool
    total: int
    items: list[SectionAttendanceReportRow]


__all__ = [
    "AttendanceMode",
    "AttendanceReportQuery",
    "BulkRecordsInput",
    "MODES",
    "RECORD_STATUSES",
    "RecordInput",
    "RecordOut",
    "RecordStatus",
    "RecordUpdate",
    "RosterEntry",
    "SESSION_STATUSES",
    "SectionAttendanceReport",
    "SectionAttendanceReportRow",
    "SessionCounts",
    "SessionCreate",
    "SessionDetail",
    "SessionList",
    "SessionOut",
    "SessionQuery",
    "SessionStatus",
    "SessionUpdate",
    "StudentAttendanceReport",
    "StudentAttendanceReportRow",
]
