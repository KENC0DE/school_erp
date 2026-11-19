"""Pagination, filtering and sorting helpers (ARCH §5.1).

Every list endpoint returns the same envelope ``{items, next_cursor, total?}``
and accepts the same ``limit`` / ``cursor`` / ``sort`` / ``order`` parameters.
Cursors are opaque, base64url-encoded keyset positions so pages stay stable when
rows are inserted between requests.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from app.errors import InvalidCursor, InvalidFilter, InvalidSort
from fastapi import Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, and_, asc, desc, or_
from sqlalchemy.sql.elements import ColumnElement

DEFAULT_LIMIT = 25
MAX_LIMIT = 200

SortOrder = Literal["asc", "desc"]


class Page[T](BaseModel):
    """The standard list envelope. ``total`` is optional for cheap keyset pages."""

    items: list[T] = Field(default_factory=list)
    next_cursor: str | None = None
    total: int | None = None


@dataclass(frozen=True)
class PageParams:
    limit: int = DEFAULT_LIMIT
    cursor: str | None = None
    sort: str | None = None
    order: SortOrder = "desc"


def page_params(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    cursor: str | None = Query(None, max_length=1000),
    sort: str | None = Query(None, max_length=60),
    order: SortOrder = Query("desc"),
) -> PageParams:
    """FastAPI dependency declaring the shared query parameters."""
    return PageParams(limit=limit, cursor=cursor, sort=sort, order=order)


@dataclass(frozen=True)
class FilterSpec:
    """One explicitly declared filter parameter."""

    column: Any
    kind: Literal["eq", "contains", "gte", "lte"] = "eq"


_WILDCARD_ESCAPE = "\\"


def _escape_like(value: str) -> str:
    return (
        value.replace(_WILDCARD_ESCAPE, _WILDCARD_ESCAPE + _WILDCARD_ESCAPE)
        .replace("%", _WILDCARD_ESCAPE + "%")
        .replace("_", _WILDCARD_ESCAPE + "_")
    )


def contains(column: Any, value: str) -> ColumnElement[bool]:
    """Case-insensitive substring match that does not treat user input as wildcards."""
    return column.ilike(f"%{_escape_like(value)}%", escape=_WILDCARD_ESCAPE)


def apply_filters(
    stmt: Select[Any],
    specs: dict[str, FilterSpec],
    values: dict[str, Any],
) -> Select[Any]:
    """Apply only the filters the router declared, rejecting unknown names."""
    for name, value in values.items():
        if value is None or value == "":
            continue
        spec = specs.get(name)
        if spec is None:
            raise InvalidFilter(
                f"Unknown filter {name}",
                details={"filter": name, "allowed": sorted(specs)},
            )
        if spec.kind == "contains":
            stmt = stmt.where(contains(spec.column, str(value)))
        elif spec.kind == "gte":
            stmt = stmt.where(spec.column >= value)
        elif spec.kind == "lte":
            stmt = stmt.where(spec.column <= value)
        else:
            stmt = stmt.where(spec.column == value)
    return stmt


def _encode_scalar(value: Any) -> dict[str, Any]:
    if isinstance(value, datetime):
        return {"t": "datetime", "v": value.isoformat()}
    if isinstance(value, date):
        return {"t": "date", "v": value.isoformat()}
    if isinstance(value, UUID):
        return {"t": "uuid", "v": str(value)}
    if isinstance(value, Decimal):
        return {"t": "decimal", "v": str(value)}
    if value is None or isinstance(value, (str, int, float, bool)):
        return {"t": "raw", "v": value}
    raise TypeError(f"Unsupported cursor value: {type(value)!r}")


def _decode_scalar(payload: dict[str, Any]) -> Any:
    kind = payload.get("t")
    value = payload.get("v")
    if kind == "datetime":
        return datetime.fromisoformat(str(value))
    if kind == "date":
        return date.fromisoformat(str(value))
    if kind == "uuid":
        return UUID(str(value))
    if kind == "decimal":
        return Decimal(str(value))
    return value


def encode_cursor(values: list[Any], *, sort: str, order: SortOrder) -> str:
    """Encode the last row's sort value and primary key as an opaque cursor."""
    payload = {
        "v": [_encode_scalar(value) for value in values],
        "s": sort,
        "o": order,
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, *, sort: str, order: SortOrder, count: int) -> list[Any]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload.get("s") != sort or payload.get("o") != order:
            raise ValueError("cursor belongs to a different sort")
        encoded = payload["v"]
        if len(encoded) != count:
            raise ValueError("cursor has the wrong shape")
        return [_decode_scalar(item) for item in encoded]
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise InvalidCursor(
            "The pagination cursor is invalid",
            details={"reason": str(exc)},
        ) from exc


async def paginate(
    session: Any,
    stmt: Select[Any],
    params: PageParams,
    *,
    sort_columns: dict[str, Any],
    default_sort: str,
    id_column: Any,
) -> tuple[list[Any], str | None]:
    """Apply keyset sorting and return one page plus the next cursor.

    ``sort_columns`` maps public sort names to ORM columns. The primary key is
    always the tie-breaker so equal sort values cannot be skipped or repeated.
    """
    sort_key = params.sort or default_sort
    column = sort_columns.get(sort_key)
    if column is None:
        raise InvalidSort(
            f"Unknown sort field {sort_key}",
            details={"sort": sort_key, "allowed": sorted(sort_columns)},
        )
    descending = params.order == "desc"

    if params.cursor:
        sort_value, id_value = decode_cursor(params.cursor, sort=sort_key, order=params.order, count=2)
        if descending:
            stmt = stmt.where(
                or_(
                    column < sort_value,
                    and_(column == sort_value, id_column < id_value),
                )
            )
        else:
            stmt = stmt.where(
                or_(
                    column > sort_value,
                    and_(column == sort_value, id_column > id_value),
                )
            )

    ordering = desc(column) if descending else asc(column)
    tie = desc(id_column) if descending else asc(id_column)
    stmt = stmt.order_by(ordering, tie).limit(params.limit + 1)

    rows = list((await session.execute(stmt)).scalars().all())
    has_more = len(rows) > params.limit
    rows = rows[: params.limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor(
            [getattr(last, column.key), getattr(last, id_column.key)],
            sort=sort_key,
            order=params.order,
        )
    return rows, next_cursor


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "FilterSpec",
    "Page",
    "PageParams",
    "SortOrder",
    "apply_filters",
    "contains",
    "decode_cursor",
    "encode_cursor",
    "page_params",
    "paginate",
]
