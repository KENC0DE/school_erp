from __future__ import annotations

from core.modules.manifest import ModuleManifest, Nav, Perm

from modules.academics import actions as _actions  # noqa: F401 - registers actions
from modules.academics import curriculum_actions as _curriculum_actions  # noqa: F401 - registers actions
from modules.academics import models as _models  # noqa: F401 - registers models
from modules.academics import section_actions as _section_actions  # noqa: F401 - registers actions
from modules.academics import subject_actions as _subject_actions  # noqa: F401 - registers actions
from modules.academics import year_actions as _year_actions  # noqa: F401 - registers actions
from modules.academics.defaults import ensure_default_academics
from modules.academics.router import router

MANIFEST = ModuleManifest(
    key="academics",
    name="Academic structure",
    version="0.4.0",
    description="Grade levels, stages, academic years and terms, subjects and sections, the school's scope and curriculum profiles.",
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
    actions=[
        *_actions.__all__,
        *_year_actions.__all__,
        *_subject_actions.__all__,
        *_section_actions.__all__,
        *_curriculum_actions.__all__,
    ],
    events=["term.closed"],
    i18n_namespaces=["academics"],
    bootstrap=ensure_default_academics,
    licensable=True,
    default_enabled=True,
    core=False,
)
