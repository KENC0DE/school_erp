"""Attendance module settings (ARCH §9.4).

The school works in one mode. Per-period mode needs the timetable module: until
that module publishes slots, a per-period session carries its own lesson number
(P6-07 replaces that with the timetable slot).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AttendanceSettings(BaseModel):
    mode: Literal["daily", "per_period"] = Field(
        "daily",
        json_schema_extra={"label_key": "settings.attendance.mode"},
        description="One register per section per day, or one per lesson",
    )
    require_reason: bool = Field(
        False,
        json_schema_extra={"label_key": "settings.attendance.require_reason"},
        description="Require a reason for absent, late and excused entries",
    )
    allow_future_dates: bool = Field(
        False,
        json_schema_extra={"label_key": "settings.attendance.allow_future_dates"},
        description="Allow registers dated after today",
    )


__all__ = ["AttendanceSettings"]
