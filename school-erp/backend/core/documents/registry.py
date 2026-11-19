"""Collecting the document fields that enabled modules offer (P5-02).

Each module declares the values it can bind into a layout on its manifest
(``ModuleManifest.document_fields``). The editor asks the server for the union
of those declarations, which means a field can only appear while the module
that owns it is available: disabling assessment removes every
``student.marks.*`` field without the editor knowing anything about modules.

The registry is deliberately a pure function over manifests and module states
so it can be unit-tested without a database; ``core.documents.service`` wires
it to the live gate state.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from core.documents.fields import FIELD_KINDS, DocumentField
from core.modules.manifest import ModuleManifest

# The formatting dimensions the renderer understands. A field advertises the
# dimensions that make sense for its value; the editor offers only those.
FORMAT_OPTIONS: dict[str, tuple[str, ...]] = {
    "calendar": ("ec", "gc", "both"),
    "script": ("am", "en"),
    "money": ("etb",),
}


@dataclass(frozen=True)
class RegisteredField:
    """A field together with the module that offered it."""

    module: str
    field: DocumentField

    def to_dict(self) -> dict[str, Any]:
        return {**self.field.to_dict(), "module": self.module}


def _check_field(module: str, document_field: DocumentField) -> None:
    if document_field.kind not in FIELD_KINDS:
        raise ValueError(
            f"module '{module}' declares field '{document_field.key}' "
            f"with unknown kind '{document_field.kind}'"
        )
    unknown = [fmt for fmt in document_field.formats if fmt not in FORMAT_OPTIONS]
    if unknown:
        raise ValueError(
            f"module '{module}' declares field '{document_field.key}' with unknown format(s) {unknown}"
        )


def collect_fields(
    manifests: Iterable[ModuleManifest],
    states: Mapping[str, Mapping[str, Any]],
) -> list[RegisteredField]:
    """Every field from an available module, in module then declaration order.

    Duplicate keys are a manifest bug, not a merge decision: two modules that
    both claim ``student.full_name`` would make the renderer's binding
    ambiguous, so the registry refuses to start a request with such a set.
    """
    registered: list[RegisteredField] = []
    seen: dict[str, str] = {}
    for manifest in manifests:
        if not states.get(manifest.key, {}).get("available", False):
            continue
        for document_field in manifest.document_fields:
            _check_field(manifest.key, document_field)
            if document_field.key in seen:
                raise ValueError(
                    f"field '{document_field.key}' is declared by both "
                    f"'{seen[document_field.key]}' and '{manifest.key}'"
                )
            seen[document_field.key] = manifest.key
            registered.append(RegisteredField(module=manifest.key, field=document_field))
    return registered


__all__ = ["FORMAT_OPTIONS", "RegisteredField", "collect_fields"]
