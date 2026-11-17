"""Custom fields engine (ARCH §5.6)."""

from core.custom_fields.models import ENTITY_TYPES, FIELD_TYPES, CustomFieldDef
from core.custom_fields.service import (
    create_definition,
    definitions_for,
    delete_definition,
    merge_custom,
    update_definition,
    validate_entity_values,
)
from core.custom_fields.validation import validate_custom_values

__all__ = [
    "ENTITY_TYPES",
    "FIELD_TYPES",
    "CustomFieldDef",
    "create_definition",
    "definitions_for",
    "delete_definition",
    "merge_custom",
    "update_definition",
    "validate_custom_values",
    "validate_entity_values",
]
