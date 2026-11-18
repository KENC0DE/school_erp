"""Schema introspection and validation for layered settings.

A module declares a Pydantic model as ``settings_schema``. This module flattens
it to dotted keys, derives the form metadata the web UI renders and validates a
single changed value against the whole model.
"""

from __future__ import annotations

import types
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from app.errors import NotFound, ValidationFailed
from pydantic import BaseModel, SecretStr, ValidationError


@dataclass(frozen=True)
class SettingField:
    module: str
    key: str
    type: str
    default: Any
    label_key: str
    enum: list[str] | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    max_length: int | None = None
    secret: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _unwrap_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _flatten_dict(values: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for name, value in values.items():
        key = f"{prefix}{name}"
        if isinstance(value, dict):
            flat.update(_flatten_dict(value, f"{key}."))
        else:
            flat[key] = value
    return flat


def flatten_values(model: type[BaseModel]) -> dict[str, Any]:
    """Code-layer defaults, flattened to ``group.field`` keys."""
    return _flatten_dict(model().model_dump(mode="json"))


def _constraints(info: Any) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for meta in getattr(info, "metadata", []):
        for attr in ("ge", "gt", "le", "lt", "max_length", "min_length"):
            value = getattr(meta, attr, None)
            if value is not None:
                found[attr] = value
    if found.get("gt") is not None:
        found["minimum"] = found["gt"]
    if found.get("ge") is not None:
        found["minimum"] = found["ge"]
    if found.get("lt") is not None:
        found["maximum"] = found["lt"]
    if found.get("le") is not None:
        found["maximum"] = found["le"]
    return found


def _json_type(annotation: Any, info: Any) -> tuple[str, list[str] | None]:
    annotation = _unwrap_optional(annotation)
    if annotation is SecretStr:
        return "secret", None
    origin = get_origin(annotation)
    if origin is Literal:
        return "enum", [str(value) for value in get_args(annotation)]
    if origin is Annotated:
        base, *rest = get_args(annotation)
        return _json_type(base, info)
    if origin in (list, tuple, set):
        return "list", None
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return "enum", [str(member.value) for member in annotation]
    if annotation is bool:
        return "boolean", None
    if annotation in (int, float):
        return "number", None
    return "string", None


def field_specs(
    module: str,
    model: type[BaseModel],
    prefix: str = "",
    *,
    defaults: dict[str, Any] | None = None,
) -> list[SettingField]:
    """Flatten one settings model into the fields the UI renders.

    ``defaults`` is computed once from the outermost model so nested groups keep
    their full dotted keys (``school_profile.name``).
    """
    if defaults is None:
        defaults = flatten_values(model)
    specs: list[SettingField] = []
    for name, info in model.model_fields.items():
        key = f"{prefix}{name}"
        annotation = info.annotation
        base = _unwrap_optional(annotation)
        if isinstance(base, type) and issubclass(base, BaseModel):
            specs.extend(field_specs(module, base, f"{key}.", defaults=defaults))
            continue
        kind, enum = _json_type(annotation, info)
        extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else {}
        secret = kind == "secret" or bool(extra.get("secret"))
        constraints = _constraints(info)
        specs.append(
            SettingField(
                module=module,
                key=key,
                type="secret" if secret else kind,
                default="" if secret else defaults.get(key),
                label_key=str(extra.get("label_key") or f"settings.{module}.{key}"),
                enum=enum,
                minimum=constraints.get("minimum"),
                maximum=constraints.get("maximum"),
                max_length=constraints.get("max_length"),
                secret=secret,
            )
        )
    return specs


def unflatten(values: dict[str, Any]) -> dict[str, Any]:
    nested: dict[str, Any] = {}
    for key, value in values.items():
        cursor = nested
        parts = key.split(".")
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return nested


def validate_value(
    model: type[BaseModel],
    key: str,
    value: Any,
    current: dict[str, Any],
) -> Any:
    """Validate the candidate against the whole typed model and return it in JSON form."""
    merged = {**current, key: value}
    try:
        validated = model.model_validate(unflatten(merged))
    except ValidationError as exc:
        details = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors(include_url=False)
        ]
        raise ValidationFailed(
            "The setting value is invalid",
            message_key="error.invalid_setting",
            details={"key": key, "errors": details},
        ) from exc
    return _flatten_dict(validated.model_dump(mode="json"))[key]


def field_map(module: str, model: type[BaseModel]) -> dict[str, SettingField]:
    return {spec.key: spec for spec in field_specs(module, model)}


def require_field(module: str, model: type[BaseModel], key: str) -> SettingField:
    field = field_map(module, model).get(key)
    if field is None:
        raise NotFound(
            f"Unknown setting {module}.{key}",
            message_key="error.unknown_setting",
            details={"module": module, "key": key},
        )
    return field
