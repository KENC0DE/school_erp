from __future__ import annotations

import uuid

from app.errors import NotFound, ValidationFailed
from core.actions.registry import ActionContext, action
from core.api.concurrency import apply_row_version
from core.api.pagination import FilterSpec, PageParams, apply_filters, paginate
from core.audit.service import record
from sqlalchemy import func, select

from modules.sample.models import SampleNote
from modules.sample.schemas import NoteCreate, NoteList, NoteOut, NoteQuery, NoteUpdate

SORT_COLUMNS = {
    "created_at": SampleNote.created_at,
    "author_name": SampleNote.author_name,
    "id": SampleNote.id,
}

FILTERS = {
    "q": FilterSpec(SampleNote.content, "contains"),
    "author": FilterSpec(SampleNote.author_name, "contains"),
}


async def _list(ctx: ActionContext, payload: dict | None = None) -> NoteList:
    query = NoteQuery.model_validate(payload or {})
    params = PageParams(
        limit=query.limit,
        cursor=query.cursor,
        sort=query.sort,
        order=query.order,
    )
    stmt = select(SampleNote).where(SampleNote.deleted_at.is_(None))
    stmt = apply_filters(
        stmt,
        FILTERS,
        {"q": query.q, "author": query.author},
    )
    total = (await ctx.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows, next_cursor = await paginate(
        ctx.session,
        stmt,
        params,
        sort_columns=SORT_COLUMNS,
        default_sort="created_at",
        id_column=SampleNote.id,
    )
    return NoteList(
        items=[NoteOut.from_model(row) for row in rows],
        next_cursor=next_cursor,
        total=total,
    )


@action(
    key="sample.notes.list",
    module="sample",
    permission="sample.notes.view",
    risk="read",
    describe="List the notes stored in the sample module",
    input=NoteQuery,
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


async def _update(ctx: ActionContext, payload: dict) -> NoteOut:
    data = NoteUpdate.model_validate(payload)
    note_id = payload.get("note_id")
    if not note_id:
        raise ValidationFailed("note_id is required", message_key="error.validation")
    note = await ctx.session.get(SampleNote, uuid.UUID(str(note_id)))
    if note is None or note.deleted_at is not None:
        raise NotFound("The note does not exist")
    before = NoteOut.from_model(note).model_dump(mode="json")
    changes = apply_row_version(
        note,
        data.row_version,
        {"content": data.content},
        current_state=before,
        allowed={"content"},
    )
    after = NoteOut.from_model(note).model_dump(mode="json")
    if changes:
        await record(
            ctx.session,
            action="sample.notes.update",
            module="sample",
            entity_type="sample_note",
            entity_id=str(note.id),
            before=before,
            after=after,
            actor=ctx.principal,
            via=ctx.via,
        )
    await ctx.session.commit()
    return NoteOut.from_model(note)


@action(
    key="sample.notes.update",
    module="sample",
    permission="sample.notes.create",
    risk="write",
    describe="Update a sample note using optimistic concurrency (row_version)",
    input=NoteUpdate,
    output=NoteOut,
)
async def update_note(ctx: ActionContext, payload: dict) -> NoteOut:
    return await _update(ctx, payload)


__all__ = ["create_note", "list_notes", "preview_create", "update_note"]
