from __future__ import annotations

from core.modules.manifest import ModuleManifest, Nav, Perm

from modules.staff import actions as _actions  # noqa: F401 - registers actions
from modules.staff import models as _models  # noqa: F401 - registers models
from modules.staff.router import router

MANIFEST = ModuleManifest(
    key="staff",
    name="Staff",
    version="0.1.0",
    description="Staff profiles on persons, departments, positions, contracts, qualifications, documents and user-account links.",
    permissions=[
        Perm("staff.view", "staff.perm.view", scopes=("all", "department")),
        Perm("staff.manage", "staff.perm.manage"),
        Perm("staff.contracts.view", "staff.perm.contracts_view"),
        Perm("staff.contracts.manage", "staff.perm.contracts_manage"),
    ],
    nav=[
        Nav(
            key="staff",
            label_key="staff.nav",
            path="/staff",
            perm="staff.view",
            icon="briefcase",
            order=30,
        )
    ],
    router=router,
    actions=[*_actions.__all__],
    i18n_namespaces=["staff"],
    licensable=True,
    default_enabled=True,
    core=False,
)

__all__ = ["MANIFEST"]
