"""Type-safe validation for custom field values (P1-17).

Validation is deliberately strict and never coerces floats: money and marks
must not lose precision, so numeric fields accept strings or integers and store
a canonical decimal string. Errors carry an i18n ``message_key`` plus the
parameters needed to render them; no user-facing text is built here.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from core.custom_fields.models import (
    BOOLEAN,
    DATE,
    INTEGER,
    LONG_TEXT,
    NUMBER,
    OPTION_TYPES,
    SELECT,
    TEXT,
    CustomFieldDef,
)

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _error(field: str, code: str, **params: object) -> dict:
    return {
        "field": field,
        "code": code,
        "message_key": f"error.custom_field.{code.lower()}",
        "params": params,
    }


def _as_decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or isinstance(value, float):
        return None
    if isinstance(value, (int, Decimal)):
        return Decimal(value)
    if isinstance(value, str):
        try:
            parsed = Decimal(value.strip())
        except InvalidOperation:
            return None
        return parsed if parsed.is_finite() else None
    return None


def _decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return "0" if text in {"-0", "-0.0"} else text


def _validate_one(defn: CustomFieldDef, value: object) -> tuple[object, dict | None]:
    if defn.field_type in (TEXT, LONG_TEXT):
        if not isinstance(value, str):
            return None, _error(defn.key, "TYPE", type="text")
        text = value.strip()
        if defn.max_length is not None and len(text) > defn.max_length:
            return None, _error(defn.key, "MAX_LENGTH", max=defn.max_length)
        if defn.pattern and text and not re.fullmatch(defn.pattern, text):
            return None, _error(defn.key, "PATTERN")
        return (text or None), None

    if defn.field_type == INTEGER:
        if isinstance(value, bool) or isinstance(value, float):
            return None, _error(defn.key, "TYPE", type="integer")
        try:
            integer = int(value) if not isinstance(value, str) else int(value.strip())
        except (TypeError, ValueError):
            return None, _error(defn.key, "TYPE", type="integer")
        if isinstance(value, str) and str(integer) != value.strip().lstrip("+"):
            return None, _error(defn.key, "TYPE", type="integer")
        return integer, _bounds(defn, Decimal(integer))

    if defn.field_type == NUMBER:
        number = _as_decimal(value)
        if number is None:
            return None, _error(defn.key, "TYPE", type="number")
        error = _bounds(defn, number)
        return (None if error else _decimal_text(number)), error

    if defn.field_type == BOOLEAN:
        if not isinstance(value, bool):
            return None, _error(defn.key, "TYPE", type="boolean")
        return value, None

    if defn.field_type == DATE:
        if not isinstance(value, str) or not ISO_DATE.fullmatch(value):
            return None, _error(defn.key, "TYPE", type="date")
        try:
            date.fromisoformat(value)
        except ValueError:
            return None, _error(defn.key, "TYPE", type="date")
        return value, None

    if defn.field_type in OPTION_TYPES:
        options = [str(option) for option in (defn.options or [])]
        if defn.field_type == SELECT:
            if not isinstance(value, str) or value not in options:
                return None, _error(defn.key, "OPTION")
            return value, None
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            return None, _error(defn.key, "TYPE", type="multiselect")
        chosen = list(dict.fromkeys(value))
        if any(item not in options for item in chosen):
            return None, _error(defn.key, "OPTION")
        return chosen or None, None

    return None, _error(defn.key, "TYPE")


def _bounds(defn: CustomFieldDef, number: Decimal) -> dict | None:
    if defn.min_value is not None and number < Decimal(str(defn.min_value)):
        return _error(defn.key, "MIN", min=str(defn.min_value))
    if defn.max_value is not None and number > Decimal(str(defn.max_value)):
        return _error(defn.key, "MAX", max=str(defn.max_value))
    return None


def validate_custom_values(
    definitions: list[CustomFieldDef],
    values: object,
    *,
    partial: bool = False,
) -> tuple[dict, list[dict]]:
    """Validate ``values`` against ``definitions``.

    Returns ``(cleaned, errors)``. ``cleaned`` only contains keys that were
    supplied; a cleared value is ``None`` so the caller can remove it from the
    merged JSON object. With ``partial=True`` missing required fields are
    allowed (updates), but supplied values are still fully checked.
    """
    if values is None:
        values = {}
    if not isinstance(values, dict):
        return {}, [_error("", "TYPE", type="object")]

    active = [defn for defn in definitions if defn.active]
    by_key = {defn.key: defn for defn in active}
    errors: list[dict] = []
    cleaned: dict = {}

    for key in values:
        if key not in by_key:
            errors.append(_error(str(key), "UNKNOWN"))

    for defn in active:
        present = defn.key in values and values[defn.key] not in (None, "")
        if not present:
            if defn.required and not partial:
                errors.append(_error(defn.key, "REQUIRED"))
            elif defn.key in values:
                cleaned[defn.key] = None
            continue
        value, error = _validate_one(defn, values[defn.key])
        if error is not None:
            errors.append(error)
        else:
            cleaned[defn.key] = value

    return cleaned, errors


__all__ = ["ISO_DATE", "validate_custom_values"]
