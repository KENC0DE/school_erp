"""HTTP routes for admission applications, decisions, conversion and documents."""

from __future__ import annotations

import uuid
from typing import Literal

from app.logging import request_id_var
from app.settings import Settings
from core.actions.registry import ActionContext
from core.api.concurrency import parse_if_match
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from core.files.deps import get_app_settings, get_storage
from core.files.storage import Storage
from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from modules.admissions import documents_service, public
from modules.admissions.actions import (
    convert_application,
    create_application,
    decide_application,
    delete_application,
    form_view,
    get_application,
    preview_application,
    preview_conversion,
    restore_application,
    search_applications,
    update_application,
)
from modules.admissions.public import (
    PublicApplicationCreate,
    PublicApplicationOut,
    PublicFormOut,
)
from modules.admissions.schemas import (
    AdmissionFormOut,
    AdmissionStatus,
    ApplicationCreate,
    ApplicationCreateOut,
    ApplicationList,
    ApplicationOut,
    ApplicationPreview,
    ApplicationQuery,
    ApplicationUpdate,
    ConversionInput,
    ConversionOut,
    ConversionPreview,
    DecisionInput,
    DecisionOut,
)

router = APIRouter(tags=["admissions"])


def _context(
    principal: Principal,
    session: AsyncSession,
    request: Request | None = None,
    settings: Settings | None = None,
) -> ActionContext:
    return ActionContext(
        principal=principal,
        session=session,
        via=principal.via,
        request_id=request_id_var.get(),
        request=request,
        settings=settings,
    )


def _with_application(payload: dict, application_id: uuid.UUID) -> dict:
    return {**payload, "application_id": str(application_id)}


@router.get("/public/form", response_model=PublicFormOut)
async def public_form_route(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> PublicFormOut:
    """The optional public page. No account is required to read the form."""
    return await public.form_view(session, settings)


@router.post("/public/applications", response_model=PublicApplicationOut, status_code=201)
async def submit_public_application_route(
    payload: PublicApplicationCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> PublicApplicationOut:
    """Accept a public submission after the token, honeypot and rate checks."""
    return await public.submit_application(session, settings, payload, request)


@router.get("", response_model=ApplicationList)
async def list_applications_route(
    q: str | None = Query(None, max_length=120),
    status: AdmissionStatus | None = Query(None),
    year_id: uuid.UUID | None = Query(None),
    level_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    cursor: str | None = Query(None, max_length=1000),
    sort: str | None = Query(None, max_length=60),
    order: Literal["asc", "desc"] = Query("desc"),
    principal: Principal = Depends(require("admissions.view")),
    session: AsyncSession = Depends(get_session),
) -> ApplicationList:
    query = ApplicationQuery(
        q=q,
        status=status,
        year_id=year_id,
        level_id=level_id,
        section_id=section_id,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
    )
    return await search_applications(_context(principal, session), query.model_dump())


@router.get("/form", response_model=AdmissionFormOut)
async def form_route(
    principal: Principal = Depends(require("admissions.view")),
    session: AsyncSession = Depends(get_session),
) -> AdmissionFormOut:
    return await form_view(_context(principal, session), {})


@router.post("/preview", response_model=ApplicationPreview)
async def preview_route(
    payload: ApplicationCreate,
    principal: Principal = Depends(require("admissions.manage")),
    session: AsyncSession = Depends(get_session),
) -> ApplicationPreview:
    return await preview_application(_context(principal, session), payload.model_dump())


@router.post("", response_model=ApplicationCreateOut, status_code=201)
async def create_application_route(
    payload: ApplicationCreate,
    principal: Principal = Depends(require("admissions.manage")),
    session: AsyncSession = Depends(get_session),
) -> ApplicationCreateOut:
    return await create_application(_context(principal, session), payload.model_dump())


@router.get("/{application_id}", response_model=ApplicationOut)
async def get_application_route(
    application_id: uuid.UUID,
    principal: Principal = Depends(require("admissions.view")),
    session: AsyncSession = Depends(get_session),
) -> ApplicationOut:
    return await get_application(_context(principal, session), {"application_id": str(application_id)})


@router.patch("/{application_id}", response_model=ApplicationOut)
async def update_application_route(
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
    principal: Principal = Depends(require("admissions.manage")),
    session: AsyncSession = Depends(get_session),
) -> ApplicationOut:
    body = _with_application(payload.model_dump(exclude_unset=True), application_id)
    return await update_application(_context(principal, session), body)


@router.post("/{application_id}/decision", response_model=DecisionOut)
async def decide_application_route(
    application_id: uuid.UUID,
    payload: DecisionInput,
    principal: Principal = Depends(require("admissions.decide")),
    session: AsyncSession = Depends(get_session),
) -> DecisionOut:
    return await decide_application(
        _context(principal, session), _with_application(payload.model_dump(), application_id)
    )


@router.get("/{application_id}/conversion", response_model=ConversionPreview)
async def conversion_preview_route(
    application_id: uuid.UUID,
    principal: Principal = Depends(require("admissions.decide")),
    session: AsyncSession = Depends(get_session),
) -> ConversionPreview:
    return await preview_conversion(_context(principal, session), {"application_id": str(application_id)})


@router.post("/{application_id}/convert", response_model=ConversionOut)
async def convert_application_route(
    application_id: uuid.UUID,
    payload: ConversionInput,
    request: Request,
    principal: Principal = Depends(require("admissions.decide")),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> ConversionOut:
    body = _with_application(payload.model_dump(), application_id)
    return await convert_application(_context(principal, session, request, settings), body)


@router.delete("/{application_id}", dependencies=[Depends(require("admissions.manage"))])
async def delete_application_route(
    application_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("admissions.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    body = _with_application({"row_version": expected, "reason": reason}, application_id)
    return await delete_application(_context(principal, session), body)


@router.post("/{application_id}/restore", response_model=ApplicationOut)
async def restore_application_route(
    application_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("admissions.manage")),
    session: AsyncSession = Depends(get_session),
) -> ApplicationOut:
    body = _with_application({"reason": reason}, application_id)
    return await restore_application(_context(principal, session), body)


@router.get("/{application_id}/documents")
async def list_documents_route(
    application_id: uuid.UUID,
    principal: Principal = Depends(require("admissions.view")),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    items = await documents_service.list_documents(session, storage, settings, application_id)
    return {"items": items}


@router.post("/{application_id}/documents", status_code=201)
async def upload_document_route(
    application_id: uuid.UUID,
    file: UploadFile = File(...),
    principal: Principal = Depends(require("admissions.manage")),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    data = await file.read(settings.storage_max_upload_bytes + 1)
    return await documents_service.upload_document(
        session,
        principal,
        storage,
        settings,
        application_id,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
    )


@router.delete("/{application_id}/documents/{file_id}")
async def delete_document_route(
    application_id: uuid.UUID,
    file_id: str,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("admissions.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await documents_service.delete_document(session, principal, application_id, file_id, reason=reason)
