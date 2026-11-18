from __future__ import annotations

import uuid

from app.errors import Forbidden
from app.logging import request_id_var
from core.actions.registry import ActionContext
from core.api.concurrency import parse_if_match
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.subject_actions import (
    create_group,
    create_subject,
    delete_group,
    delete_subject,
    get_group,
    get_level_subjects,
    get_subject,
    list_groups,
    list_subjects,
    replace_level_subjects,
    restore_group,
    restore_subject,
    update_group,
    update_subject,
)
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

subject_router = APIRouter(tags=["academics"])


def _context(principal: Principal, session: AsyncSession) -> ActionContext:
    return ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )


def _guard_hidden(principal: Principal, include_inactive: bool) -> None:
    if include_inactive and not principal.can("academics.manage"):
        raise Forbidden(
            "Managing the catalog requires academics.manage",
            details={"permission": "academics.manage"},
        )


@subject_router.get("/subjects", response_model=SubjectList)
async def get_subjects(
    include_inactive: bool = Query(False),
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> SubjectList:
    _guard_hidden(principal, include_inactive)
    return await list_subjects(_context(principal, session), {"include_inactive": include_inactive})


@subject_router.get("/subjects/{subject_id}", response_model=SubjectOut)
async def get_subject_detail(
    subject_id: uuid.UUID,
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> SubjectOut:
    return await get_subject(_context(principal, session), {"subject_id": str(subject_id)})


@subject_router.post("/subjects", response_model=SubjectOut, status_code=201)
async def post_subject(
    payload: SubjectCreate,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> SubjectOut:
    return await create_subject(_context(principal, session), payload.model_dump())


@subject_router.patch("/subjects/{subject_id}", response_model=SubjectOut)
async def patch_subject(
    subject_id: uuid.UUID,
    payload: SubjectUpdate,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> SubjectOut:
    body = {**payload.model_dump(exclude_unset=True), "subject_id": str(subject_id), "reason": reason}
    return await update_subject(_context(principal, session), body)


@subject_router.delete("/subjects/{subject_id}", response_model=SubjectOut)
async def delete_subject_route(
    subject_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> SubjectOut:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    body = {"subject_id": str(subject_id), "row_version": expected, "reason": reason}
    return await delete_subject(_context(principal, session), body)


@subject_router.post("/subjects/{subject_id}/restore", response_model=SubjectOut)
async def restore_subject_route(
    subject_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> SubjectOut:
    body = {"subject_id": str(subject_id), "reason": reason}
    return await restore_subject(_context(principal, session), body)


@subject_router.get("/levels/{level_id}/subjects", response_model=LevelSubjectsOut)
async def get_level_subject_list(
    level_id: uuid.UUID,
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> LevelSubjectsOut:
    return await get_level_subjects(_context(principal, session), {"level_id": str(level_id)})


@subject_router.put("/levels/{level_id}/subjects", response_model=LevelSubjectsOut)
async def put_level_subject_list(
    level_id: uuid.UUID,
    payload: LevelSubjectReplace,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> LevelSubjectsOut:
    body = {**payload.model_dump(mode="json"), "level_id": str(level_id)}
    return await replace_level_subjects(_context(principal, session), body)


@subject_router.get("/subject-groups", response_model=SubjectGroupList)
async def get_group_list(
    include_inactive: bool = Query(False),
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> SubjectGroupList:
    _guard_hidden(principal, include_inactive)
    return await list_groups(_context(principal, session), {"include_inactive": include_inactive})


@subject_router.get("/subject-groups/{group_id}", response_model=SubjectGroupOut)
async def get_group_detail(
    group_id: uuid.UUID,
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> SubjectGroupOut:
    return await get_group(_context(principal, session), {"group_id": str(group_id)})


@subject_router.post("/subject-groups", response_model=SubjectGroupOut, status_code=201)
async def post_group(
    payload: SubjectGroupCreate,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> SubjectGroupOut:
    return await create_group(_context(principal, session), payload.model_dump(mode="json"))


@subject_router.patch("/subject-groups/{group_id}", response_model=SubjectGroupOut)
async def patch_group(
    group_id: uuid.UUID,
    payload: SubjectGroupUpdate,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> SubjectGroupOut:
    body = {
        **payload.model_dump(mode="json", exclude_unset=True),
        "group_id": str(group_id),
        "reason": reason,
    }
    return await update_group(_context(principal, session), body)


@subject_router.delete("/subject-groups/{group_id}", response_model=SubjectGroupOut)
async def delete_group_route(
    group_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> SubjectGroupOut:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    body = {"group_id": str(group_id), "row_version": expected, "reason": reason}
    return await delete_group(_context(principal, session), body)


@subject_router.post("/subject-groups/{group_id}/restore", response_model=SubjectGroupOut)
async def restore_group_route(
    group_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> SubjectGroupOut:
    body = {"group_id": str(group_id), "reason": reason}
    return await restore_group(_context(principal, session), body)
