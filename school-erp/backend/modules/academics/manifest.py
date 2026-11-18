from __future__ import annotations

from core.modules.manifest import ModuleManifest, Nav, Perm

from modules.academics import actions as _actions  # noqa: F401 - registers actions
from modules.academics import models as _models  # noqa: F401 - registers models
from modules.academics.defaults import ensure_default_academics
from modules.academics.router import router

MANIFEST = ModuleManifest(
    key="academics",
    name="Academic structure",
    version="0.1.0",
    description="Grade levels, stages and the school's academic scope.",
    permissions=[
        Perm("academics.view", "academics.perm.view"),
        Perm("academics.manage", "academics.perm.manage"),
    ],
    nav=[
        Nav(
            key="academics",
            label_key="academics.nav",
            path="/academics",
            perm="academics.view",
            icon="graduation-cap",
            order=10,
        )
    ],
    router=router,
    actions=_actions.__all__,
    i18n_namespaces=["academics"],
    bootstrap=ensure_default_academics,
    licensable=True,
    default_enabled=True,
    core=False,
)
