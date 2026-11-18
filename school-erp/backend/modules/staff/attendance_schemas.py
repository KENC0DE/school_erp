"""Schemas for staff attendance (ARCH §9.3)."""

from __future__ import annotations

import uuid
from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

StaffAttendanceStatus = Literal["present", "absent", "late", "leave"]

STAFF_ATTENDANCE_STATUSES: tuple[str, ...] = ("present", "absent", "late", "leave")


class StaffAttendanceQuery(BaseModel):
    date: Date | None = None
    department_id: uuid.UUID | None = None
    status: StaffAttendanceStatus | None = None
    q: str | None = Field(default=None, max_length=120)


class StaffAttendanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_id: uuid.UUID
    status: StaffAttendanceStatus = "present"
    reason: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=2000)
    # Optional optimistic check for a replayed offline edit.
    row_version: int | None = Field(default=None, ge=1)


class StaffAttendanceBulkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: Date
    items: list[StaffAttendanceInput] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _unique_staff(self) -> StaffAttendanceBulkInput:
        seen = [str(item.staff_id) for item in self.items]
        if len(seen) != len(set(seen)):
            raise ValueError("A staff member appears twice in the same entry")
        return self


class StaffAttendanceEntryOut(BaseModel):
    staff_id: str
    staff_number: str
    staff_name: str
    staff_name_am: str | None = None
    department_id: str | None = None
    department_name: str | None = None
    status: StaffAttendanceStatus | None = None
    reason: str | None = None
    note: str | None = None
    record_id: str | None = None
    row_version: int | None = None


class StaffAttendanceCounts(BaseModel):
    total: int = 0
    recorded: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    leave: int = 0
    unrecorded: int = 0


class StaffAttendanceDay(BaseModel):
    date: Date
    counts: StaffAttendanceCounts
    items: list[StaffAttendanceEntryOut]


class StaffAttendanceSummary(BaseModel):
    staff_id: str
    staff_number: str
    staff_name: str
    from_date: Date
    to_date: Date
    total: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    leave: int = 0
    attended: int = 0
    rate_percent: int = 0


__all__ = [
    "STAFF_ATTENDANCE_STATUSES",
    "StaffAttendanceBulkInput",
    "StaffAttendanceCounts",
    "StaffAttendanceDay",
    "StaffAttendanceEntryOut",
    "StaffAttendanceInput",
    "StaffAttendanceQuery",
    "StaffAttendanceStatus",
    "StaffAttendanceSummary",
]
