from __future__ import annotations

from pydantic import BaseModel, Field


class SampleSettings(BaseModel):
    """Demonstrates a module-owned typed settings schema."""

    default_author: str = Field("Sample module", min_length=1, max_length=100)
    allow_empty_notes: bool = False
    page_size: int = Field(25, ge=1, le=100)


__all__ = ["SampleSettings"]
