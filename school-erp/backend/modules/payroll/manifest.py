from __future__ import annotations

from core.modules.manifest import ModuleManifest, Perm

from modules.payroll import actions as _actions  # noqa: F401 - registers actions
from modules.payroll import models as _models  # noqa: F401 - registers models
from modules.payroll.router import router

MANIFEST = ModuleManifest(
    key="payroll",
    name="Payroll",
    version="0.1.0",
    description=(
        "Optional payroll: salary components, configurable tax and pension rule sets, "
        "and payslips in ETB. Rates ship empty: the school's accountant supplies them."
    ),
    depends_on=["staff"],
    permissions=[
        Perm("payroll.view", "payroll.perm.view"),
        Perm("payroll.manage", "payroll.perm.manage"),
        Perm("payroll.run", "payroll.perm.run"),
    ],
    router=router,
    actions=[*_actions.__all__],
    i18n_namespaces=["payroll"],
    licensable=True,
    default_enabled=False,
    core=False,
)

__all__ = ["MANIFEST"]
