"""Action-registry entry points for curriculum profiles."""

from __future__ import annotations

import uuid

from app.errors import Forbidden
from core.actions.registry import ActionContext, action

from modules.academics import curriculum_service
from modules.academics.curriculum_schemas import (
    CurriculumApply,
    CurriculumApplyOut,
    CurriculumLevelReplace,
    CurriculumProfileCreate,
    CurriculumProfileDuplicate,
    CurriculumProfileList,
    CurriculumProfileOut,
    CurriculumProfileUpdate,
)


def _require_manager_for_hidden(ctx: ActionContext, include_inactive: bool) -> None:
    if include_inactive and not ctx.principal.can("academics.manage"):
        raise Forbidden(
            "Managing the catalog requires academics.manage",
            details={"permission": "academics.manage"},
        )


async def _commit(ctx: ActionContext) -> None:
    await ctx.session.commit()


@action(
    key="academics.curriculum.list",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="List curriculum profiles",
    output=CurriculumProfileList,
)
async def list_profiles(ctx: ActionContext, payload: dict | None = None) -> CurriculumProfileList:
    data = payload or {}
    include_inactive = bool(data.get("include_inactive"))
    _require_manager_for_hidden(ctx, include_inactive)
    return await curriculum_service.list_profiles(ctx.session, include_inactive=include_inactive)


@action(
    key="academics.curriculum.get",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="Read one curriculum profile with its subjects per level",
    output=CurriculumProfileOut,
)
async def get_profile(ctx: ActionContext, payload: dict) -> CurriculumProfileOut:
    return await curriculum_service.get_profile(ctx.session, uuid.UUID(str(payload["profile_id"])))


@action(
    key="academics.curriculum.create",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Create a blank curriculum profile",
    input=CurriculumProfileCreate,
    output=CurriculumProfileOut,
)
async def create_profile(ctx: ActionContext, payload: dict) -> CurriculumProfileOut:
    data = CurriculumProfileCreate.model_validate(payload)
    result = await curriculum_service.create_profile(ctx.session, ctx.principal, data, via=ctx.via)
    await _commit(ctx)
    return result


@action(
    key="academics.curriculum.update",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Edit a curriculum profile using optimistic concurrency",
    input=CurriculumProfileUpdate,
    output=CurriculumProfileOut,
)
async def update_profile(ctx: ActionContext, payload: dict) -> CurriculumProfileOut:
    data = CurriculumProfileUpdate.model_validate(payload)
    result = await curriculum_service.update_profile(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["profile_id"])),
        data,
        via=ctx.via,
        reason=payload.get("reason"),
    )
    await _commit(ctx)
    return result


@action(
    key="academics.curriculum.delete",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Soft-delete a custom curriculum profile (reversible)",
    output=CurriculumProfileOut,
)
async def delete_profile(ctx: ActionContext, payload: dict) -> CurriculumProfileOut:
    result = await curriculum_service.delete_profile(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["profile_id"])),
        row_version=payload.get("row_version"),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.curriculum.restore",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Restore a soft-deleted curriculum profile",
    output=CurriculumProfileOut,
)
async def restore_profile(ctx: ActionContext, payload: dict) -> CurriculumProfileOut:
    result = await curriculum_service.restore_profile(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["profile_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.curriculum.duplicate",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Duplicate a curriculum profile, including its subjects per level",
    input=CurriculumProfileDuplicate,
    output=CurriculumProfileOut,
)
async def duplicate_profile(ctx: ActionContext, payload: dict) -> CurriculumProfileOut:
    data = CurriculumProfileDuplicate.model_validate(payload)
    result = await curriculum_service.duplicate_profile(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["profile_id"])),
        data,
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.curriculum.subjects.replace",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Replace the subjects a profile offers at one level",
    input=CurriculumLevelReplace,
    output=CurriculumProfileOut,
)
async def replace_level_subjects(ctx: ActionContext, payload: dict) -> CurriculumProfileOut:
    data = CurriculumLevelReplace.model_validate(payload)
    result = await curriculum_service.replace_level_subjects(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["profile_id"])),
        uuid.UUID(str(payload["level_id"])),
        data,
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.curriculum.apply",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Preview or apply a curriculum profile from a chosen academic year",
    input=CurriculumApply,
    output=CurriculumApplyOut,
)
async def apply_profile(ctx: ActionContext, payload: dict) -> CurriculumApplyOut:
    data = CurriculumApply.model_validate(payload)
    result = await curriculum_service.apply_profile(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["profile_id"])),
        data,
        via=ctx.via,
    )
    if data.confirm:
        await _commit(ctx)
    return result


__all__ = [
    "apply_profile",
    "create_profile",
    "delete_profile",
    "duplicate_profile",
    "get_profile",
    "list_profiles",
    "replace_level_subjects",
    "restore_profile",
    "update_profile",
]
