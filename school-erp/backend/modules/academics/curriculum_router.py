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

from modules.academics.curriculum_actions import (
    apply_profile,
    create_profile,
    delete_profile,
    duplicate_profile,
    get_profile,
    list_profiles,
    replace_level_subjects,
    restore_profile,
    update_profile,
)
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

curriculum_router = APIRouter(tags=["academics"])


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


@curriculum_router.get("/curriculum-profiles", response_model=CurriculumProfileList)
async def get_profile_list(
    include_inactive: bool = Query(False),
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> CurriculumProfileList:
    _guard_hidden(principal, include_inactive)
    return await list_profiles(_context(principal, session), {"include_inactive": include_inactive})


@curriculum_router.get("/curriculum-profiles/{profile_id}", response_model=CurriculumProfileOut)
async def get_profile_detail(
    profile_id: uuid.UUID,
    principal: Principal = Depends(require("academics.view")),
    session: AsyncSession = Depends(get_session),
) -> CurriculumProfileOut:
    return await get_profile(_context(principal, session), {"profile_id": str(profile_id)})


@curriculum_router.post("/curriculum-profiles", response_model=CurriculumProfileOut, status_code=201)
async def post_profile(
    payload: CurriculumProfileCreate,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> CurriculumProfileOut:
    return await create_profile(_context(principal, session), payload.model_dump(mode="json"))


@curriculum_router.patch("/curriculum-profiles/{profile_id}", response_model=CurriculumProfileOut)
async def patch_profile(
    profile_id: uuid.UUID,
    payload: CurriculumProfileUpdate,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> CurriculumProfileOut:
    body = {
        **payload.model_dump(mode="json", exclude_unset=True),
        "profile_id": str(profile_id),
        "reason": reason,
    }
    return await update_profile(_context(principal, session), body)


@curriculum_router.delete("/curriculum-profiles/{profile_id}", response_model=CurriculumProfileOut)
async def delete_profile_route(
    profile_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> CurriculumProfileOut:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    body = {"profile_id": str(profile_id), "row_version": expected, "reason": reason}
    return await delete_profile(_context(principal, session), body)


@curriculum_router.post("/curriculum-profiles/{profile_id}/restore", response_model=CurriculumProfileOut)
async def restore_profile_route(
    profile_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> CurriculumProfileOut:
    body = {"profile_id": str(profile_id), "reason": reason}
    return await restore_profile(_context(principal, session), body)


@curriculum_router.post(
    "/curriculum-profiles/{profile_id}/duplicate",
    response_model=CurriculumProfileOut,
    status_code=201,
)
async def duplicate_profile_route(
    profile_id: uuid.UUID,
    payload: CurriculumProfileDuplicate,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> CurriculumProfileOut:
    body = {**payload.model_dump(mode="json"), "profile_id": str(profile_id)}
    return await duplicate_profile(_context(principal, session), body)


@curriculum_router.put(
    "/curriculum-profiles/{profile_id}/levels/{level_id}/subjects",
    response_model=CurriculumProfileOut,
)
async def put_profile_level_subjects(
    profile_id: uuid.UUID,
    level_id: uuid.UUID,
    payload: CurriculumLevelReplace,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> CurriculumProfileOut:
    body = {
        **payload.model_dump(mode="json"),
        "profile_id": str(profile_id),
        "level_id": str(level_id),
    }
    return await replace_level_subjects(_context(principal, session), body)


@curriculum_router.post(
    "/curriculum-profiles/{profile_id}/apply",
    response_model=CurriculumApplyOut,
)
async def apply_profile_route(
    profile_id: uuid.UUID,
    payload: CurriculumApply,
    principal: Principal = Depends(require("academics.manage")),
    session: AsyncSession = Depends(get_session),
) -> CurriculumApplyOut:
    body = {**payload.model_dump(mode="json"), "profile_id": str(profile_id)}
    return await apply_profile(_context(principal, session), body)
