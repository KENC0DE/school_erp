from __future__ import annotations

from core.modules.manifest import ModuleManifest, Nav, Perm

from modules.documents import models as _models  # noqa: F401 - register tables
from modules.documents.router import router
from modules.documents.settings import DocumentSettings

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
    nav=[
        Nav(
            key="documents",
            label_key="documents.nav",
            path="/documents",
            perm="documents.template.design",
            icon="file-text",
            order=35,
        ),
        Nav(
            key="document-approvals",
            label_key="documents.approvals.nav",
            path="/documents/approvals",
            perm="documents.approve",
            icon="check-square",
            order=36,
        ),
    ],
    router=router,
    i18n_namespaces=["documents"],
    settings_schema=DocumentSettings,
    licensable=True,
    default_enabled=True,
    core=False,
)

__all__ = ["MANIFEST"]
