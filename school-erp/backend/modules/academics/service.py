"""Audited business logic for the academic structure catalog (ARCH §9.1)."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import get_including_deleted, restore, soft_delete
from core.settings.core_schema import CoreSettings
from core.settings.service import effective_map, set_setting
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import GradeLevel, Stage, StageLevel
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

MODULE = "academics"


def _level_state(level: GradeLevel) -> dict[str, Any]:
    return {
        "code": level.code,
        "name": level.name,
        "name_am": level.name_am,
        "scope_level": level.scope_level,
        "sort_order": level.sort_order,
        "is_active": level.is_active,
        "is_starter": level.is_starter,
        "is_verified": level.is_verified,
        "row_version": level.row_version,
        "deleted": level.deleted_at is not None,
    }


def _stage_state(stage: Stage, members: list[GradeLevel]) -> dict[str, Any]:
    return {
        "code": stage.code,
        "name": stage.name,
        "name_am": stage.name_am,
        "sort_order": stage.sort_order,
        "is_active": stage.is_active,
        "is_starter": stage.is_starter,
        "is_verified": stage.is_verified,
        "level_codes": [level.code for level in members],
        "row_version": stage.row_version,
        "deleted": stage.deleted_at is not None,
    }


def _in_scope(level: GradeLevel, first: int, last: int) -> bool:
    return first <= level.scope_level <= last


def _level_out(level: GradeLevel, first: int, last: int) -> LevelOut:
    return LevelOut(
        id=str(level.id),
        code=level.code,
        name=level.name,
        name_am=level.name_am,
        scope_level=level.scope_level,
        sort_order=level.sort_order,
        is_active=level.is_active,
        is_starter=level.is_starter,
        is_verified=level.is_verified,
        in_scope=_in_scope(level, first, last),
        row_version=level.row_version,
    )


async def academic_scope(session: AsyncSession) -> tuple[int, int]:
    effective = await effective_map(session, "core", CoreSettings)
    return (
        int(effective["academic_scope.first_level"].value),
        int(effective["academic_scope.last_level"].value),
    )


async def scope_view(session: AsyncSession) -> ScopeOut:
    first, last = await academic_scope(session)
    active_levels = (
        (await session.execute(select(GradeLevel).where(GradeLevel.is_active.is_(True)))).scalars().all()
    )
    level_count = sum(1 for level in active_levels if _in_scope(level, first, last))
    level_options = sorted({level.scope_level for level in active_levels})
    stage_count = int(
        (
            await session.execute(
                select(func.count(func.distinct(Stage.id)))
                .select_from(Stage)
                .join(StageLevel, StageLevel.stage_id == Stage.id)
                .join(GradeLevel, GradeLevel.id == StageLevel.level_id)
                .where(
                    Stage.is_active.is_(True),
                    GradeLevel.is_active.is_(True),
                    GradeLevel.scope_level.between(first, last),
                )
            )
        ).scalar_one()
    )
    return ScopeOut(
        first_level=first,
        last_level=last,
        level_count=level_count,
        stage_count=stage_count,
        scope_levels=level_options,
    )


async def list_levels(
    session: AsyncSession,
    *,
    all_scope: bool = False,
    include_inactive: bool = False,
) -> LevelList:
    first, last = await academic_scope(session)
    stmt = select(GradeLevel)
    if not include_inactive:
        stmt = stmt.where(GradeLevel.is_active.is_(True))
    if not all_scope:
        stmt = stmt.where(GradeLevel.scope_level.between(first, last))
    levels = (await session.execute(stmt.order_by(GradeLevel.sort_order, GradeLevel.name))).scalars().all()
    scope = await scope_view(session)
    items = [_level_out(level, first, last) for level in levels]
    return LevelList(items=items, total=len(items), scope=scope)


async def get_level(
    session: AsyncSession,
    level_id: uuid.UUID,
    *,
    all_scope: bool = False,
) -> LevelOut:
    level = await _live_level(session, level_id)
    first, last = await academic_scope(session)
    if not all_scope and not _in_scope(level, first, last):
        # Out-of-scope levels do not exist for ordinary readers or dropdowns.
        raise NotFound(
            "That grade level is outside the school's scope",
            message_key="error.academics.level_out_of_scope",
        )
    return _level_out(level, first, last)


async def scoped_level(session: AsyncSession, level_id: uuid.UUID) -> GradeLevel:
    """Return a live level that belongs to the school's current scope."""
    level = await _live_level(session, level_id)
    first, last = await academic_scope(session)
    if not _in_scope(level, first, last):
        raise NotFound(
            "That grade level is outside the school's scope",
            message_key="error.academics.level_out_of_scope",
        )
    return level


async def _live_level(session: AsyncSession, level_id: uuid.UUID) -> GradeLevel:
    level = (await session.execute(select(GradeLevel).where(GradeLevel.id == level_id))).scalar_one_or_none()
    if level is None:
        raise NotFound(
            "The grade level does not exist",
            message_key="error.academics.level_not_found",
        )
    return level


async def _assert_level_code_free(
    session: AsyncSession, code: str, *, current_id: uuid.UUID | None = None
) -> None:
    stmt = select(GradeLevel.id).where(GradeLevel.code == code)
    if current_id is not None:
        stmt = stmt.where(GradeLevel.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "A grade level with that code already exists",
            message_key="error.academics.level_code_taken",
            details={"code": code},
        )


async def _next_level_order(session: AsyncSession) -> int:
    current = (await session.execute(select(func.max(GradeLevel.sort_order)))).scalar_one_or_none()
    return int(current) + 1 if current is not None else 0


async def create_level(
    session: AsyncSession,
    principal: Principal,
    data: LevelCreate,
    *,
    via: str = "api",
) -> LevelOut:
    await _assert_level_code_free(session, data.code)
    level = GradeLevel(
        code=data.code,
        name=data.name,
        name_am=data.name_am,
        scope_level=data.scope_level,
        sort_order=data.sort_order if data.sort_order is not None else await _next_level_order(session),
        is_active=data.is_active,
        is_starter=False,
        is_verified=data.is_verified,
    )
    session.add(level)
    await session.flush()
    await record(
        session,
        action="academics.levels.create",
        module=MODULE,
        entity_type="academic_level",
        entity_id=str(level.id),
        after=_level_state(level),
        actor=principal,
        via=via,
    )
    first, last = await academic_scope(session)
    return _level_out(level, first, last)


async def update_level(
    session: AsyncSession,
    principal: Principal,
    level_id: uuid.UUID,
    data: LevelUpdate,
    *,
    via: str = "api",
) -> LevelOut:
    level = await _live_level(session, level_id)
    before = _level_state(level)
    ensure_row_version(level, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    changes: dict[str, Any] = {}
    for key in (
        "name",
        "name_am",
        "scope_level",
        "sort_order",
        "is_active",
        "is_verified",
    ):
        if key not in payload:
            continue
        value = payload[key]
        if value is None and key != "name_am":
            continue
        if getattr(level, key) != value:
            setattr(level, key, value)
            changes[key] = value
    if changes:
        level.row_version = (level.row_version or 0) + 1
    await session.flush()
    after = _level_state(level)
    if changes:
        await record(
            session,
            action="academics.levels.update",
            module=MODULE,
            entity_type="academic_level",
            entity_id=str(level.id),
            before=before,
            after=after,
            actor=principal,
            via=via,
        )
    first, last = await academic_scope(session)
    return _level_out(level, first, last)


async def delete_level(
    session: AsyncSession,
    principal: Principal,
    level_id: uuid.UUID,
    *,
    row_version: int | None = None,
    reason: str | None = None,
    via: str = "api",
) -> LevelOut:
    level = await _live_level(session, level_id)
    if row_version is not None:
        ensure_row_version(level, row_version, current_state=_level_state(level))
    changed = await soft_delete(
        session,
        level,
        action="academics.levels.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="academic_level",
    )
    if changed:
        await session.flush()
    first, last = await academic_scope(session)
    return _level_out(level, first, last)


async def restore_level(
    session: AsyncSession,
    principal: Principal,
    level_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> LevelOut:
    level = await get_including_deleted(session, GradeLevel, level_id)
    if level is None:
        raise NotFound(
            "The grade level does not exist",
            message_key="error.academics.level_not_found",
        )
    await _assert_level_code_free(session, level.code, current_id=level.id)
    changed = await restore(
        session,
        level,
        action="academics.levels.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="academic_level",
    )
    if changed:
        await session.flush()
    first, last = await academic_scope(session)
    return _level_out(level, first, last)


async def _live_stage(session: AsyncSession, stage_id: uuid.UUID) -> Stage:
    stage = (await session.execute(select(Stage).where(Stage.id == stage_id))).scalar_one_or_none()
    if stage is None:
        raise NotFound(
            "The stage does not exist",
            message_key="error.academics.stage_not_found",
        )
    return stage


async def _assert_stage_code_free(session: AsyncSession, code: str) -> None:
    if (await session.execute(select(Stage.id).where(Stage.code == code))).scalar_one_or_none() is not None:
        raise Conflict(
            "A stage with that code already exists",
            message_key="error.academics.stage_code_taken",
            details={"code": code},
        )


async def _next_stage_order(session: AsyncSession) -> int:
    current = (await session.execute(select(func.max(Stage.sort_order)))).scalar_one_or_none()
    return int(current) + 1 if current is not None else 0


async def _members_by_stage(
    session: AsyncSession,
    stage_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[GradeLevel]]:
    grouped: dict[uuid.UUID, list[GradeLevel]] = {stage_id: [] for stage_id in stage_ids}
    if not stage_ids:
        return grouped
    rows = (
        await session.execute(
            select(StageLevel.stage_id, GradeLevel)
            .join(GradeLevel, GradeLevel.id == StageLevel.level_id)
            .where(StageLevel.stage_id.in_(stage_ids))
            .order_by(GradeLevel.sort_order, GradeLevel.name)
        )
    ).all()
    for stage_id, level in rows:
        grouped.setdefault(stage_id, []).append(level)
    return grouped


def _stage_out(
    stage: Stage,
    members: list[GradeLevel],
    first: int,
    last: int,
    *,
    all_scope: bool,
    include_inactive: bool,
) -> StageOut:
    visible = [
        level
        for level in members
        if (all_scope or _in_scope(level, first, last)) and (include_inactive or level.is_active)
    ]
    return StageOut(
        id=str(stage.id),
        code=stage.code,
        name=stage.name,
        name_am=stage.name_am,
        sort_order=stage.sort_order,
        is_active=stage.is_active,
        is_starter=stage.is_starter,
        is_verified=stage.is_verified,
        in_scope=any(_in_scope(level, first, last) and level.is_active for level in members),
        levels=[_level_out(level, first, last) for level in visible],
        row_version=stage.row_version,
    )


async def list_stages(
    session: AsyncSession,
    *,
    all_scope: bool = False,
    include_inactive: bool = False,
) -> StageList:
    first, last = await academic_scope(session)
    stmt = select(Stage)
    if not include_inactive:
        stmt = stmt.where(Stage.is_active.is_(True))
    stages = (await session.execute(stmt.order_by(Stage.sort_order, Stage.name))).scalars().all()
    members = await _members_by_stage(session, [stage.id for stage in stages])
    items: list[StageOut] = []
    for stage in stages:
        view = _stage_out(
            stage,
            members.get(stage.id, []),
            first,
            last,
            all_scope=all_scope,
            include_inactive=include_inactive,
        )
        # Outside management mode a stage with no in-scope level is not offered.
        if not all_scope and not view.levels:
            continue
        items.append(view)
    scope = await scope_view(session)
    return StageList(items=items, total=len(items), scope=scope)


async def get_stage(
    session: AsyncSession,
    stage_id: uuid.UUID,
    *,
    all_scope: bool = False,
) -> StageOut:
    stage = await _live_stage(session, stage_id)
    members = (await _members_by_stage(session, [stage.id])).get(stage.id, [])
    first, last = await academic_scope(session)
    view = _stage_out(
        stage,
        members,
        first,
        last,
        all_scope=all_scope,
        include_inactive=all_scope,
    )
    if not all_scope and not view.levels:
        raise NotFound(
            "That stage has no levels inside the school's scope",
            message_key="error.academics.stage_out_of_scope",
        )
    return view


async def _validated_level_ids(
    session: AsyncSession,
    level_ids: list[uuid.UUID],
) -> list[GradeLevel]:
    unique_ids = list(dict.fromkeys(level_ids))
    if not unique_ids:
        raise ValidationFailed(
            "A stage needs at least one grade level",
            message_key="error.academics.stage_empty",
        )
    rows = (await session.execute(select(GradeLevel).where(GradeLevel.id.in_(unique_ids)))).scalars().all()
    by_id = {row.id: row for row in rows}
    missing = [str(level_id) for level_id in unique_ids if level_id not in by_id]
    if missing:
        raise ValidationFailed(
            "One or more selected grade levels do not exist",
            message_key="error.academics.level_missing",
            details={"level_ids": missing},
        )
    return [by_id[level_id] for level_id in unique_ids]


async def _replace_members(session: AsyncSession, stage_id: uuid.UUID, level_ids: list[uuid.UUID]) -> None:
    from sqlalchemy import delete

    await session.execute(delete(StageLevel).where(StageLevel.stage_id == stage_id))
    for level_id in dict.fromkeys(level_ids):
        session.add(StageLevel(stage_id=stage_id, level_id=level_id))
    await session.flush()


async def create_stage(
    session: AsyncSession,
    principal: Principal,
    data: StageCreate,
    *,
    via: str = "api",
) -> StageOut:
    await _assert_stage_code_free(session, data.code)
    members = await _validated_level_ids(session, data.level_ids)
    stage = Stage(
        code=data.code,
        name=data.name,
        name_am=data.name_am,
        sort_order=data.sort_order if data.sort_order is not None else await _next_stage_order(session),
        is_active=data.is_active,
        is_starter=False,
        is_verified=data.is_verified,
    )
    session.add(stage)
    await session.flush()
    for level in members:
        session.add(StageLevel(stage_id=stage.id, level_id=level.id))
    await session.flush()
    await record(
        session,
        action="academics.stages.create",
        module=MODULE,
        entity_type="academic_stage",
        entity_id=str(stage.id),
        after=_stage_state(
            stage,
            sorted(members, key=lambda item: (item.sort_order, item.name)),
        ),
        actor=principal,
        via=via,
    )
    return await get_stage(session, stage.id, all_scope=True)


async def update_stage(
    session: AsyncSession,
    principal: Principal,
    stage_id: uuid.UUID,
    data: StageUpdate,
    *,
    via: str = "api",
) -> StageOut:
    stage = await _live_stage(session, stage_id)
    members = (await _members_by_stage(session, [stage.id])).get(stage.id, [])
    before = _stage_state(stage, sorted(members, key=lambda item: (item.sort_order, item.name)))
    ensure_row_version(stage, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    changes: dict[str, Any] = {}
    for key in ("name", "name_am", "sort_order", "is_active", "is_verified"):
        if key not in payload:
            continue
        value = payload[key]
        if value is None and key != "name_am":
            continue
        if getattr(stage, key) != value:
            setattr(stage, key, value)
            changes[key] = value
    new_level_ids = payload.get("level_ids")
    if new_level_ids is not None:
        members = await _validated_level_ids(session, [uuid.UUID(str(item)) for item in new_level_ids])
        await _replace_members(session, stage.id, [level.id for level in members])
        changes["level_ids"] = [str(level.id) for level in members]
    if changes:
        stage.row_version = (stage.row_version or 0) + 1
    await session.flush()
    members = (await _members_by_stage(session, [stage.id])).get(stage.id, [])
    if changes:
        await record(
            session,
            action="academics.stages.update",
            module=MODULE,
            entity_type="academic_stage",
            entity_id=str(stage.id),
            before=before,
            after=_stage_state(stage, sorted(members, key=lambda item: (item.sort_order, item.name))),
            actor=principal,
            via=via,
        )
    return await get_stage(session, stage.id, all_scope=True)


async def delete_stage(
    session: AsyncSession,
    principal: Principal,
    stage_id: uuid.UUID,
    *,
    row_version: int | None = None,
    reason: str | None = None,
    via: str = "api",
) -> StageOut:
    stage = await _live_stage(session, stage_id)
    members = (await _members_by_stage(session, [stage.id])).get(stage.id, [])
    if row_version is not None:
        ensure_row_version(stage, row_version, current_state=_stage_state(stage, members))
    await soft_delete(
        session,
        stage,
        action="academics.stages.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="academic_stage",
    )
    await session.flush()
    first, last = await academic_scope(session)
    return _stage_out(
        stage,
        members,
        first,
        last,
        all_scope=True,
        include_inactive=True,
    )


async def restore_stage(
    session: AsyncSession,
    principal: Principal,
    stage_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> StageOut:
    stage = await get_including_deleted(session, Stage, stage_id)
    if stage is None:
        raise NotFound(
            "The stage does not exist",
            message_key="error.academics.stage_not_found",
        )
    await _assert_stage_code_free(session, stage.code)
    await restore(
        session,
        stage,
        action="academics.stages.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="academic_stage",
    )
    await session.flush()
    return await get_stage(session, stage.id, all_scope=True)


async def update_scope(
    session: AsyncSession,
    principal: Principal,
    data: ScopeUpdate,
    *,
    via: str = "api",
) -> ScopeOut:
    if data.first_level > data.last_level:
        raise ValidationFailed(
            "The first grade level cannot be above the last",
            message_key="error.academics.scope_order",
            details={"first_level": data.first_level, "last_level": data.last_level},
        )
    available = int(
        (
            await session.execute(
                select(func.count())
                .select_from(GradeLevel)
                .where(
                    GradeLevel.is_active.is_(True),
                    GradeLevel.scope_level.between(data.first_level, data.last_level),
                )
            )
        ).scalar_one()
    )
    if available < 1:
        raise ValidationFailed(
            "No active grade level exists inside that scope",
            message_key="error.academics.scope_empty",
            details={"first_level": data.first_level, "last_level": data.last_level},
        )

    current_first, current_last = await academic_scope(session)
    if (current_first, current_last) == (data.first_level, data.last_level):
        return await scope_view(session)

    before = {"first_level": current_first, "last_level": current_last}
    # Keep the model valid after every single write. Expanding downwards sets
    # first_level first; moving the whole range up sets last_level first.
    if data.first_level > current_last:
        order = (
            ("academic_scope.last_level", data.last_level),
            ("academic_scope.first_level", data.first_level),
        )
    else:
        order = (
            ("academic_scope.first_level", data.first_level),
            ("academic_scope.last_level", data.last_level),
        )
    for key, value in order:
        await set_setting(session, "core", CoreSettings, key, value, actor=principal)
    after = {"first_level": data.first_level, "last_level": data.last_level}
    await record(
        session,
        action="academics.scope.update",
        module=MODULE,
        entity_type="academic_scope",
        entity_id="academic_scope",
        before=before,
        after=after,
        actor=principal,
        reason=data.reason,
        via=via,
    )
    await session.flush()
    return await scope_view(session)


__all__ = [
    "academic_scope",
    "create_level",
    "create_stage",
    "delete_level",
    "delete_stage",
    "get_level",
    "get_stage",
    "list_levels",
    "list_stages",
    "restore_level",
    "restore_stage",
    "scope_view",
    "scoped_level",
    "update_level",
    "update_scope",
    "update_stage",
]
