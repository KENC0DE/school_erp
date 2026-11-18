from __future__ import annotations

from core.modules.manifest import ModuleManifest, Nav, Perm

from modules.students import actions as _actions  # noqa: F401 - registers actions
from modules.students import models as _models  # noqa: F401 - registers models
from modules.students.router import router

MANIFEST = ModuleManifest(
    key="students",
    name="Students",
    version="0.1.0",
    description="Student records, enrollment, guardians, medical data and documents.",
    depends_on=["academics"],
    permissions=[
        Perm("students.view", "students.perm.view"),
        Perm("students.manage", "students.perm.manage"),
        Perm("students.medical.view", "students.perm.medical_view"),
        Perm("students.medical.manage", "students.perm.medical_manage"),
    ],
    nav=[
        Nav(
            key="students",
            label_key="students.nav",
            path="/students",
            perm="students.view",
            icon="users",
            order=20,
        )
    ],
    router=router,
    actions=[*_actions.__all__],
    i18n_namespaces=["students"],
    licensable=True,
    default_enabled=True,
    core=False,
)

__all__ = ["MANIFEST"]
