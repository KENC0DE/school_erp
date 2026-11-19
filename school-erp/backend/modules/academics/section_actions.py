"""Action-registry entry points for sections."""

from __future__ import annotations

import uuid

from app.errors import Forbidden
from core.actions.registry import ActionContext, action

from modules.academics import section_service
from modules.academics.section_schemas import SectionCreate, SectionList, SectionOut, SectionUpdate


def _require_manager_for_hidden(ctx: ActionContext, *, all_scope: bool, include_inactive: bool) -> None:
    if (all_scope or include_inactive) and not ctx.principal.can("academics.manage"):
        raise Forbidden(
            "Seeing sections outside the school's scope requires academics.manage",
            details={"permission": "academics.manage"},
        )


async def _commit(ctx: ActionContext) -> None:
    await ctx.session.commit()


@action(
    key="academics.sections.list",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="List sections, optionally by year and level",
    output=SectionList,
)
async def list_sections(ctx: ActionContext, payload: dict | None = None) -> SectionList:
    data = payload or {}
    all_scope = bool(data.get("all_scope"))
    include_inactive = bool(data.get("include_inactive"))
    _require_manager_for_hidden(ctx, all_scope=all_scope, include_inactive=include_inactive)
    year_id = data.get("year_id")
    level_id = data.get("level_id")
    return await section_service.list_sections(
        ctx.session,
        year_id=uuid.UUID(str(year_id)) if year_id else None,
        level_id=uuid.UUID(str(level_id)) if level_id else None,
        include_inactive=include_inactive,
        all_scope=all_scope,
    )


@action(
    key="academics.sections.get",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="Read one section",
    output=SectionOut,
)
async def get_section(ctx: ActionContext, payload: dict) -> SectionOut:
    all_scope = bool(payload.get("all_scope"))
    _require_manager_for_hidden(ctx, all_scope=all_scope, include_inactive=False)
    return await section_service.get_section(
        ctx.session,
        uuid.UUID(str(payload["section_id"])),
        all_scope=all_scope,
    )


@action(
    key="academics.sections.create",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Create a section for a level and academic year",
    input=SectionCreate,
    output=SectionOut,
)
async def create_section(ctx: ActionContext, payload: dict) -> SectionOut:
    data = SectionCreate.model_validate(payload)
    result = await section_service.create_section(ctx.session, ctx.principal, data, via=ctx.via)
    await _commit(ctx)
    return result


@action(
    key="academics.sections.update",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Edit a section using optimistic concurrency",
    input=SectionUpdate,
    output=SectionOut,
)
async def update_section(ctx: ActionContext, payload: dict) -> SectionOut:
    data = SectionUpdate.model_validate(payload)
    result = await section_service.update_section(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["section_id"])),
        data,
        via=ctx.via,
        reason=payload.get("reason"),
    )
    await _commit(ctx)
    return result


@action(
    key="academics.sections.delete",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Soft-delete a section (reversible)",
    output=SectionOut,
)
async def delete_section(ctx: ActionContext, payload: dict) -> SectionOut:
    result = await section_service.delete_section(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["section_id"])),
        row_version=payload.get("row_version"),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.sections.restore",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Restore a soft-deleted section",
    output=SectionOut,
)
async def restore_section(ctx: ActionContext, payload: dict) -> SectionOut:
    result = await section_service.restore_section(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["section_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


__all__ = [
    "create_section",
    "delete_section",
    "get_section",
    "list_sections",
    "restore_section",
    "update_section",
]
