"""Loader entry point. Importing this package registers all module models."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from core.modules.registry import ModuleRegistry


def load_registry() -> "ModuleRegistry":
    # Imported lazily: the registry scans this package, so a module-level import
    # here would be circular.
    from core.modules.registry import ModuleRegistry

    return ModuleRegistry.load()


__all__ = ["load_registry"]
