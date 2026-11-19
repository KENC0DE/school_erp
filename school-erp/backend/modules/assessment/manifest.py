from __future__ import annotations

from core.modules.manifest import ModuleManifest, Nav, Perm

from modules.assessment import actions as _actions  # noqa: F401 - registers actions
from modules.assessment import models as _models  # noqa: F401 - registers models
from modules.assessment.fields import FIELDS
from modules.assessment.router import router

MANIFEST = ModuleManifest(
    key="assessment",
    name="Assessment",
    version="0.1.0",
    description=(
        "Mark structures, teacher scores, versioned grade scales, marking windows, "
        "submissions, corrections and published term and year results."
    ),
    depends_on=["academics", "students", "staff"],
    document_fields=list(FIELDS),
    permissions=[
        Perm(
            "assessment.view",
            "assessment.perm.view",
            scopes=(
                "all",
                "department",
                "assigned_subjects",
                "own_class",
                "own_children",
                "self",
            ),
        ),
        Perm("assessment.manage", "assessment.perm.manage"),
        Perm(
            "assessment.enter_marks",
            "assessment.perm.enter_marks",
            scopes=("all", "assigned_subjects"),
        ),
        Perm(
            "assessment.submit",
            "assessment.perm.submit",
            scopes=("all", "assigned_subjects"),
        ),
        Perm(
            "assessment.approve",
            "assessment.perm.approve",
            scopes=("all", "department"),
        ),
        Perm("assessment.publish", "assessment.perm.publish"),
        Perm(
            "assessment.correct",
            "assessment.perm.correct",
            scopes=("all", "assigned_subjects"),
        ),
        Perm(
            "assessment.correct_approve",
            "assessment.perm.correct_approve",
            scopes=("all", "department"),
        ),
    ],
    nav=[
        Nav(
            key="assessment",
            label_key="assessment.nav",
            path="/assessment",
            perm="assessment.view",
            icon="clipboard-list",
            order=26,
        )
    ],
    router=router,
    actions=[*_actions.__all__],
    events=["marks.submitted", "marks.published"],
    i18n_namespaces=["assessment"],
    licensable=True,
    default_enabled=True,
    core=False,
)

__all__ = ["MANIFEST"]
