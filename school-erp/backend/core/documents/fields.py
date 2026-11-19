"""Document fields offered to Document Studio (P4-17, extended in P5-02).

A module declares the values it can bind into a layout as a tuple of
``DocumentField`` objects on its manifest. Keeping the declaration here, rather
than in a template, means a field can only appear if the module that owns the
data is enabled and can format it correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

FieldKind = Literal["text", "integer", "decimal", "date", "boolean", "table"]
FIELD_KINDS: tuple[FieldKind, ...] = ("text", "integer", "decimal", "date", "boolean", "table")


@dataclass(frozen=True)
class DocumentField:
    """One bindable value with its sample and formatting hints."""

    key: str
    label_key: str
    kind: FieldKind = "text"
    # Formatting dimensions the renderer understands: calendar (EC/GC/both),
    # script (am/en) and money (ETB). An empty tuple means the field is not
    # user-formatted.
    formats: tuple[str, ...] = ()
    sample: Any = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label_key": self.label_key,
            "kind": self.kind,
            "formats": list(self.formats),
            "sample": self.sample,
        }


__all__ = ["FIELD_KINDS", "DocumentField", "FieldKind"]
