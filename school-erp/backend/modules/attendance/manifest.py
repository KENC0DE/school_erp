from __future__ import annotations

from core.modules.manifest import ModuleManifest, Nav, Perm

from modules.attendance import actions as _actions  # noqa: F401 - registers actions
from modules.attendance import models as _models  # noqa: F401 - registers models
from modules.attendance.router import router
from modules.attendance.settings import AttendanceSettings

MANIFEST = ModuleManifest(
    key="attendance",
    name="Attendance",
    version="0.1.0",
    description="Daily or per-period attendance registers, fast entry, statuses and offline-safe records.",
    depends_on=["academics", "students", "staff"],
    permissions=[
        Perm(
            "attendance.view",
            "attendance.perm.view",
            scopes=("all", "assigned_subjects", "own_class"),
        ),
        Perm(
            "attendance.record",
            "attendance.perm.record",
            scopes=("all", "assigned_subjects", "own_class"),
        ),
        Perm("attendance.manage", "attendance.perm.manage"),
    ],
    nav=[
        Nav(
            key="attendance",
            label_key="attendance.nav",
            path="/attendance",
            perm="attendance.view",
            icon="calendar-check",
            order=25,
        )
    ],
    router=router,
    actions=[*_actions.__all__],
    i18n_namespaces=["attendance"],
    settings_schema=AttendanceSettings,
    licensable=True,
    default_enabled=True,
    core=False,
)

__all__ = ["MANIFEST"]
