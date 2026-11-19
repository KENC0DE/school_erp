"""Document layout schema, version 1 (P5-01).

The canonical definition is the Zod schema in
``shared/ts/documents/src/layout.ts``; ``shared/schema/document-layout.v1.json``
is generated from it and this module mirrors it for the server. Both suites
validate ``shared/schema/document-layout.fixtures.json`` so the two definitions
cannot drift apart.

Geometry is millimetres. Layout numbers are drawing data rather than money or
marks, so they are floats; monetary and mark values never enter a layout as
literals — they arrive through bound fields and are formatted by the renderer.

Refinements JSON Schema cannot express are enforced here exactly as the Zod
``superRefine`` hooks enforce them: unique element ids, a custom page that names
its size, unique table columns and summaries that name a real column. Optional
fields reject an explicit ``null`` so Pydantic accepts the same documents as
Zod's strict objects.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

LAYOUT_SCHEMA_VERSION = 1
LAYOUT_SCHEMA_ID = "https://erp.local/schema/document-layout.v1.json"

IDENTIFIER_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$"
COLOUR_PATTERN = r"^#[0-9a-fA-F]{6}$"
Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=IDENTIFIER_PATTERN)]
Colour = Annotated[str, Field(pattern=COLOUR_PATTERN)]
FieldKey = Annotated[str, Field(min_length=1, max_length=120)]
Length = Annotated[float, Field(ge=0, le=5000)]
PositiveLength = Annotated[float, Field(gt=0, le=5000)]

ComparisonOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains"]
PresenceOp = Literal["exists", "empty"]
ConditionOp = ComparisonOp | PresenceOp
ConditionValue = str | bool | int | float


class _Closed(BaseModel):
    """Strict object: unknown keys and explicit nulls are rejected."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _reject_null(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key, value in data.items():
                if value is None:
                    raise ValueError(f"{key} cannot be null")
        return data


class Rect(_Closed):
    x_mm: Length
    y_mm: Length
    w_mm: PositiveLength
    h_mm: PositiveLength


class FormatOptions(_Closed):
    calendar: Literal["ec", "gc", "both"] | None = None
    script: Literal["am", "en", "both"] | None = None
    money: Literal["etb"] | None = None
    date_pattern: Annotated[str, Field(min_length=1, max_length=40)] | None = None
    number_decimals: Annotated[int, Field(ge=0, le=6)] | None = None


class TextStyle(_Closed):
    font_family: Annotated[str, Field(min_length=1, max_length=100)]
    font_size_pt: Annotated[float, Field(ge=4, le=200)]
    bold: bool = False
    italic: bool = False
    underline: bool = False
    colour: Colour = "#111111"
    line_height: Annotated[float, Field(ge=0.5, le=4)] = 1.2
    letter_spacing_pt: Annotated[float, Field(ge=-2, le=10)] = 0


class Condition(_Closed):
    """A comparison, a presence check, or an ``all``/``any`` group.

    Zod models this as a recursive union; one closed model with an exact-shape
    validator accepts and rejects the same documents without the union needing
    a discriminator key.
    """

    op: ConditionOp | None = None
    field: FieldKey | None = None
    value: ConditionValue | None = None
    all: list[Condition] | None = None
    any: list[Condition] | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> Condition:
        groups = [name for name in ("all", "any") if getattr(self, name) is not None]
        if groups:
            if len(groups) > 1:
                raise ValueError("a condition group takes exactly one of all or any")
            if self.op is not None or self.field is not None or self.value is not None:
                raise ValueError("a condition group takes only all or any")
            children = getattr(self, groups[0])
            assert children is not None
            if not 1 <= len(children) <= 20:
                raise ValueError("a condition group needs between 1 and 20 conditions")
            return self
        if self.op is None or self.field is None:
            raise ValueError("a condition needs an operator and a field")
        if self.op in ("exists", "empty"):
            if self.value is not None:
                raise ValueError(f"{self.op} takes no value")
        elif self.value is None:
            raise ValueError(f"{self.op} needs a value")
        return self


Condition.model_rebuild()


class TableColumn(_Closed):
    key: Identifier
    label: Annotated[str, Field(min_length=1, max_length=120)]
    binding: FieldKey | None = None
    width_mm: Annotated[float, Field(gt=0, le=2000)] | None = None
    align: Literal["left", "center", "right"] = "left"
    format: FormatOptions | None = None


class TableSummary(_Closed):
    column: Identifier
    aggregate: Literal["sum", "average", "count"]
    label: Annotated[str, Field(min_length=1, max_length=120)]


class TableSpec(_Closed):
    source: FieldKey
    show_header: bool = True
    repeat_header: bool = True
    row_height_mm: Annotated[float, Field(ge=3, le=50)] = 6
    columns: Annotated[list[TableColumn], Field(min_length=1, max_length=30)]
    summaries: Annotated[list[TableSummary], Field(max_length=10)] = []

    @model_validator(mode="after")
    def _check_columns(self) -> TableSpec:
        seen: set[str] = set()
        for column in self.columns:
            if column.key in seen:
                raise ValueError(f'duplicate table column "{column.key}"')
            seen.add(column.key)
        for summary in self.summaries:
            if summary.column not in seen:
                raise ValueError(f'summary names unknown column "{summary.column}"')
        return self


class ImageSource(_Closed):
    kind: Literal["field", "file", "url"]
    value: Annotated[str, Field(min_length=1, max_length=500)]


class Stroke(_Closed):
    colour: Colour
    width_mm: Annotated[float, Field(ge=0, le=20)]


class _ElementBase(_Closed):
    id: Identifier
    rect: Rect
    z: Annotated[int, Field(ge=-1000, le=1000)] = 0
    rotation_deg: Annotated[float, Field(ge=-180, le=180)] = 0
    visible_when: Condition | None = None
    locked: bool = False


class TextElement(_ElementBase):
    type: Literal["text"]
    content: Annotated[str, Field(min_length=1, max_length=4000)]
    style: TextStyle
    align: Literal["left", "center", "right"] = "left"
    vertical_align: Literal["top", "middle", "bottom"] = "top"
    wrap: bool = True
    format: FormatOptions | None = None


class ImageElement(_ElementBase):
    type: Literal["image"]
    source: ImageSource
    fit: Literal["contain", "cover", "fill"] = "contain"
    alt: Annotated[str, Field(min_length=1, max_length=200)] | None = None


class ShapeElement(_ElementBase):
    type: Literal["shape"]
    shape: Literal["rect", "ellipse", "line"]
    fill: Colour | None = None
    stroke: Stroke | None = None
    radius_mm: Annotated[float, Field(ge=0, le=100)] = 0


class TableElement(_ElementBase):
    type: Literal["table"]
    table: TableSpec
    style: TextStyle


class QrElement(_ElementBase):
    type: Literal["qr"]
    data: Annotated[str, Field(min_length=1, max_length=500)]
    error_correction: Literal["L", "M", "Q", "H"] = "M"
    foreground: Colour = "#000000"
    background: Colour = "#ffffff"


class BarcodeElement(_ElementBase):
    type: Literal["barcode"]
    data: Annotated[str, Field(min_length=1, max_length=500)]
    symbology: Literal["code128", "code39", "ean13", "ean8"] = "code128"
    show_text: bool = True
    foreground: Colour = "#000000"
    background: Colour = "#ffffff"


Element = Annotated[
    TextElement | ImageElement | ShapeElement | TableElement | QrElement | BarcodeElement,
    Field(discriminator="type"),
]

ELEMENT_TYPES: tuple[str, ...] = (
    "text",
    "image",
    "shape",
    "table",
    "qr",
    "barcode",
)


class Margin(_Closed):
    top: Annotated[float, Field(ge=0, le=100)] = 12
    right: Annotated[float, Field(ge=0, le=100)] = 12
    bottom: Annotated[float, Field(ge=0, le=100)] = 12
    left: Annotated[float, Field(ge=0, le=100)] = 12


class Page(_Closed):
    size: Literal["A4", "A5", "Letter", "custom"]
    width_mm: PositiveLength | None = None
    height_mm: PositiveLength | None = None
    orientation: Literal["portrait", "landscape"] = "portrait"
    margins_mm: Margin = Field(default_factory=Margin)
    bleed_mm: Annotated[float, Field(ge=0, le=20)] = 0
    background_colour: Colour | None = None

    @model_validator(mode="after")
    def _check_size(self) -> Page:
        if self.size == "custom":
            if self.width_mm is None or self.height_mm is None:
                raise ValueError("a custom page needs width_mm and height_mm")
        elif self.width_mm is not None or self.height_mm is not None:
            raise ValueError("a preset page takes its dimensions from the preset")
        return self


class Font(_Closed):
    family: Annotated[str, Field(min_length=1, max_length=100)]
    file_id: UUID | None = None
    fallback: Annotated[str, Field(min_length=1, max_length=100)] | None = None


class Layout(_Closed):
    version: Literal[1]
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    page: Page
    fonts: Annotated[list[Font], Field(max_length=10)] = []
    elements: Annotated[list[Element], Field(max_length=500)] = []

    @model_validator(mode="after")
    def _check_ids(self) -> Layout:
        seen: set[str] = set()
        for element in self.elements:
            if element.id in seen:
                raise ValueError(f'duplicate element id "{element.id}"')
            seen.add(element.id)
        return self


def validate_layout(value: Any) -> Layout:
    """Parse a layout, rejecting anything the schema does not describe."""
    return Layout.model_validate(value)


__all__ = [
    "LAYOUT_SCHEMA_ID",
    "LAYOUT_SCHEMA_VERSION",
    "ELEMENT_TYPES",
    "BarcodeElement",
    "Condition",
    "Element",
    "Font",
    "FormatOptions",
    "ImageElement",
    "ImageSource",
    "Layout",
    "Margin",
    "Page",
    "QrElement",
    "Rect",
    "ShapeElement",
    "Stroke",
    "TableColumn",
    "TableElement",
    "TableSpec",
    "TableSummary",
    "TextElement",
    "TextStyle",
    "validate_layout",
]
