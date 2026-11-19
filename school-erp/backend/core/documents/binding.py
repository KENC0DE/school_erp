"""Binding layout tokens to data (P5-03).

Text elements hold literals with ``{{field}}`` tokens. This module resolves a
dotted path, applies the element's format options (or a ``|filter`` from the
token itself) and returns text the HTML renderer can escape.

Numbers are formatted from ``Decimal`` text, never from float arithmetic, so a
mark or an amount prints exactly as the snapshot stored it. Dates accept real
``date``/``datetime`` values and ISO strings, because a stored data snapshot is
JSON and arrives as text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from core.calendar.ethiopian import (
    format_dual,
    format_ethiopian,
    from_gregorian,
)

TOKEN = re.compile(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*(?:\|\s*([A-Za-z]+)\s*)?\}\}")
CALENDAR_FILTERS = {"ec": "ec", "gc": "gc", "both": "both"}
SCRIPT_FILTERS = {"am": "am", "en": "en"}
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ].*)?$")
MISSING = object()


def resolve_path(data: Any, path: str) -> Any:
    """Walk a dotted path through mappings; ``MISSING`` when absent."""
    current = data
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return MISSING
        current = current[part]
    return current


def _script(value: str | None) -> str:
    return value if value in {"am", "en"} else "en"


def resolve_field(data: Any, path: str, script: str = "en") -> Any:
    """Resolve a field, preferring a script-specific variant when present.

    A dataset that carries ``student.full_name`` and ``student.full_name_am``
    lets a template ask for Amharic names with ``script: am``; a dataset with
    only the base key still renders.
    """
    if script in {"am", "en"}:
        head, _, tail = path.rpartition(".")
        variant = f"{head}.{tail}_{script}" if head else f"{path}_{script}"
        value = resolve_path(data, variant)
        if value is not MISSING:
            return value
    return resolve_path(data, path)


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and _ISO_DATE.match(value):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        for prefix in ("ETB", "ብር", "Br"):
            if text.startswith(prefix):
                text = text[len(prefix) :].strip()
        try:
            return Decimal(text)
        except InvalidOperation:
            return None
    return None


def _plain_decimal(number: Decimal) -> str:
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def format_value(
    value: Any,
    *,
    calendar: str | None = None,
    script: str | None = None,
    money: bool = False,
    decimals: int | None = None,
    pattern: str | None = None,
) -> str:
    """Format one bound value using the options the layout declared."""
    language = _script(script)
    moment = _parse_date(value)
    if moment is not None:
        if calendar == "ec":
            return format_ethiopian(*from_gregorian(moment), locale=language)
        if calendar == "both":
            return format_dual(moment, "both", locale=language)
        return moment.strftime(pattern or "%d %b %Y")

    if isinstance(value, bool):
        if language == "am":
            return "አዎ" if value else "አይ"
        return "Yes" if value else "No"

    number = _decimal(value)
    if number is not None:
        if money:
            places = 2 if decimals is None else decimals
            return f"ETB {number:,.{places}f}"
        if decimals is not None:
            return f"{number:,.{decimals}f}"
        return _plain_decimal(number)

    return "" if value is None or value is MISSING else str(value)


def format_with_options(
    value: Any,
    options: Any,
    filter_name: str | None = None,
    default_script: str = "en",
) -> str:
    """Apply an element's ``FormatOptions`` and an optional token filter.

    ``default_script`` is the document language: an Amharic document prints
    ``አዎ`` and Ethiopian month names even when the element names no script.
    """
    calendar = CALENDAR_FILTERS.get(filter_name or "")
    money = filter_name == "etb"
    script = SCRIPT_FILTERS.get(filter_name or "")
    decimals = getattr(options, "number_decimals", None)
    pattern = getattr(options, "date_pattern", None)
    if calendar is None:
        calendar = getattr(options, "calendar", None)
    if script is None:
        script = getattr(options, "script", None) or default_script
    if not money:
        money = getattr(options, "money", None) == "etb"
    return format_value(
        value,
        calendar=calendar,
        script=script,
        money=money,
        decimals=decimals,
        pattern=pattern,
    )


def render_tokens(
    text: str,
    data: Any,
    options: Any = None,
    default_script: str = "en",
) -> str:
    """Substitute tokens in literal text, leaving the literals untouched."""
    pieces: list[str] = []
    cursor = 0
    for match in TOKEN.finditer(text):
        pieces.append(text[cursor : match.start()])
        path, filter_name = match.group(1), match.group(2)
        script = SCRIPT_FILTERS.get(filter_name or "") or getattr(options, "script", None) or default_script
        value = resolve_field(data, path, _script(script))
        if value is not MISSING:
            pieces.append(format_with_options(value, options, filter_name, default_script=default_script))
        cursor = match.end()
    pieces.append(text[cursor:])
    return "".join(pieces)


def _comparable(value: Any) -> Any:
    number = _decimal(value)
    if number is not None:
        return number
    return value


def _compare(left: Any, right: Any, op: str) -> bool:
    if op == "contains":
        if isinstance(left, str):
            return str(right) in left
        if isinstance(left, (list, tuple, set)):
            return right in left
        return False
    a, b = _comparable(left), _comparable(right)
    if op == "eq":
        return a == b
    if op == "ne":
        return a != b
    try:
        if op == "gt":
            return a > b
        if op == "gte":
            return a >= b
        if op == "lt":
            return a < b
        if op == "lte":
            return a <= b
    except TypeError:
        return False
    return False


def condition_is_true(condition: Any, data: Any) -> bool:
    """Evaluate one recursive condition against the bound data."""
    if condition is None:
        return True
    group_all = getattr(condition, "all", None)
    if group_all is not None:
        return all(condition_is_true(item, data) for item in group_all)
    group_any = getattr(condition, "any", None)
    if group_any is not None:
        return any(condition_is_true(item, data) for item in group_any)
    value = resolve_field(data, condition.field, "en")
    missing = value is MISSING
    if condition.op == "exists":
        return not missing and value is not None and value != ""
    if condition.op == "empty":
        return missing or value is None or value == ""
    if missing:
        return False
    return _compare(value, condition.value, condition.op)


__all__ = [
    "CALENDAR_FILTERS",
    "MISSING",
    "SCRIPT_FILTERS",
    "TOKEN",
    "condition_is_true",
    "format_value",
    "format_with_options",
    "render_tokens",
    "resolve_field",
    "resolve_path",
]
