"""Custom field definitions and validated values (P1-17)."""

from __future__ import annotations

import re
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.service import record
from core.auth.principal import Principal
from core.custom_fields.models import (
    ENTITY_TYPES,
    FIELD_TYPES,
    OPTION_TYPES,
    CustomFieldDef,
)
from core.custom_fields.validation import validate_custom_values
from core.db.soft_delete import get_live, soft_delete
from core.rbac.models import Role

KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
GROUP_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
LABEL_PATTERN = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")


def _view(defn: CustomFieldDef) -> dict[str, Any]:
    return {
        "id": str(defn.id),
        "entity_type": defn.entity_type,
        "key": defn.key,
        "label_key": defn.label_key,
        "help_key": defn.help_key,
        "field_type": defn.field_type,
        "required": defn.required,
        "options": defn.options or [],
        "min_value": defn.min_value,
        "max_value": defn.max_value,
        "max_length": defn.max_length,
        "pattern": defn.pattern,
        "visible_roles": defn.visible_roles or [],
        "active": defn.active,
        "order": defn.order,
        "group_key": defn.group_key,
        "row_version": defn.row_version,
    }


def is_visible(defn: CustomFieldDef, principal: Principal | None) -> bool:
    """A definition with no roles is visible to every permitted user."""
    roles = defn.visible_roles or []
    if not roles or principal is None:
        return True
    if "*" in principal.permissions:
        return True
    return bool(set(principal.roles) & {str(role) for role in roles})


async def definitions_for(
    session: AsyncSession,
    entity_type: str,
    *,
    principal: Principal | None = None,
    include_hidden: bool = False,
    active_only: bool = True,
) -> list[CustomFieldDef]:
    stmt = select(CustomFieldDef).where(CustomFieldDef.entity_type == entity_type)
    if active_only:
        stmt = stmt.where(CustomFieldDef.active.is_(True))
    stmt = stmt.order_by(CustomFieldDef.order, CustomFieldDef.key)
    rows = list((await session.execute(stmt)).scalars().all())
    if include_hidden or principal is None:
        return rows
    return [row for row in rows if is_visible(row, principal)]


async def list_entity_types(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(CustomFieldDef.entity_type).where(CustomFieldDef.active.is_(True)).distinct()
        )
    ).scalars()
    used = set(rows)
    return [
        {"entity_type": key, "label_key": label, "fields": key in used}
        for key, label in ENTITY_TYPES.items()
    ]


async def _require_entity_type(entity_type: str) -> None:
    if entity_type not in ENTITY_TYPES:
        raise ValidationFailed(
            "Unknown entity type for custom fields",
            message_key="error.custom_field.entity_type",
            details={"entity_type": entity_type},
        )


async def _check_roles(session: AsyncSession, roles: list[str] | None) -> list[str] | None:
    if roles is None:
        return None
    cleaned = list(dict.fromkeys(str(role).strip() for role in roles if str(role).strip()))
    if not cleaned:
        return []
    known = set(
        (await session.execute(select(Role.key).where(Role.key.in_(cleaned), Role.is_active.is_(True))))
        .scalars()
        .all()
    )
    missing = [role for role in cleaned if role not in known]
    if missing:
        raise ValidationFailed(
            "Unknown role in custom field visibility",
            message_key="error.custom_field.unknown_role",
            details={"roles": missing},
        )
    return cleaned


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    field_type = payload.get("field_type")
    if field_type not in FIELD_TYPES:
        raise ValidationFailed(
            "Unknown custom field type",
            message_key="error.custom_field.field_type",
            details={"field_type": field_type},
        )
    key = str(payload.get("key") or "").strip()
    if not KEY_PATTERN.fullmatch(key):
        raise ValidationFailed(
            "Custom field keys are lowercase snake_case",
            message_key="error.custom_field.key",
            details={"key": key},
        )
    label_key = str(payload.get("label_key") or "").strip()
    if not LABEL_PATTERN.fullmatch(label_key):
        raise ValidationFailed(
            "Labels must reference an i18n key",
            message_key="error.custom_field.label_key",
            details={"label_key": label_key},
        )
    help_key = payload.get("help_key")
    if help_key is not None:
        help_key = str(help_key).strip() or None
        if help_key is not None and not LABEL_PATTERN.fullmatch(help_key):
            raise ValidationFailed(
                "Help text must reference an i18n key",
                message_key="error.custom_field.label_key",
                details={"help_key": help_key},
            )
    group_key = payload.get("group_key")
    if group_key is not None:
        group_key = str(group_key).strip() or None
        if group_key is not None and not GROUP_PATTERN.fullmatch(group_key):
            raise ValidationFailed(
                "Group keys are lowercase snake_case",
                message_key="error.custom_field.group",
                details={"group_key": group_key},
            )

    options = payload.get("options")
    if field_type in OPTION_TYPES:
        if not isinstance(options, list) or not options:
            raise ValidationFailed(
                "Choice fields need at least one option",
                message_key="error.custom_field.options",
            )
        options = list(dict.fromkeys(str(option).strip() for option in options if str(option).strip()))
        if not options:
            raise ValidationFailed(
                "Choice fields need at least one option",
                message_key="error.custom_field.options",
            )
    else:
        options = None

    min_value = payload.get("min_value")
    max_value = payload.get("max_value")
    if field_type not in {"integer", "number"}:
        min_value = max_value = None
    else:
        for name, value in (("min", min_value), ("max", max_value)):
            if value is None:
                continue
            try:
                Decimal(str(value))
            except InvalidOperation as exc:
                raise ValidationFailed(
                    "Numeric bounds must be numbers",
                    message_key="error.custom_field.bound",
                    details={"bound": name},
                ) from exc
        if min_value is not None and max_value is not None:
            if Decimal(str(min_value)) > Decimal(str(max_value)):
                raise ValidationFailed(
                    "The minimum cannot be greater than the maximum",
                    message_key="error.custom_field.bound_order",
                )

    max_length = payload.get("max_length")
    if field_type not in {"text", "long_text"}:
        max_length = None
    elif max_length is not None and int(max_length) < 1:
        raise ValidationFailed(
            "Maximum length must be positive",
            message_key="error.custom_field.max_length_rule",
        )

    pattern = payload.get("pattern")
    if field_type not in {"text", "long_text"}:
        pattern = None
    elif pattern:
        try:
            re.compile(str(pattern))
        except re.error as exc:
            raise ValidationFailed(
                "The pattern is not a valid regular expression",
                message_key="error.custom_field.pattern_rule",
            ) from exc

    return {
        "key": key,
        "label_key": label_key,
        "help_key": help_key,
        "field_type": field_type,
        "required": bool(payload.get("required", False)),
        "options": options,
        "min_value": None if min_value is None else str(min_value),
        "max_value": None if max_value is None else str(max_value),
        "max_length": max_length,
        "pattern": pattern,
        "active": bool(payload.get("active", True)),
        "order": int(payload.get("order", 0)),
        "group_key": group_key,
    }


async def _ensure_unique(
    session: AsyncSession,
    entity_type: str,
    key: str,
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    stmt = select(CustomFieldDef).where(
        CustomFieldDef.entity_type == entity_type,
        CustomFieldDef.key == key,
    )
    if exclude_id is not None:
        stmt = stmt.where(CustomFieldDef.id != exclude_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "A field with this key already exists for the entity",
            message_key="error.custom_field.duplicate_key",
            details={"entity_type": entity_type, "key": key},
        )


async def create_definition(
    session: AsyncSession,
    principal: Principal,
    entity_type: str,
    payload: dict[str, Any],
    *,
    via: str | None = None,
) -> CustomFieldDef:
    await _require_entity_type(entity_type)
    values = _clean_payload(payload)
    await _ensure_unique(session, entity_type, values["key"])
    visible_roles = await _check_roles(session, payload.get("visible_roles"))
    defn = CustomFieldDef(entity_type=entity_type, visible_roles=visible_roles, **values)
    session.add(defn)
    await session.flush()
    await record(
        session,
        action="custom_fields.create",
        module="core",
        entity_type="custom_field_def",
        entity_id=str(defn.id),
        after=_view(defn),
        actor=principal,
        via=via,
    )
    await session.commit()
    return defn


async def update_definition(
    session: AsyncSession,
    principal: Principal,
    field_id: uuid.UUID,
    payload: dict[str, Any],
    *,
    via: str | None = None,
) -> CustomFieldDef:
    defn = await get_live(session, CustomFieldDef, field_id)
    before = _view(defn)
    merged = {**_view(defn), **payload}
    merged["key"] = merged.get("key") or defn.key
    values = _clean_payload(merged)
    if values["key"] != defn.key:
        await _ensure_unique(session, defn.entity_type, values["key"], exclude_id=defn.id)
    visible_roles = (
        await _check_roles(session, payload["visible_roles"])
        if "visible_roles" in payload
        else defn.visible_roles
    )
    for name, value in values.items():
        setattr(defn, name, value)
    defn.visible_roles = visible_roles
    defn.row_version = (defn.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="custom_fields.update",
        module="core",
        entity_type="custom_field_def",
        entity_id=str(defn.id),
        before=before,
        after=_view(defn),
        actor=principal,
        via=via,
    )
    await session.commit()
    return defn


async def delete_definition(
    session: AsyncSession,
    principal: Principal,
    field_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str | None = None,
) -> None:
    defn = await get_live(session, CustomFieldDef, field_id)
    await soft_delete(
        session,
        defn,
        action="custom_fields.delete",
        module="core",
        actor=principal,
        reason=reason,
        via=via,
        entity_type="custom_field_def",
    )
    await session.commit()


def merge_custom(existing: dict | None, cleaned: dict) -> dict:
    """Merge validated values, dropping keys the caller cleared."""
    merged = dict(existing or {})
    for key, value in cleaned.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


async def validate_entity_values(
    session: AsyncSession,
    entity_type: str,
    values: object,
    *,
    partial: bool = False,
) -> dict:
    """Validate and return cleaned values, or raise with per-field errors."""
    await _require_entity_type(entity_type)
    definitions = await definitions_for(session, entity_type, include_hidden=True)
    cleaned, errors = validate_custom_values(definitions, values, partial=partial)
    if errors:
        raise ValidationFailed(
            "Custom field values are invalid",
            message_key="error.custom_field.invalid",
            details={"errors": errors},
        )
    return cleaned


def definition_view(defn: CustomFieldDef) -> dict[str, Any]:
    return _view(defn)


async def get_definition(session: AsyncSession, field_id: uuid.UUID) -> CustomFieldDef:
    defn = await get_live(session, CustomFieldDef, field_id)
    if defn is None:  # pragma: no cover - get_live already raises
        raise NotFound()
    return defn


__all__ = [
    "create_definition",
    "definition_view",
    "definitions_for",
    "delete_definition",
    "get_definition",
    "is_visible",
    "list_entity_types",
    "merge_custom",
    "update_definition",
    "validate_entity_values",
]
