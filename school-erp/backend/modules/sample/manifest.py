from __future__ import annotations

from core.modules.manifest import ModuleManifest, Nav, Perm

from modules.sample import actions as _actions  # noqa: F401 - registers actions
from modules.sample import models as _models  # noqa: F401 - registers models
from modules.sample.router import router

MANIFEST = ModuleManifest(
    key="sample",
    name="Sample module",
    version="0.1.0",
    description="Throwaway walking-skeleton module.",
    permissions=[
        Perm("sample.notes.view", "sample.perm.view"),
        Perm("sample.notes.create", "sample.perm.create"),
    ],
    nav=[
        Nav(
            key="sample",
            label_key="sample.nav",
            path="/sample",
            perm="sample.notes.view",
            icon="beaker",
            order=50,
        )
    ],
    router=router,
    actions=_actions.__all__ if hasattr(_actions, "__all__") else [],
    i18n_namespaces=["sample"],
    licensable=True,
    default_enabled=True,
    core=False,
)
