"""Canonical hashing shared by the instance and the controller vault."""

from __future__ import annotations

import hashlib
import json
from typing import Any

HASH_FIELDS = (
    "seq",
    "ts",
    "actor_type",
    "actor_id",
    "on_behalf_of",
    "via",
    "ip",
    "user_agent",
    "module",
    "entity_type",
    "entity_id",
    "action",
    "before",
    "after",
    "reason",
    "request_id",
    "reverts_id",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def entry_payload(entry: dict[str, Any]) -> dict[str, Any]:
    return {field: entry.get(field) for field in HASH_FIELDS}


def compute_hash(prev_hash: str | None, entry: dict[str, Any]) -> str:
    body = canonical_json(entry_payload(entry))
    material = f"{prev_hash or ''}:{body}".encode()
    return hashlib.sha256(material).hexdigest()
