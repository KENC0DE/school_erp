"""Reusable person input models for core and other modules (ARCH §5.8)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class PersonInput(BaseModel):
    given_name_en: str | None = Field(default=None, max_length=120)
    father_name_en: str | None = Field(default=None, max_length=120)
    grandfather_name_en: str | None = Field(default=None, max_length=120)
    given_name_am: str | None = Field(default=None, max_length=120)
    father_name_am: str | None = Field(default=None, max_length=120)
    grandfather_name_am: str | None = Field(default=None, max_length=120)
    mother_name_en: str | None = Field(default=None, max_length=120)
    mother_name_am: str | None = Field(default=None, max_length=120)
    baptismal_name: str | None = Field(default=None, max_length=120)
    nickname: str | None = Field(default=None, max_length=120)
    sex: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    place_of_birth: str | None = Field(default=None, max_length=200)
    nationality: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None
    photo_file_id: uuid.UUID | None = None
    custom: dict[str, Any] | None = None


__all__ = ["PersonInput"]
