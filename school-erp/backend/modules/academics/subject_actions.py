"""Action-registry entry points for subjects, assignments and groups."""

from __future__ import annotations

import uuid

from app.errors import Forbidden
from core.actions.registry import ActionContext, action

from modules.academics import group_service, subject_service
from modules.academics.subject_schemas import (
    LevelSubjectReplace,
    LevelSubjectsOut,
    SubjectCreate,
    SubjectGroupCreate,
    SubjectGroupList,
    SubjectGroupOut,
    SubjectGroupUpdate,
    SubjectList,
    SubjectOut,
    SubjectUpdate,
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
    key="academics.subjects.list",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="List the subject catalog",
    output=SubjectList,
)
async def list_subjects(ctx: ActionContext, payload: dict | None = None) -> SubjectList:
    data = payload or {}
    include_inactive = bool(data.get("include_inactive"))
    _require_manager_for_hidden(ctx, include_inactive)
    return await subject_service.list_subjects(ctx.session, include_inactive=include_inactive)


@action(
    key="academics.subjects.get",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="Read one subject",
    output=SubjectOut,
)
async def get_subject(ctx: ActionContext, payload: dict) -> SubjectOut:
    return await subject_service.get_subject(ctx.session, uuid.UUID(str(payload["subject_id"])))


@action(
    key="academics.subjects.create",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Add a subject to the catalog",
    input=SubjectCreate,
    output=SubjectOut,
)
async def create_subject(ctx: ActionContext, payload: dict) -> SubjectOut:
    data = SubjectCreate.model_validate(payload)
    result = await subject_service.create_subject(ctx.session, ctx.principal, data, via=ctx.via)
    await _commit(ctx)
    return result


@action(
    key="academics.subjects.update",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Edit a subject using optimistic concurrency",
    input=SubjectUpdate,
    output=SubjectOut,
)
async def update_subject(ctx: ActionContext, payload: dict) -> SubjectOut:
    data = SubjectUpdate.model_validate(payload)
    result = await subject_service.update_subject(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["subject_id"])),
        data,
        via=ctx.via,
        reason=payload.get("reason"),
    )
    await _commit(ctx)
    return result


@action(
    key="academics.subjects.delete",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Soft-delete a subject (reversible)",
    output=SubjectOut,
)
async def delete_subject(ctx: ActionContext, payload: dict) -> SubjectOut:
    result = await subject_service.delete_subject(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["subject_id"])),
        row_version=payload.get("row_version"),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.subjects.restore",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Restore a soft-deleted subject",
    output=SubjectOut,
)
async def restore_subject(ctx: ActionContext, payload: dict) -> SubjectOut:
    result = await subject_service.restore_subject(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["subject_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.subjects.assignments.get",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="List the subjects a grade level offers",
    output=LevelSubjectsOut,
)
async def get_level_subjects(ctx: ActionContext, payload: dict) -> LevelSubjectsOut:
    return await subject_service.level_subjects(ctx.session, uuid.UUID(str(payload["level_id"])))


@action(
    key="academics.subjects.assignments.replace",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Replace the subjects and credits a grade level offers",
    input=LevelSubjectReplace,
    output=LevelSubjectsOut,
)
async def replace_level_subjects(ctx: ActionContext, payload: dict) -> LevelSubjectsOut:
    data = LevelSubjectReplace.model_validate(payload)
    result = await subject_service.replace_level_subjects(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["level_id"])),
        data,
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.subject_groups.list",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="List subject groups",
    output=SubjectGroupList,
)
async def list_groups(ctx: ActionContext, payload: dict | None = None) -> SubjectGroupList:
    data = payload or {}
    include_inactive = bool(data.get("include_inactive"))
    _require_manager_for_hidden(ctx, include_inactive)
    return await group_service.list_groups(ctx.session, include_inactive=include_inactive)


@action(
    key="academics.subject_groups.get",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="Read one subject group",
    output=SubjectGroupOut,
)
async def get_group(ctx: ActionContext, payload: dict) -> SubjectGroupOut:
    return await group_service.get_group(ctx.session, uuid.UUID(str(payload["group_id"])))


@action(
    key="academics.subject_groups.create",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Add a subject group",
    input=SubjectGroupCreate,
    output=SubjectGroupOut,
)
async def create_group(ctx: ActionContext, payload: dict) -> SubjectGroupOut:
    data = SubjectGroupCreate.model_validate(payload)
    result = await group_service.create_group(ctx.session, ctx.principal, data, via=ctx.via)
    await _commit(ctx)
    return result


@action(
    key="academics.subject_groups.update",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Edit a subject group or its members",
    input=SubjectGroupUpdate,
    output=SubjectGroupOut,
)
async def update_group(ctx: ActionContext, payload: dict) -> SubjectGroupOut:
    data = SubjectGroupUpdate.model_validate(payload)
    result = await group_service.update_group(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["group_id"])),
        data,
        via=ctx.via,
        reason=payload.get("reason"),
    )
    await _commit(ctx)
    return result


@action(
    key="academics.subject_groups.delete",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Soft-delete a subject group (reversible)",
    output=SubjectGroupOut,
)
async def delete_group(ctx: ActionContext, payload: dict) -> SubjectGroupOut:
    result = await group_service.delete_group(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["group_id"])),
        row_version=payload.get("row_version"),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.subject_groups.restore",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Restore a soft-deleted subject group",
    output=SubjectGroupOut,
)
async def restore_group(ctx: ActionContext, payload: dict) -> SubjectGroupOut:
    result = await group_service.restore_group(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["group_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


__all__ = [
    "create_group",
    "create_subject",
    "delete_group",
    "delete_subject",
    "get_group",
    "get_level_subjects",
    "get_subject",
    "list_groups",
    "list_subjects",
    "replace_level_subjects",
    "restore_group",
    "restore_subject",
    "update_group",
    "update_subject",
]
