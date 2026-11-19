from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class Perm:
    code: str
    label_key: str = ""
    scopes: tuple[str, ...] = ("all",)
    description: str = ""


@dataclass(frozen=True)
class Nav:
    key: str
    label_key: str
    path: str
    perm: str | None = None
    icon: str | None = None
    order: int = 100


@dataclass
class ModuleManifest:
    key: str
    name: str
    version: str = "0.1.0"
    depends_on: list[str] = field(default_factory=list)
    permissions: list[Perm] = field(default_factory=list)
    nav: list[Nav] = field(default_factory=list)
    router: APIRouter | None = None
    actions: list[Any] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    i18n_namespaces: list[str] = field(default_factory=list)
    document_fields: list[Any] = field(default_factory=list)
    settings_schema: type | None = None
    # Modules may ship starter data (grade levels, templates, ...). The hook is
    # idempotent and runs on startup after the module rows exist.
    bootstrap: Callable[[AsyncSession], Awaitable[None]] | None = None
    licensable: bool = True
    default_enabled: bool = False
    core: bool = False
    description: str = ""


class ManifestError(ValueError):
    pass


def validate_manifests(manifests: dict[str, ModuleManifest]) -> None:
    keys = set(manifests)
    if len(keys) != len(manifests):
        raise ManifestError("Duplicate module keys")

    for manifest in manifests.values():
        for dep in manifest.depends_on:
            if dep not in keys:
                raise ManifestError(f"Module '{manifest.key}' depends on unknown module '{dep}'")
            if dep == manifest.key:
                raise ManifestError(f"Module '{manifest.key}' depends on itself")

    # Cycle detection with an explicit DFS stack.
    state: dict[str, int] = {key: 0 for key in keys}

    def visit(key: str, stack: list[str]) -> None:
        if state[key] == 1:
            cycle = " -> ".join([*stack, key])
            raise ManifestError(f"Cyclic module dependency: {cycle}")
        if state[key] == 2:
            return
        state[key] = 1
        for dep in manifests[key].depends_on:
            visit(dep, [*stack, key])
        state[key] = 2

    for key in keys:
        visit(key, [])


def permission_declarations(manifests: dict[str, ModuleManifest]) -> list[dict[str, Any]]:
    from core.rbac.permissions import CORE_PERMISSIONS

    declared: list[dict[str, Any]] = [
        {
            "code": perm.code,
            "module": "core",
            "scopes": list(perm.scopes),
            "label_key": perm.label_key or f"core.perm.{perm.code}",
        }
        for perm in CORE_PERMISSIONS
    ]
    for manifest in manifests.values():
        for perm in manifest.permissions:
            declared.append(
                {
                    "code": perm.code,
                    "module": manifest.key,
                    "scopes": list(perm.scopes),
                    "label_key": perm.label_key or f"{manifest.key}.perm.{perm.code}",
                }
            )
    return declared


def router_declares_permission(router: APIRouter) -> Callable[[], bool]:
    """Used by tests to inspect mounted routes."""

    def check() -> bool:
        return any(getattr(route, "dependant", None) for route in router.routes)

    return check
