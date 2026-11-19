"""HTTP routes for Document Studio (P5-02 fields, P5-04 templates, P5-08 generation).

Static paths are declared before ``/templates/{template_id}`` so
``/templates/starters`` and ``/templates/import`` can never be read as an id.
Design routes need ``documents.template.design``; generation and everything
that reads an issued artifact need ``documents.generate``. P5-10 adds the
approval workflow and narrows these further.

Generation is asynchronous: the route validates the target and records the
batch, then hands the expensive rendering to the worker. Tests and brokers are
deliberately decoupled, so nothing here talks to Celery in the test environment.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.errors import Forbidden
from core.api.pagination import PageParams, page_params
from core.auth.deps import public_access, require
from core.auth.principal import Principal
from core.db.deps import get_session as db_session
from core.documents.registry import FORMAT_OPTIONS
from core.documents.service import fields_for
from core.files.deps import get_app_settings, get_storage
from core.files.storage import Storage
from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from modules.documents.generation import (
    create_batch,
    generation_targets,
    search_generation_students,
)
from modules.documents.issued import (
    batch_download,
    get_batch,
    get_issued,
    list_batches,
    list_issued,
    reprint,
)
from modules.documents.preview import (
    common_context,
    render_preview,
    sample_context,
    student_context,
)
from modules.documents.schemas import (
    DocType,
    DocumentFieldOut,
    DocumentFieldsOut,
    DocumentFormatOptions,
    DocumentGenerationOut,
    DocumentGenerationRequest,
    DocumentPreviewOut,
    DocumentPreviewRequest,
    DocumentVerificationOut,
    FileLinkOut,
    GenerationBatchList,
    GenerationBatchOut,
    GenerationStudentList,
    GenerationTargetsOut,
    IssuedDocumentDetail,
    IssuedDocumentList,
    ReprintOut,
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
from modules.documents.verification import verify_document

logger = logging.getLogger("erp.documents")

router = APIRouter(tags=["documents"])
DESIGN = "documents.template.design"
GENERATE = "documents.generate"


# --- public verification ----------------------------------------------------
# Declared before the gated routes. The endpoint is intentionally public and
# returns a minimal view; the module gate still applies to the router.


@router.get(
    "/public/verify/{code}",
    response_model=DocumentVerificationOut,
    dependencies=[Depends(public_access)],
)
async def verify_document_route(
    request: Request,
    code: str = Path(max_length=64),
    session: AsyncSession = Depends(db_session),
    settings=Depends(get_app_settings),  # type: ignore[no-untyped-def]
) -> DocumentVerificationOut:
    return await verify_document(session, settings, code, request)


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


@router.post("/preview", response_model=DocumentPreviewOut)
async def preview_route(
    request: Request,
    payload: DocumentPreviewRequest,
    principal: Principal = Depends(require(DESIGN)),
    session: AsyncSession = Depends(db_session),
) -> DocumentPreviewOut:
    """Render the unsaved layout with sample or real student data.

    The response is the exact HTML the production renderer prints, so the
    preview cannot drift from the PDF. Real student data is only read when the
    caller may see that student's record.
    """
    if payload.mode == "student":
        if not principal.can("students.view"):
            raise Forbidden(
                "Previewing a student needs access to student records",
                message_key="error.permission_denied",
                details={"permission": "students.view"},
            )
        assert payload.student_id is not None  # guarded by the request model
        data, student_name = await student_context(session, principal, payload.student_id)
        common = await common_context(session)
        rendered = render_preview(
            payload.layout,
            {**data, **common},
            locale=principal.locale,
        )
        return DocumentPreviewOut(
            mode="student",
            student_id=payload.student_id,
            student_name=student_name,
            **rendered,
        )

    fields = await fields_for(
        session,
        request.app.state.registry,
        request.app.state.settings,
    )
    context = {**sample_context(fields), **await common_context(session)}
    rendered = render_preview(payload.layout, context, locale=principal.locale)
    return DocumentPreviewOut(mode="sample", **rendered)


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


# --- generation -------------------------------------------------------------
# Static generation paths come before any ``/generation/batches/{id}`` route so
# neither can be read as the other.


@router.get("/generation/targets", response_model=GenerationTargetsOut)
async def generation_targets_route(
    principal: Principal = Depends(require(GENERATE)),
    session: AsyncSession = Depends(db_session),
) -> GenerationTargetsOut:
    """The current year's levels and sections for the generation dialog."""
    return await generation_targets(session)


@router.get("/generation/students", response_model=GenerationStudentList)
async def generation_students_route(
    q: str | None = Query(None, max_length=120),
    limit: int = Query(20, ge=1, le=50),
    principal: Principal = Depends(require(GENERATE)),
    session: AsyncSession = Depends(db_session),
) -> GenerationStudentList:
    return await search_generation_students(
        session,
        q=q,
        limit=limit,
        locale=principal.locale,
    )


@router.post("/generation", response_model=DocumentGenerationOut, status_code=202)
async def generate_route(
    request: Request,
    payload: DocumentGenerationRequest,
    principal: Principal = Depends(require(GENERATE)),
    session: AsyncSession = Depends(db_session),
) -> DocumentGenerationOut:
    """Validate a target, record the batch and queue the worker.

    The response returns immediately with the job and batch ids; the client
    polls the batch for progress. A bulk of hundreds of students therefore never
    ties up the request.
    """
    batch, job = await create_batch(session, principal, payload)
    settings = request.app.state.settings
    if settings.app_env != "test":
        try:
            from core.events.celery_app import documents_generate_task

            await asyncio.to_thread(
                documents_generate_task.delay,
                str(job.id),
                str(batch.id),
            )
        except Exception as exc:  # pragma: no cover - broker outages are operational
            logger.warning("document batch enqueue failed for %s: %s", batch.id, exc)
    return DocumentGenerationOut(
        job_id=job.id,
        batch_id=batch.id,
        count=batch.count,
        status=batch.status,
    )


@router.get("/generation/batches", response_model=GenerationBatchList)
async def list_batches_route(
    template_id: uuid.UUID | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    principal: Principal = Depends(require(GENERATE)),
    session: AsyncSession = Depends(db_session),
    storage: Storage = Depends(get_storage),
    settings=Depends(get_app_settings),  # type: ignore[no-untyped-def]
) -> GenerationBatchList:
    return await list_batches(
        session,
        storage,
        settings,
        template_id=template_id,
        limit=limit,
    )


@router.get("/generation/batches/{batch_id}", response_model=GenerationBatchOut)
async def get_batch_route(
    batch_id: uuid.UUID,
    principal: Principal = Depends(require(GENERATE)),
    session: AsyncSession = Depends(db_session),
    storage: Storage = Depends(get_storage),
    settings=Depends(get_app_settings),  # type: ignore[no-untyped-def]
) -> GenerationBatchOut:
    return await get_batch(session, storage, settings, batch_id)


@router.get("/generation/batches/{batch_id}/download", response_model=FileLinkOut)
async def batch_download_route(
    batch_id: uuid.UUID,
    principal: Principal = Depends(require(GENERATE)),
    session: AsyncSession = Depends(db_session),
    storage: Storage = Depends(get_storage),
    settings=Depends(get_app_settings),  # type: ignore[no-untyped-def]
) -> FileLinkOut:
    return await batch_download(session, storage, settings, batch_id)


# --- issued documents -------------------------------------------------------


@router.get("/issued", response_model=IssuedDocumentList)
async def list_issued_route(
    template_id: uuid.UUID | None = Query(None),
    batch_id: uuid.UUID | None = Query(None),
    recipient_id: uuid.UUID | None = Query(None),
    q: str | None = Query(None, max_length=120),
    params: PageParams = Depends(page_params),
    principal: Principal = Depends(require(GENERATE)),
    session: AsyncSession = Depends(db_session),
    storage: Storage = Depends(get_storage),
    settings=Depends(get_app_settings),  # type: ignore[no-untyped-def]
) -> IssuedDocumentList:
    return await list_issued(
        session,
        storage,
        settings,
        params,
        template_id=template_id,
        batch_id=batch_id,
        recipient_id=recipient_id,
        q=q,
    )


@router.get("/issued/{issued_id}", response_model=IssuedDocumentDetail)
async def get_issued_route(
    issued_id: uuid.UUID,
    principal: Principal = Depends(require(GENERATE)),
    session: AsyncSession = Depends(db_session),
    storage: Storage = Depends(get_storage),
    settings=Depends(get_app_settings),  # type: ignore[no-untyped-def]
) -> IssuedDocumentDetail:
    return await get_issued(session, storage, settings, issued_id)


@router.get("/issued/{issued_id}/reprint", response_model=ReprintOut)
async def reprint_route(
    issued_id: uuid.UUID,
    principal: Principal = Depends(require(GENERATE)),
    session: AsyncSession = Depends(db_session),
    storage: Storage = Depends(get_storage),
    settings=Depends(get_app_settings),  # type: ignore[no-untyped-def]
) -> ReprintOut:
    """Serve the stored artifact again; never re-render today's data."""
    return await reprint(session, principal, storage, settings, issued_id)


__all__ = ["router"]
