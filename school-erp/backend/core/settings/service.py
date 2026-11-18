"""Layered settings resolution and mutation (ARCH §5.10).

Priority: ``code`` (schema defaults) < ``central`` (controller) < ``instance``
(school). Only values a module declared in its ``settings_schema`` can be stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.principal import Principal
from core.db.soft_delete import actor_uuid
from core.settings.core_schema import CoreSettings
from core.settings.models import CENTRAL, INSTANCE, Setting
from core.settings.schema import (
    SettingField,
    field_specs,
    flatten_values,
    require_field,
    unflatten,
    validate_value,
)

CORE = "core"


@dataclass(frozen=True)
class Effective:
    spec: SettingField
    value: Any
    source: str


async def _rows(session: AsyncSession, module: str, *, include_deleted: bool = False) -> list[Setting]:
    stmt = select(Setting).where(Setting.module == module)
    if include_deleted:
        stmt = stmt.execution_options(include_deleted=True)
    return list((await session.execute(stmt)).scalars().all())


def _resolve(specs: list[SettingField], rows: list[Setting]) -> dict[str, Effective]:
    defaults = {spec.key: spec.default for spec in specs}
    by_layer = {(row.layer, row.key): row for row in rows}
    result: dict[str, Effective] = {}
    for spec in specs:
        value = defaults[spec.key]
        source = "code"
        central = by_layer.get((CENTRAL, spec.key))
        instance = by_layer.get((INSTANCE, spec.key))
        if central is not None:
            value, source = central.value, CENTRAL
        if instance is not None:
            value, source = instance.value, INSTANCE
        result[spec.key] = Effective(spec=spec, value=value, source=source)
    return result


async def effective_map(session: AsyncSession, module: str, model: type) -> dict[str, Effective]:
    specs = field_specs(module, model)
    return _resolve(specs, await _rows(session, module))


async def module_settings(session: AsyncSession, module: str, model: type) -> dict[str, Any]:
    effective = await effective_map(session, module, model)
    return {
        "module": module,
        "label_key": f"settings.module.{module}",
        "fields": [
            {**item.spec.as_dict(), "value": item.value, "source": item.source} for item in effective.values()
        ],
    }


async def load_model(session: AsyncSession, module: str, model: type[BaseModel]) -> Any:
    """Return the effective values as a validated instance of ``model``."""
    effective = await effective_map(session, module, model)
    return model.model_validate(unflatten({key: item.value for key, item in effective.items()}))


async def all_settings(session: AsyncSession, registry: Any) -> list[dict[str, Any]]:
    items = [await module_settings(session, CORE, CoreSettings)]
    for manifest in sorted(registry.all(), key=lambda item: item.key):
        if manifest.settings_schema is not None:
            items.append(await module_settings(session, manifest.key, manifest.settings_schema))
    return items


def module_model(registry: Any, module: str) -> type | None:
    if module == CORE:
        return CoreSettings
    manifest = registry.get(module)
    return manifest.settings_schema if manifest else None


async def _find(session: AsyncSession, module: str, key: str, layer: str) -> Setting | None:
    return (
        (
            await session.execute(
                select(Setting)
                .where(Setting.module == module, Setting.key == key, Setting.layer == layer)
                .execution_options(include_deleted=True)
            )
        )
        .scalars()
        .first()
    )


async def set_setting(
    session: AsyncSession,
    module: str,
    model: type,
    key: str,
    value: Any,
    *,
    layer: str = INSTANCE,
    actor: Principal | None = None,
) -> Effective:
    """Validate and store one value at a layer. Caller commits and audits."""
    if layer not in (CENTRAL, INSTANCE):
        raise ValueError(f"Unknown settings layer {layer}")
    require_field(module, model, key)
    current = {name: item.value for name, item in (await effective_map(session, module, model)).items()}
    validated = validate_value(model, key, value, current)
    row = await _find(session, module, key, layer)
    actor_id = actor_uuid(actor)
    if row is None:
        row = Setting(
            layer=layer,
            module=module,
            key=key,
            value=validated,
            created_by=actor_id,
            updated_by=actor_id,
        )
        session.add(row)
    else:
        row.value = validated
        row.deleted_at = None
        row.deleted_by = None
        row.updated_by = actor_id
        row.row_version = (row.row_version or 0) + 1
    await session.flush()
    effective = await effective_map(session, module, model)
    return effective[key]


async def clear_setting(
    session: AsyncSession,
    module: str,
    model: type,
    key: str,
    *,
    layer: str = INSTANCE,
    actor: Principal | None = None,
) -> bool:
    """Remove one override (soft delete). Returns False when nothing was set."""
    require_field(module, model, key)
    row = await _find(session, module, key, layer)
    if row is None or row.deleted_at is not None:
        return False
    row.deleted_at = datetime.now(UTC)
    row.deleted_by = actor_uuid(actor)
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    return True


def code_values(model: type) -> dict[str, Any]:
    return flatten_values(model)


__all__ = [
    "CORE",
    "Effective",
    "all_settings",
    "clear_setting",
    "code_values",
    "effective_map",
    "load_model",
    "module_model",
    "module_settings",
    "set_setting",
]
