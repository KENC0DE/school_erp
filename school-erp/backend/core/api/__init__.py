"""Transport-level API conventions shared by every module (ARCH §5.1)."""

from core.api.concurrency import (
    apply_row_version,
    ensure_row_version,
    parse_if_match,
    version_from_payload,
)
from core.api.idempotency import IdempotencyMiddleware, IdempotencyRecord
from core.api.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    FilterSpec,
    Page,
    PageParams,
    apply_filters,
    contains,
    decode_cursor,
    encode_cursor,
    page_params,
    paginate,
)

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "FilterSpec",
    "IdempotencyMiddleware",
    "IdempotencyRecord",
    "Page",
    "PageParams",
    "apply_filters",
    "apply_row_version",
    "contains",
    "decode_cursor",
    "encode_cursor",
    "ensure_row_version",
    "page_params",
    "paginate",
    "parse_if_match",
    "version_from_payload",
]
