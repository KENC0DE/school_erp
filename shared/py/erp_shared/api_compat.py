"""OpenAPI compatibility checking for the additive-only `/api/v1` policy (P1-26).

The school API is versioned in the URL, and within a major version changes are
additive: an old mobile build must keep working against a newer server. This
module compares a generated OpenAPI document against the snapshot of the last
release and reports changes that would break an existing client.

It is pure and dependency-free so the CI script and the test suite share exactly
the same rules. Removals are allowed only for items that were already marked
``deprecated: true`` in the last *two* release snapshots, which is how the
"deprecations stay for at least two releases" policy is enforced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
V1_PREFIX = "/api/v1"
_REQUEST = "request"
_RESPONSE = "response"
_NEUTRAL = "neutral"


@dataclass(frozen=True)
class BreakingChange:
    """One incompatible change, in reviewable terms."""

    kind: str
    location: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind} at {self.location}: {self.detail}"


def is_v1_path(path: str) -> bool:
    return path == V1_PREFIX or path.startswith(f"{V1_PREFIX}/")


def _operations(path_item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        method: value
        for method, value in path_item.items()
        if method in HTTP_METHODS and isinstance(value, dict)
    }


def _resolve(document: dict[str, Any], schema: Any) -> dict[str, Any]:
    """Follow local ``$ref`` pointers, merging JSON-Schema-style siblings."""
    if not isinstance(schema, dict):
        return {}
    siblings = {key: value for key, value in schema.items() if key != "$ref"}
    reference = schema.get("$ref")
    if not isinstance(reference, str) or not reference.startswith("#/"):
        return schema
    node: Any = document
    for part in reference[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            return siblings
        node = node[part]
    if not isinstance(node, dict):
        return siblings
    return {**node, **siblings}


def _flatten(document: dict[str, Any], schema: Any) -> dict[str, Any]:
    """Resolve ``$ref`` and merge ``allOf`` so type checks see one object."""
    resolved = _resolve(document, schema)
    parts = resolved.get("allOf")
    if not isinstance(parts, list):
        return resolved
    merged: dict[str, Any] = {key: value for key, value in resolved.items() if key != "allOf"}
    for part in parts:
        flat = _flatten(document, part)
        properties = {**flat.get("properties", {}), **merged.get("properties", {})}
        if properties:
            merged["properties"] = properties
        required = list(dict.fromkeys([*flat.get("required", []), *merged.get("required", [])]))
        if required:
            merged["required"] = required
        for key in ("type", "items", "enum", "anyOf", "oneOf"):
            if key not in merged and key in flat:
                merged[key] = flat[key]
    return merged


def _deprecated(document: dict[str, Any], schema: Any) -> bool:
    if not isinstance(schema, dict):
        return False
    resolved = _resolve(document, schema)
    return bool(resolved.get("deprecated") or schema.get("deprecated"))


def _type(schema: dict[str, Any]) -> str | None:
    value = schema.get("type")
    if isinstance(value, str):
        return value
    for union in ("anyOf", "oneOf"):
        variants = schema.get(union)
        if isinstance(variants, list):
            return f"{union}:{len(variants)}"
    if schema.get("properties") or schema.get("additionalProperties") is not None:
        return "object"
    return None


def _canonical(schema: dict[str, Any]) -> str:
    """A small, stable signature used to match union variants by shape."""
    return repr(
        (
            schema.get("type"),
            sorted(schema.get("enum") or []),
            tuple(sorted(schema.get("properties", {}))),
            schema.get("format"),
        )
    )


class Comparator:
    def __init__(
        self,
        current: dict[str, Any],
        baseline: dict[str, Any],
        previous: dict[str, Any] | None = None,
    ) -> None:
        self.current = current
        self.baseline = baseline
        self.previous = previous
        self.changes: list[BreakingChange] = []

    # -- removal policy ---------------------------------------------------
    def _removal_allowed(self, baseline_node: Any, previous_node: Any) -> bool:
        """Only a deprecation present in the last two releases may disappear."""
        if previous_node is None or not self.previous:
            return False
        return _deprecated(self.baseline, baseline_node) and _deprecated(self.previous, previous_node)

    # -- public API -------------------------------------------------------
    def compare(self) -> list[BreakingChange]:
        base_paths = {path: item for path, item in self.baseline.get("paths", {}).items() if is_v1_path(path)}
        cur_paths = {path: item for path, item in self.current.get("paths", {}).items() if is_v1_path(path)}
        prev_paths = (self.previous or {}).get("paths", {})

        for path in sorted(base_paths):
            if path not in cur_paths:
                for method, base_op in _operations(base_paths[path]).items():
                    previous_op = _operations(prev_paths.get(path, {})).get(method)
                    if self._removal_allowed(base_op, previous_op):
                        continue
                    self._add(
                        "endpoint_removed",
                        f"{method.upper()} {path}",
                        "the endpoint disappeared from /api/v1",
                    )
                continue

            for method, base_op in _operations(base_paths[path]).items():
                cur_op = cur_paths[path].get(method)
                location = f"{method.upper()} {path}"
                if not isinstance(cur_op, dict):
                    previous_op = _operations(prev_paths.get(path, {})).get(method)
                    if self._removal_allowed(base_op, previous_op):
                        continue
                    self._add(
                        "endpoint_removed",
                        location,
                        "the endpoint disappeared from /api/v1",
                    )
                    continue
                previous_op = _operations(prev_paths.get(path, {})).get(method)
                self._compare_operation(
                    location,
                    base_paths[path],
                    base_op,
                    cur_paths[path],
                    cur_op,
                    previous_op,
                )
        return self.changes

    # -- helpers ----------------------------------------------------------
    def _add(self, kind: str, location: str, detail: str) -> None:
        self.changes.append(BreakingChange(kind, location, detail))

    def _compare_operation(
        self,
        location: str,
        base_path_item: dict[str, Any],
        base_op: dict[str, Any],
        cur_path_item: dict[str, Any],
        cur_op: dict[str, Any],
        previous_op: dict[str, Any] | None,
    ) -> None:
        base_params = self._parameters(base_path_item, base_op)
        cur_params = self._parameters(cur_path_item, cur_op)
        prev_params = self._parameters({}, previous_op or {})

        for key, base_param in base_params.items():
            label = f"{location} parameter {key[1]}:{key[0]}"
            cur_param = cur_params.get(key)
            if cur_param is None:
                self._add(
                    "parameter_removed",
                    label,
                    "existing clients still send or rely on this parameter",
                )
                continue
            if cur_param.get("required") and not base_param.get("required"):
                self._add(
                    "parameter_now_required",
                    label,
                    "a previously optional parameter became required",
                )
            self._compare_schema(
                base_param.get("schema"),
                cur_param.get("schema"),
                label,
                previous_op and prev_params.get(key, {}).get("schema"),
                _REQUEST,
            )
        for key, cur_param in cur_params.items():
            if key not in base_params and cur_param.get("required"):
                self._add(
                    "required_parameter_added",
                    f"{location} parameter {key[1]}:{key[0]}",
                    "a new required parameter breaks existing clients",
                )

        self._compare_request_body(location, base_op, cur_op, previous_op)
        self._compare_responses(location, base_op, cur_op, previous_op)

    @staticmethod
    def _parameters(
        path_item: dict[str, Any], operation: dict[str, Any]
    ) -> dict[tuple[str, str], dict[str, Any]]:
        combined = [*path_item.get("parameters", []), *operation.get("parameters", [])]
        return {
            (str(item.get("name")), str(item.get("in"))): item for item in combined if isinstance(item, dict)
        }

    def _compare_request_body(
        self,
        location: str,
        base_op: dict[str, Any],
        cur_op: dict[str, Any],
        previous_op: dict[str, Any] | None,
    ) -> None:
        base_body = base_op.get("requestBody")
        cur_body = cur_op.get("requestBody")
        prev_body = (previous_op or {}).get("requestBody")
        if base_body and not cur_body:
            self._add(
                "request_body_removed",
                f"{location} request body",
                "the request body disappeared",
            )
            return
        if not base_body and cur_body:
            if cur_body.get("required"):
                self._add(
                    "required_request_body_added",
                    f"{location} request body",
                    "a new required body breaks clients that send none",
                )
            return
        if not base_body or not cur_body:
            return
        if cur_body.get("required") and not base_body.get("required"):
            self._add(
                "request_body_now_required",
                f"{location} request body",
                "a previously optional body became required",
            )
        self._compare_content(
            base_body.get("content", {}),
            cur_body.get("content", {}),
            (prev_body or {}).get("content", {}),
            f"{location} request body",
            _REQUEST,
        )

    def _compare_responses(
        self,
        location: str,
        base_op: dict[str, Any],
        cur_op: dict[str, Any],
        previous_op: dict[str, Any] | None,
    ) -> None:
        base_responses = base_op.get("responses", {})
        cur_responses = cur_op.get("responses", {})
        prev_responses = (previous_op or {}).get("responses", {})
        for status, base_response in base_responses.items():
            cur_response = cur_responses.get(status)
            if cur_response is None:
                self._add(
                    "response_removed",
                    f"{location} response {status}",
                    "clients may branch on this status code",
                )
                continue
            self._compare_content(
                base_response.get("content", {}),
                cur_response.get("content", {}),
                prev_responses.get(status, {}).get("content", {}),
                f"{location} response {status}",
                _RESPONSE,
            )

    def _compare_content(
        self,
        base_content: dict[str, Any],
        cur_content: dict[str, Any],
        prev_content: dict[str, Any],
        location: str,
        direction: str,
    ) -> None:
        for media_type, base_media in base_content.items():
            cur_media = cur_content.get(media_type)
            if cur_media is None:
                self._add(
                    "media_type_removed",
                    f"{location} {media_type}",
                    "clients request or parse this media type",
                )
                continue
            self._compare_schema(
                base_media.get("schema"),
                cur_media.get("schema"),
                f"{location} {media_type}",
                (prev_content.get(media_type) or {}).get("schema"),
                direction,
            )

    def _compare_schema(
        self,
        base_schema: Any,
        cur_schema: Any,
        location: str,
        previous_schema: Any = None,
        direction: str = _NEUTRAL,
    ) -> None:
        base = _flatten(self.baseline, base_schema)
        cur = _flatten(self.current, cur_schema)
        if not base:
            return
        prev: dict[str, Any] = (
            _flatten(self.previous, previous_schema) if self.previous and previous_schema is not None else {}
        )

        base_type = _type(base)
        cur_type = _type(cur)
        if base_type and cur_type and base_type != cur_type:
            self._add(
                "type_changed",
                location,
                f"{base_type} became {cur_type}",
            )
            return
        if base_type and not cur_type and (base.get("properties") or base_type != "object"):
            self._add(
                "type_removed",
                location,
                f"the {base_type} contract was dropped",
            )
            return

        if base_type == "array":
            self._compare_schema(
                base.get("items"),
                cur.get("items"),
                f"{location}[]",
                prev.get("items") if prev else None,
                direction,
            )

        base_enum = base.get("enum")
        if isinstance(base_enum, list):
            cur_enum = cur.get("enum") if isinstance(cur.get("enum"), list) else []
            missing = [value for value in base_enum if value not in cur_enum]
            if missing:
                self._add(
                    "enum_value_removed",
                    location,
                    f"enum values {missing} are no longer accepted",
                )

        for union in ("anyOf", "oneOf"):
            base_variants = base.get(union)
            cur_variants = cur.get(union)
            if isinstance(base_variants, list) and cur_variants is not None:
                if not isinstance(cur_variants, list):
                    self._add("type_changed", location, f"{union} was replaced")
                    continue
                cur_signatures = {_canonical(_flatten(self.current, item)) for item in cur_variants}
                for variant in base_variants:
                    flat = _flatten(self.baseline, variant)
                    if _canonical(flat) not in cur_signatures:
                        self._add(
                            "union_variant_removed",
                            location,
                            f"one {union} variant is no longer accepted",
                        )
                        break

        if direction == _REQUEST:
            self._compare_constraints(base, cur, location)

        base_properties = base.get("properties")
        cur_properties = cur.get("properties")
        if isinstance(base_properties, dict) and base_properties:
            if not isinstance(cur_properties, dict) or not cur_properties:
                if not (cur_type == "object" and cur.get("additionalProperties") is not False):
                    self._add(
                        "object_contract_removed",
                        location,
                        "the described fields were replaced by an unconstrained object",
                    )
                return
            base_required = set(base.get("required", []))
            cur_required = set(cur.get("required", []))
            prev_properties = prev.get("properties", {}) if isinstance(prev, dict) else {}
            for name, base_property in base_properties.items():
                field_location = f"{location}.{name}"
                cur_property = cur_properties.get(name)
                if cur_property is None:
                    if self._removal_allowed(base_property, prev_properties.get(name)):
                        continue
                    self._add(
                        "field_removed",
                        field_location,
                        "the field is part of the released contract",
                    )
                    continue
                self._compare_schema(
                    base_property,
                    cur_property,
                    field_location,
                    prev_properties.get(name),
                    direction,
                )
            for name in sorted(cur_required - base_required):
                if name in base_properties and name in cur_properties:
                    self._add(
                        "field_now_required",
                        f"{location}.{name}",
                        "a previously optional field became required",
                    )
                elif name in cur_properties:
                    self._add(
                        "required_field_added",
                        f"{location}.{name}",
                        "a new required field breaks existing requests",
                    )

    def _compare_constraints(self, base: dict[str, Any], cur: dict[str, Any], location: str) -> None:
        """A request that accepted a value yesterday must still accept it."""
        pairs = (
            ("minimum", lambda old, new: new > old, "minimum was raised"),
            ("maximum", lambda old, new: new < old, "maximum was lowered"),
            ("minLength", lambda old, new: new > old, "minLength was raised"),
            ("maxLength", lambda old, new: new < old, "maxLength was lowered"),
        )
        for key, narrows, detail in pairs:
            old = base.get(key)
            new = cur.get(key)
            if isinstance(old, (int, float)) and isinstance(new, (int, float)) and narrows(old, new):
                self._add("constraint_narrowed", location, f"{detail} ({old} → {new})")


def compare_schemas(
    current: dict[str, Any],
    baseline: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> list[BreakingChange]:
    """Compare the generated document with the last released snapshot."""
    return Comparator(current, baseline, previous).compare()


__all__ = ["BreakingChange", "Comparator", "compare_schemas", "is_v1_path"]
