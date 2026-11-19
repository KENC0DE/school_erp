"""Optimistic concurrency for mutable rows (ARCH §5.1).

Every business row carries ``row_version``. Updates send the version they read;
a mismatch returns ``409 CONFLICT`` with the current state instead of silently
overwriting somebody else's change.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.errors import NotFound, VersionConflict, VersionRequired


def parse_if_match(header: str | None) -> int | None:
    """Read an ``If-Match`` header (``"3"``, ``3`` or ``W/"3"``)."""
    if header is None or not header.strip():
        return None
    value = header.strip()
    if value.startswith("W/"):
        value = value[2:]
    value = value.strip().strip('"')
    try:
        return int(value)
    except ValueError as exc:
        raise VersionRequired(
            "If-Match must contain an integer row_version",
            details={"if_match": header},
        ) from exc


def version_from_payload(payload: Mapping[str, Any], *, field: str = "row_version") -> int:
    """Read the expected version from a request body and reject a missing value."""
    value = payload.get(field)
    if value is None:
        raise VersionRequired(
            f"{field} is required for this update",
            details={"field": field},
        )
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise VersionRequired(
            f"{field} must be an integer",
            details={"field": field, "value": value},
        ) from exc
    if version < 1:
        raise VersionRequired(
            f"{field} must be positive",
            details={"field": field, "value": value},
        )
    return version


def ensure_row_version(
    entity: Any,
    expected: int,
    *,
    current_state: Mapping[str, Any] | None = None,
) -> None:
    """Raise ``409 CONFLICT`` with the current state when the version is stale."""
    if entity is None:
        raise NotFound()
    actual = getattr(entity, "row_version", None)
    if actual is None:
        raise VersionRequired("This entity does not support row_version")
    if actual != expected:
        details: dict[str, Any] = {"expected": expected, "current": actual}
        if current_state is not None:
            details["state"] = dict(current_state)
        raise VersionConflict(
            "The record changed since it was loaded",
            details=details,
        )


def apply_row_version(
    entity: Any,
    expected: int,
    values: Mapping[str, Any],
    *,
    current_state: Mapping[str, Any] | None = None,
    allowed: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """Check the version, apply allowed fields and increment the version.

    Returns the changed fields as ``{key: value}`` so callers can write a precise
    audit entry.
    """
    ensure_row_version(entity, expected, current_state=current_state)
    changes: dict[str, Any] = {}
    for key, value in values.items():
        if allowed is not None and key not in allowed:
            continue
        if getattr(entity, key) == value:
            continue
        setattr(entity, key, value)
        changes[key] = value
    if changes:
        entity.row_version = (entity.row_version or 0) + 1
    return changes


__all__ = [
    "apply_row_version",
    "ensure_row_version",
    "parse_if_match",
    "version_from_payload",
]
