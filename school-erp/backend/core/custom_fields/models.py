"""Per-entity custom field definitions (ARCH §5.6, P1-17).

Values live in the owning entity's ``custom`` JSON column; this module only
defines the fields and validates values, so a module can add custom fields
without a schema migration.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import BusinessModel, JSONType

TEXT = "text"
LONG_TEXT = "long_text"
INTEGER = "integer"
NUMBER = "number"
BOOLEAN = "boolean"
DATE = "date"
SELECT = "select"
MULTISELECT = "multiselect"

FIELD_TYPES = (TEXT, LONG_TEXT, INTEGER, NUMBER, BOOLEAN, DATE, SELECT, MULTISELECT)
OPTION_TYPES = (SELECT, MULTISELECT)

# Entities that may carry custom fields. Extend the map as modules land; the
# value is the i18n key used by the admin screens.
ENTITY_TYPES: dict[str, str] = {
    "person": "custom.entity.person",
    "student": "custom.entity.student",
    "staff": "custom.entity.staff",
    "guardian": "custom.entity.guardian",
    "admission_application": "custom.entity.admission_application",
}


class CustomFieldDef(BusinessModel):
    __tablename__ = "custom_field_defs"
    __table_args__ = (UniqueConstraint("entity_type", "key", name="uq_custom_field_defs_entity_key"),)

    entity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    label_key: Mapped[str] = mapped_column(String(160), nullable=False)
    help_key: Mapped[str | None] = mapped_column(String(160))
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[list | None] = mapped_column(JSONType)
    min_value: Mapped[str | None] = mapped_column(Text)
    max_value: Mapped[str | None] = mapped_column(Text)
    max_length: Mapped[int | None] = mapped_column(Integer)
    pattern: Mapped[str | None] = mapped_column(String(200))
    visible_roles: Mapped[list | None] = mapped_column(JSONType)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    group_key: Mapped[str | None] = mapped_column(String(80))


__all__ = [
    "BOOLEAN",
    "DATE",
    "ENTITY_TYPES",
    "FIELD_TYPES",
    "INTEGER",
    "LONG_TEXT",
    "MULTISELECT",
    "NUMBER",
    "OPTION_TYPES",
    "SELECT",
    "TEXT",
    "CustomFieldDef",
]
