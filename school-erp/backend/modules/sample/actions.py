from __future__ import annotations

import uuid

from core.actions.registry import ActionContext, action
from core.audit.service import record
from sqlalchemy import select

from modules.sample.models import SampleNote
from modules.sample.schemas import NoteCreate, NoteList, NoteOut


async def _list(ctx: ActionContext, _payload: dict | None = None) -> NoteList:
    rows = (
        (
            await ctx.session.execute(
                select(SampleNote)
                .where(SampleNote.deleted_at.is_(None))
                .order_by(SampleNote.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return NoteList(items=[NoteOut.from_model(row) for row in rows])


@action(
    key="sample.notes.list",
    module="sample",
    permission="sample.notes.view",
    risk="read",
    describe="List the notes stored in the sample module",
    output=NoteList,
)
async def list_notes(ctx: ActionContext, payload: dict | None = None) -> NoteList:
    return await _list(ctx, payload)


async def preview_create(ctx: ActionContext, payload: dict) -> dict:
    data = NoteCreate.model_validate(payload)
    return {"will_create": "sample_note", "content": data.content, "count": 1}


async def _create(ctx: ActionContext, payload: dict) -> NoteOut:
    data = NoteCreate.model_validate(payload)
    note = SampleNote(
        content=data.content,
        author_name=ctx.principal.display_name,
        author_id=uuid.UUID(ctx.principal.actor_id) if ctx.principal.actor_type == "user" else None,
        created_by=uuid.UUID(ctx.principal.actor_id) if ctx.principal.actor_type == "user" else None,
    )
    ctx.session.add(note)
    await ctx.session.flush()
    await record(
        ctx.session,
        action="sample.notes.create",
        module="sample",
        entity_type="sample_note",
        entity_id=str(note.id),
        after={"content": note.content, "author_name": note.author_name},
        actor=ctx.principal,
        via=ctx.via,
    )
    await ctx.session.commit()
    return NoteOut.from_model(note)


@action(
    key="sample.notes.create",
    module="sample",
    permission="sample.notes.create",
    risk="write",
    describe="Create a sample note (used to prove audit and permissions)",
    input=NoteCreate,
    output=NoteOut,
    preview=preview_create,
)
async def create_note(ctx: ActionContext, payload: dict) -> NoteOut:
    return await _create(ctx, payload)


__all__ = ["create_note", "list_notes", "preview_create"]
