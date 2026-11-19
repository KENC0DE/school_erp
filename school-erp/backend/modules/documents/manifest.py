from __future__ import annotations

from core.modules.manifest import ModuleManifest, Perm

from modules.documents import models as _models  # noqa: F401 - register tables
from modules.documents.router import router

MANIFEST = ModuleManifest(
    key="documents",
    name="Document Studio",
    version="0.1.0",
    description=(
        "Design printable templates on a canvas and generate verifiable PDFs "
        "filled from published school data."
    ),
    permissions=[
        Perm("documents.template.design", "documents.perm.template_design"),
        Perm("documents.generate", "documents.perm.generate"),
        Perm("documents.approve", "documents.perm.approve"),
    ],
    router=router,
    i18n_namespaces=["documents"],
    licensable=True,
    default_enabled=True,
    core=False,
)

__all__ = ["MANIFEST"]
