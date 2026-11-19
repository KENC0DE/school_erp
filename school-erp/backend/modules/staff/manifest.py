from __future__ import annotations

from core.modules.manifest import ModuleManifest, Nav, Perm

from modules.staff import actions as _actions  # noqa: F401 - registers actions
from modules.staff import attendance_actions as _attendance_actions  # noqa: F401
from modules.staff import leave_actions as _leave_actions  # noqa: F401 - registers actions
from modules.staff import models as _models  # noqa: F401 - registers models
from modules.staff.fields import FIELDS as DOCUMENT_FIELDS
from modules.staff.router import router

MANIFEST = ModuleManifest(
    key="staff",
    name="Staff",
    version="0.1.0",
    description="Staff profiles on persons, departments, positions, contracts, qualifications, documents, teaching assignments and leave.",
    permissions=[
        Perm("staff.view", "staff.perm.view", scopes=("all", "department")),
        Perm("staff.manage", "staff.perm.manage"),
        Perm("staff.contracts.view", "staff.perm.contracts_view"),
        Perm("staff.contracts.manage", "staff.perm.contracts_manage"),
        Perm("staff.leave.view", "staff.perm.leave_view", scopes=("all", "department", "self")),
        Perm("staff.leave.request", "staff.perm.leave_request", scopes=("all", "self")),
        Perm("staff.leave.approve", "staff.perm.leave_approve", scopes=("all", "department")),
        Perm("staff.leave.manage", "staff.perm.leave_manage"),
        Perm(
            "staff.attendance.view",
            "staff.perm.attendance_view",
            scopes=("all", "department", "self"),
        ),
        Perm(
            "staff.attendance.record",
            "staff.perm.attendance_record",
            scopes=("all", "department"),
        ),
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
    actions=[*_actions.__all__, *_leave_actions.__all__, *_attendance_actions.__all__],
    i18n_namespaces=["staff"],
    document_fields=list(DOCUMENT_FIELDS),
    licensable=True,
    default_enabled=True,
    core=False,
)

__all__ = ["MANIFEST"]
