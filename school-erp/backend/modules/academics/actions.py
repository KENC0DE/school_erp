"""Action-registry entry points for academic structure.

The routers and the AI layer both call these functions, so every catalog change
is audited and permission-checked identically.
"""

from __future__ import annotations

import uuid

from app.errors import Forbidden
from core.actions.registry import ActionContext, action

from modules.academics import service
from modules.academics.schemas import (
    LevelCreate,
    LevelList,
    LevelOut,
    LevelUpdate,
    ScopeOut,
    ScopeUpdate,
    StageCreate,
    StageList,
    StageOut,
    StageUpdate,
)


def _require_catalog_manager(ctx: ActionContext, *, all_scope: bool, include_inactive: bool) -> None:
    """Mirror the router guard so an AI/tool invocation cannot see hidden rows."""
    if (all_scope or include_inactive) and not ctx.principal.can("academics.manage"):
        raise Forbidden(
            "Managing the catalog requires academics.manage",
            details={"permission": "academics.manage"},
        )


async def _commit(ctx: ActionContext):
    await ctx.session.commit()


@action(
    key="academics.levels.list",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="List grade levels inside the school's scope",
    output=LevelList,
)
async def list_levels(ctx: ActionContext, payload: dict | None = None) -> LevelList:
    data = payload or {}
    all_scope = bool(data.get("all_scope"))
    include_inactive = bool(data.get("include_inactive"))
    _require_catalog_manager(ctx, all_scope=all_scope, include_inactive=include_inactive)
    return await service.list_levels(
        ctx.session,
        all_scope=all_scope,
        include_inactive=include_inactive,
    )


@action(
    key="academics.levels.get",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="Read one grade level",
    output=LevelOut,
)
async def get_level(ctx: ActionContext, payload: dict) -> LevelOut:
    all_scope = bool(payload.get("all_scope"))
    _require_catalog_manager(ctx, all_scope=all_scope, include_inactive=False)
    return await service.get_level(
        ctx.session,
        uuid.UUID(str(payload["level_id"])),
        all_scope=all_scope,
    )


@action(
    key="academics.levels.create",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Add a grade level to the catalog",
    input=LevelCreate,
    output=LevelOut,
)
async def create_level(ctx: ActionContext, payload: dict) -> LevelOut:
    data = LevelCreate.model_validate(payload)
    result = await service.create_level(ctx.session, ctx.principal, data, via=ctx.via)
    await _commit(ctx)
    return result


@action(
    key="academics.levels.update",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Edit a grade level using optimistic concurrency",
    input=LevelUpdate,
    output=LevelOut,
)
async def update_level(ctx: ActionContext, payload: dict) -> LevelOut:
    data = LevelUpdate.model_validate(payload)
    result = await service.update_level(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["level_id"])),
        data,
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.levels.delete",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Soft-delete a grade level (reversible)",
    output=LevelOut,
)
async def delete_level(ctx: ActionContext, payload: dict) -> LevelOut:
    result = await service.delete_level(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["level_id"])),
        row_version=payload.get("row_version"),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.levels.restore",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Restore a soft-deleted grade level",
    output=LevelOut,
)
async def restore_level(ctx: ActionContext, payload: dict) -> LevelOut:
    result = await service.restore_level(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["level_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.stages.list",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="List stages inside the school's scope",
    output=StageList,
)
async def list_stages(ctx: ActionContext, payload: dict | None = None) -> StageList:
    data = payload or {}
    all_scope = bool(data.get("all_scope"))
    include_inactive = bool(data.get("include_inactive"))
    _require_catalog_manager(ctx, all_scope=all_scope, include_inactive=include_inactive)
    return await service.list_stages(
        ctx.session,
        all_scope=all_scope,
        include_inactive=include_inactive,
    )


@action(
    key="academics.stages.get",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="Read one stage and its grade levels",
    output=StageOut,
)
async def get_stage(ctx: ActionContext, payload: dict) -> StageOut:
    all_scope = bool(payload.get("all_scope"))
    _require_catalog_manager(ctx, all_scope=all_scope, include_inactive=False)
    return await service.get_stage(
        ctx.session,
        uuid.UUID(str(payload["stage_id"])),
        all_scope=all_scope,
    )


@action(
    key="academics.stages.create",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Add a stage and choose its grade levels",
    input=StageCreate,
    output=StageOut,
)
async def create_stage(ctx: ActionContext, payload: dict) -> StageOut:
    data = StageCreate.model_validate(payload)
    result = await service.create_stage(ctx.session, ctx.principal, data, via=ctx.via)
    await _commit(ctx)
    return result


@action(
    key="academics.stages.update",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Edit a stage or its grade levels using optimistic concurrency",
    input=StageUpdate,
    output=StageOut,
)
async def update_stage(ctx: ActionContext, payload: dict) -> StageOut:
    data = StageUpdate.model_validate(payload)
    result = await service.update_stage(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["stage_id"])),
        data,
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.stages.delete",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Soft-delete a stage (reversible)",
    output=StageOut,
)
async def delete_stage(ctx: ActionContext, payload: dict) -> StageOut:
    result = await service.delete_stage(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["stage_id"])),
        row_version=payload.get("row_version"),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.stages.restore",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Restore a soft-deleted stage",
    output=StageOut,
)
async def restore_stage(ctx: ActionContext, payload: dict) -> StageOut:
    result = await service.restore_stage(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["stage_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.scope.get",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="Read the school's academic scope",
    output=ScopeOut,
)
async def get_scope(ctx: ActionContext, payload: dict | None = None) -> ScopeOut:
    return await service.scope_view(ctx.session)


@action(
    key="academics.scope.update",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Change which grade levels the school operates",
    input=ScopeUpdate,
    output=ScopeOut,
)
async def update_scope(ctx: ActionContext, payload: dict) -> ScopeOut:
    data = ScopeUpdate.model_validate(payload)
    result = await service.update_scope(ctx.session, ctx.principal, data, via=ctx.via)
    await _commit(ctx)
    return result


__all__ = [
    "create_level",
    "create_stage",
    "delete_level",
    "delete_stage",
    "get_level",
    "get_scope",
    "get_stage",
    "list_levels",
    "list_stages",
    "restore_level",
    "restore_stage",
    "update_level",
    "update_scope",
    "update_stage",
]
