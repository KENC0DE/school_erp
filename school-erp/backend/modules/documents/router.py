"""HTTP routes for Document Studio (P5-02 fields, P5-04 templates).

Static paths are declared before ``/templates/{template_id}`` so
``/templates/starters`` and ``/templates/import`` can never be read as an id.
Every route is gated by the design permission while the only actors are
designers; generation gets its own permission in P5-08.
"""

from __future__ import annotations

import uuid

from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session as db_session
from core.documents.registry import FORMAT_OPTIONS
from core.documents.service import fields_for
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from modules.documents.schemas import (
    DocType,
    DocumentFieldOut,
    DocumentFieldsOut,
    DocumentFormatOptions,
    StarterList,
    StarterOut,
    TemplateCreate,
    TemplateDeleted,
    TemplateDetail,
    TemplateDuplicate,
    TemplateFile,
    TemplateList,
    TemplateUpdate,
    VersionCreate,
    VersionDetail,
    VersionList,
    VersionSave,
)
from modules.documents.service import (
    create_template,
    create_version,
    delete_template,
    duplicate_template,
    export_template,
    import_template,
    list_templates,
    publish_version,
    save_version,
    template_detail,
    update_template,
    version_detail,
)
from modules.documents.starters import STARTERS, starter_view

router = APIRouter(tags=["documents"])
DESIGN = "documents.template.design"


@router.get("/fields", response_model=DocumentFieldsOut)
async def list_fields_route(
    request: Request,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> DocumentFieldsOut:
    """Fields from enabled modules, with the formatting options they support."""
    registered = await fields_for(
        session,
        request.app.state.registry,
        request.app.state.settings,
    )
    return DocumentFieldsOut(
        items=[DocumentFieldOut(**item.to_dict()) for item in registered],
        format_options=DocumentFormatOptions(
            calendar=list(FORMAT_OPTIONS["calendar"]),
            script=list(FORMAT_OPTIONS["script"]),
            money=list(FORMAT_OPTIONS["money"]),
        ),
    )


@router.get("/templates", response_model=TemplateList)
async def list_templates_route(
    doc_type: DocType | None = Query(None),
    q: str | None = Query(None, max_length=120),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> TemplateList:
    items, total = await list_templates(session, doc_type=doc_type, q=q, limit=limit, offset=offset)
    return TemplateList(items=items, total=total)


@router.get("/templates/starters", response_model=StarterList)
async def list_starters_route(
    principal: Principal = Depends(require(DESIGN)),
) -> StarterList:
    """The starter library: layouts plus the keys the client translates."""
    return StarterList(items=[StarterOut(**starter_view(item)) for item in STARTERS])


@router.post("/templates/import", response_model=TemplateDetail, status_code=201)
async def import_template_route(
    payload: TemplateFile,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> TemplateDetail:
    """Import a file produced by the export route as a new template."""
    return await import_template(session, principal, payload, via=principal.via)


@router.post("/templates", response_model=TemplateDetail, status_code=201)
async def create_template_route(
    payload: TemplateCreate,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> TemplateDetail:
    return await create_template(session, principal, payload, via=principal.via)


@router.get("/templates/{template_id}", response_model=TemplateDetail)
async def template_detail_route(
    template_id: uuid.UUID,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> TemplateDetail:
    return await template_detail(session, template_id)


@router.patch("/templates/{template_id}", response_model=TemplateDetail)
async def update_template_route(
    template_id: uuid.UUID,
    payload: TemplateUpdate,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> TemplateDetail:
    return await update_template(session, principal, template_id, payload, via=principal.via)


@router.delete("/templates/{template_id}", response_model=TemplateDeleted)
async def delete_template_route(
    template_id: uuid.UUID,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> TemplateDeleted:
    result = await delete_template(session, principal, template_id, via=principal.via)
    return TemplateDeleted(**result)


@router.post("/templates/{template_id}/duplicate", response_model=TemplateDetail, status_code=201)
async def duplicate_template_route(
    template_id: uuid.UUID,
    payload: TemplateDuplicate,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> TemplateDetail:
    return await duplicate_template(session, principal, template_id, payload, via=principal.via)


@router.get("/templates/{template_id}/export", response_model=None)
async def export_template_route(
    template_id: uuid.UUID,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> JSONResponse:
    payload = await export_template(session, template_id)
    return JSONResponse(
        content=payload.model_dump(mode="json"),
        headers={"Content-Disposition": f'attachment; filename="{payload.template.key}.json"'},
    )


@router.get("/templates/{template_id}/versions", response_model=VersionList)
async def list_versions_route(
    template_id: uuid.UUID,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> VersionList:
    detail = await template_detail(session, template_id)
    return VersionList(items=detail.versions, total=len(detail.versions))


@router.post("/templates/{template_id}/versions", response_model=VersionDetail, status_code=201)
async def create_version_route(
    template_id: uuid.UUID,
    payload: VersionCreate | None = None,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> VersionDetail:
    return await create_version(
        session, principal, template_id, payload or VersionCreate(), via=principal.via
    )


@router.get("/templates/{template_id}/versions/{version_id}", response_model=VersionDetail)
async def version_detail_route(
    template_id: uuid.UUID,
    version_id: uuid.UUID,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> VersionDetail:
    return await version_detail(session, template_id, version_id)


@router.patch("/templates/{template_id}/versions/{version_id}", response_model=VersionDetail)
async def save_version_route(
    template_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: VersionSave,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> VersionDetail:
    return await save_version(session, principal, template_id, version_id, payload, via=principal.via)


@router.post(
    "/templates/{template_id}/versions/{version_id}/publish",
    response_model=VersionDetail,
)
async def publish_version_route(
    template_id: uuid.UUID,
    version_id: uuid.UUID,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> VersionDetail:
    return await publish_version(session, principal, template_id, version_id, via=principal.via)


__all__ = ["router"]
