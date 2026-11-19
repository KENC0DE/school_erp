"""API models for the document module (P5-02)."""

from __future__ import annotations

from typing import Any

from core.documents.fields import FieldKind
from pydantic import BaseModel, Field


class DocumentFieldOut(BaseModel):
    """One bindable value, attributed to the module that offers it."""

    key: str
    label_key: str
    kind: FieldKind
    formats: list[str] = Field(default_factory=list)
    sample: Any = None
    module: str


class DocumentFormatOptions(BaseModel):
    """The formatting dimensions the renderer and the editor both understand."""

    calendar: list[str]
    script: list[str]
    money: list[str]


class DocumentFieldsOut(BaseModel):
    items: list[DocumentFieldOut] = Field(default_factory=list)
    format_options: DocumentFormatOptions


__all__ = ["DocumentFieldOut", "DocumentFieldsOut", "DocumentFormatOptions"]
