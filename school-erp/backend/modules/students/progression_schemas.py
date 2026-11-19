"""Schemas for bulk promotion, status changes and their previews (ARCH §9.2)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

PromotionAction = Literal["promote", "repeat", "graduate", "skip"]
StudentStatusAction = Literal["transfer_out", "withdraw", "graduate", "alumni", "reinstate"]

PROMOTION_ACTIONS: tuple[str, ...] = ("promote", "repeat", "graduate", "skip")
STATUS_ACTIONS: tuple[str, ...] = ("transfer_out", "withdraw", "graduate", "alumni", "reinstate")


class PromotionException(BaseModel):
    """A manual decision for one student that overrides the default rule."""

    student_id: uuid.UUID
    action: PromotionAction
    target_level_id: uuid.UUID | None = None
    target_section_id: uuid.UUID | None = None


class PromotionRequest(BaseModel):
    source_year_id: uuid.UUID
    target_year_id: uuid.UUID
    source_level_id: uuid.UUID | None = None
    source_section_id: uuid.UUID | None = None
    # An empty list means "every eligible student in the selected scope".
    student_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5000)
    exceptions: list[PromotionException] = Field(default_factory=list, max_length=5000)
    effective_date: date | None = None
    reason: str | None = Field(default=None, max_length=500)


class PromotionRow(BaseModel):
    student_id: str
    student_number: str
    full_name: str
    status: str
    current_level_id: str
    current_level_name: str
    current_level_sort_order: int
    current_section_id: str | None = None
    current_section_code: str | None = None
    action: PromotionAction
    next_level_id: str | None = None
    next_level_name: str | None = None
    target_level_id: str | None = None
    target_level_name: str | None = None
    target_section_id: str | None = None
    target_section_code: str | None = None
    warnings: list[str] = Field(default_factory=list)
    blocking: bool = False


class PromotionPreview(BaseModel):
    source_year_id: str
    target_year_id: str
    total: int
    promote: int = 0
    repeat: int = 0
    graduate: int = 0
    skip: int = 0
    blocking: int = 0
    items: list[PromotionRow] = Field(default_factory=list)


class PromotionApplyOut(BaseModel):
    source_year_id: str
    target_year_id: str
    enrolled: int = 0
    promoted: int = 0
    repeated: int = 0
    graduated: int = 0
    skipped: int = 0
    items: list[PromotionRow] = Field(default_factory=list)


class StudentStatusChange(BaseModel):
    action: StudentStatusAction
    exit_date: date | None = None
    exit_reason: str | None = Field(default=None, max_length=500)
    row_version: int | None = Field(default=None, ge=1)


class StudentStatusChangeOut(BaseModel):
    action: StudentStatusAction
    changed: bool
    student: dict


__all__ = [
    "PROMOTION_ACTIONS",
    "STATUS_ACTIONS",
    "PromotionAction",
    "PromotionApplyOut",
    "PromotionException",
    "PromotionPreview",
    "PromotionRequest",
    "PromotionRow",
    "StudentStatusAction",
    "StudentStatusChange",
    "StudentStatusChangeOut",
]
