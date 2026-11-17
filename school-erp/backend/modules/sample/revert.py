"""Revert handlers for the sample module (proves the P1-11 protocol)."""

from __future__ import annotations

import uuid

from app.errors import NotFound
from core.audit.revert import RevertContext, Reverter, register_reverter
from core.db.soft_delete import get_including_deleted, mark_deleted, mark_restored

from modules.sample.models import SampleNote


def _state(note: SampleNote) -> dict:
    return {
        "content": note.content,
        "author_name": note.author_name,
        "row_version": note.row_version,
        "deleted_at": note.deleted_at.isoformat() if note.deleted_at else None,
    }


async def _get(ctx: RevertContext) -> SampleNote:
    note = await get_including_deleted(ctx.session, SampleNote, uuid.UUID(ctx.entity_id))
    if note is None:
        raise NotFound("The note does not exist")
    return note


async def apply_revert(ctx: RevertContext) -> dict:
    note = await _get(ctx)
    if ctx.before is None:
        # The entry created the note: reverting a creation removes it (soft).
        mark_deleted(note, actor=ctx.principal)
    elif ctx.before.get("deleted_at"):
        mark_restored(note, actor=ctx.principal)
    else:
        if (ctx.before.get("content") or "") != note.content:
            note.content = ctx.before.get("content") or ""
        note.row_version = (note.row_version or 0) + 1
    await ctx.session.flush()
    return _state(note)


async def restore_note_revert(ctx: RevertContext) -> dict:
    note = await _get(ctx)
    mark_restored(note, actor=ctx.principal)
    await ctx.session.flush()
    return _state(note)


register_reverter(
    Reverter(
        entity_type="sample_note",
        module="sample",
        permission="sample.notes.create",
        apply=apply_revert,
        restore=restore_note_revert,
    )
)

__all__ = ["apply_revert", "restore_note_revert"]
