from __future__ import annotations

import uuid

from app.logging import request_id_var
from core.actions.registry import ActionContext
from core.api.concurrency import parse_if_match
from core.api.pagination import PageParams, page_params
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from modules.sample.actions import (
    create_note,
    delete_note,
    get_note,
    list_notes,
    restore_note,
    update_note,
)
from modules.sample.schemas import NoteCreate, NoteList, NoteUpdate

router = APIRouter(tags=["sample"])


def _context(principal: Principal, session: AsyncSession) -> ActionContext:
    return ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )


@router.get("/notes", response_model=NoteList)
async def get_notes(
    params: PageParams = Depends(page_params),
    q: str | None = Query(None, max_length=200),
    author: str | None = Query(None, max_length=200),
    principal: Principal = Depends(require("sample.notes.view")),
    session: AsyncSession = Depends(get_session),
) -> NoteList:
    payload = {
        "limit": params.limit,
        "cursor": params.cursor,
        "sort": params.sort or "created_at",
        "order": params.order,
        "q": q,
        "author": author,
    }
    return await list_notes(_context(principal, session), payload)


@router.post("/notes", response_model=None)
async def post_note(
    payload: NoteCreate,
    principal: Principal = Depends(require("sample.notes.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    note = await create_note(_context(principal, session), payload.model_dump())
    return note.model_dump(mode="json")


@router.patch("/notes/{note_id}", response_model=None)
async def patch_note(
    note_id: uuid.UUID,
    payload: NoteUpdate,
    principal: Principal = Depends(require("sample.notes.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    body = {**payload.model_dump(), "note_id": str(note_id)}
    note = await update_note(_context(principal, session), body)
    return note.model_dump(mode="json")


@router.get("/notes/{note_id}", response_model=None)
async def get_note_detail(
    note_id: uuid.UUID,
    principal: Principal = Depends(require("sample.notes.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    note = await get_note(_context(principal, session), {"note_id": str(note_id)})
    return note.model_dump(mode="json")


@router.delete("/notes/{note_id}", response_model=None)
async def delete_note_route(
    note_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("sample.notes.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    body = {"note_id": str(note_id), "row_version": expected, "reason": reason}
    return await delete_note(_context(principal, session), body)


@router.post("/notes/{note_id}/restore", response_model=None)
async def restore_note_route(
    note_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("sample.notes.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    note = await restore_note(_context(principal, session), {"note_id": str(note_id), "reason": reason})
    return note.model_dump(mode="json")


@router.get("/ping")
async def sample_ping(
    principal: Principal = Depends(require("sample.notes.view")),
) -> dict:
    return {"module": "sample", "user": principal.display_name, "ok": True}


@router.post("/pdf")
async def sample_pdf(principal: Principal = Depends(require("sample.notes.view"))) -> Response:
    from core.documents.pdf import render_sample_pdf

    result = await render_sample_pdf()
    return Response(
        content=result.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="amharic-spike.pdf"',
            "X-PDF-Engine": result.engine,
        },
    )
