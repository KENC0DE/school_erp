from __future__ import annotations

from app.logging import request_id_var
from core.actions.registry import ActionContext
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from modules.sample.actions import create_note, list_notes
from modules.sample.schemas import NoteCreate, NoteList

router = APIRouter(tags=["sample"])


@router.get("/notes", response_model=NoteList)
async def get_notes(
    principal: Principal = Depends(require("sample.notes.view")),
    session: AsyncSession = Depends(get_session),
) -> NoteList:
    ctx = ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )
    return await list_notes(ctx, {})


@router.post("/notes", response_model=None)
async def post_note(
    payload: NoteCreate,
    principal: Principal = Depends(require("sample.notes.create")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ctx = ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )
    note = await create_note(ctx, payload.model_dump())
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
