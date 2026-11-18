from __future__ import annotations

from core.modules.manifest import ModuleManifest, Nav, Perm

from modules.admissions import actions as _actions  # noqa: F401 - registers actions
from modules.admissions import models as _models  # noqa: F401 - registers models
from modules.admissions.router import router
from modules.admissions.settings import AdmissionSettings

MANIFEST = ModuleManifest(
    key="admissions",
    name="Admissions",
    version="0.2.0",
    description=(
        "Application intake, optional entrance test, decisions, auto-assignment "
        "and conversion of applicants into students."
    ),
    depends_on=["academics", "students"],
    permissions=[
        Perm("admissions.view", "admissions.perm.view"),
        Perm("admissions.manage", "admissions.perm.manage"),
        Perm("admissions.decide", "admissions.perm.decide"),
    ],
    nav=[
        Nav(
            key="admissions",
            label_key="admissions.nav",
            path="/admissions",
            perm="admissions.view",
            icon="clipboard-list",
            order=19,
        )
    ],
    router=router,
    actions=[*_actions.__all__],
    events=[
        "admission.application_created",
        "admission.decision",
        "admission.converted",
    ],
    i18n_namespaces=["admissions"],
    settings_schema=AdmissionSettings,
    licensable=True,
    default_enabled=True,
    core=False,
)

__all__ = ["MANIFEST"]
