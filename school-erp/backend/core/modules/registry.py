from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass

import modules as modules_pkg
from core.modules.manifest import ModuleManifest, validate_manifests


@dataclass
class ModuleRegistry:
    manifests: dict[str, ModuleManifest]

    @classmethod
    def load(cls) -> ModuleRegistry:
        found: dict[str, ModuleManifest] = {}
        for info in pkgutil.iter_modules(modules_pkg.__path__):
            if not info.ispkg:
                continue
            try:
                module = importlib.import_module(f"modules.{info.name}.manifest")
            except ModuleNotFoundError as exc:
                if exc.name == f"modules.{info.name}.manifest":
                    continue
                raise
            manifest = getattr(module, "MANIFEST", None)
            if manifest is None:
                continue
            if not isinstance(manifest, ModuleManifest):
                raise TypeError(f"modules/{info.name}/manifest.py must export MANIFEST")
            if manifest.key in found:
                raise ValueError(f"Duplicate module key '{manifest.key}'")
            found[manifest.key] = manifest
        validate_manifests(found)
        return cls(manifests=found)

    def get(self, key: str) -> ModuleManifest | None:
        return self.manifests.get(key)

    def all(self) -> list[ModuleManifest]:
        return sorted(self.manifests.values(), key=lambda m: m.key)

    def permissions(self) -> list[dict]:
        from core.modules.manifest import permission_declarations

        return permission_declarations(self.manifests)
