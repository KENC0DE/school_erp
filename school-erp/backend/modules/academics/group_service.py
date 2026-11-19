"""Subject groups such as electives or streams (ARCH §9.1)."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import get_including_deleted, restore, soft_delete
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import Subject, SubjectGroup, SubjectGroupMember
from modules.academics.subject_schemas import (
    SubjectGroupCreate,
    SubjectGroupList,
    SubjectGroupOut,
    SubjectGroupUpdate,
    SubjectOut,
)

MODULE = "academics"


def _group_state(group: SubjectGroup, members: list[Subject]) -> dict[str, Any]:
    return {
        "code": group.code,
        "name": group.name,
        "name_am": group.name_am,
        "sort_order": group.sort_order,
        "is_active": group.is_active,
        "subjects": [subject.code for subject in members],
        "row_version": group.row_version,
        "deleted": group.deleted_at is not None,
    }


def _subject_out(subject: Subject) -> SubjectOut:
    return SubjectOut(
        id=str(subject.id),
        code=subject.code,
        name=subject.name,
        name_am=subject.name_am,
        sort_order=subject.sort_order,
        is_active=subject.is_active,
        row_version=subject.row_version,
    )


def _group_out(group: SubjectGroup, members: list[Subject]) -> SubjectGroupOut:
    return SubjectGroupOut(
        id=str(group.id),
        code=group.code,
        name=group.name,
        name_am=group.name_am,
        sort_order=group.sort_order,
        is_active=group.is_active,
        subjects=[_subject_out(subject) for subject in members],
        row_version=group.row_version,
    )


async def _live_group(session: AsyncSession, group_id: uuid.UUID) -> SubjectGroup:
    group = (
        await session.execute(select(SubjectGroup).where(SubjectGroup.id == group_id))
    ).scalar_one_or_none()
    if group is None:
        raise NotFound(
            "The subject group does not exist",
            message_key="error.academics.subject_group_not_found",
        )
    return group


async def _assert_code_free(session: AsyncSession, code: str, *, current_id: uuid.UUID | None = None) -> None:
    stmt = select(SubjectGroup.id).where(SubjectGroup.code == code)
    if current_id is not None:
        stmt = stmt.where(SubjectGroup.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "A subject group with that code already exists",
            message_key="error.academics.subject_group_code_taken",
            details={"code": code},
        )


async def _next_order(session: AsyncSession) -> int:
    current = (await session.execute(select(func.max(SubjectGroup.sort_order)))).scalar_one_or_none()
    return int(current) + 1 if current is not None else 0


async def _members(session: AsyncSession, group_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Subject]]:
    grouped: dict[uuid.UUID, list[Subject]] = {group_id: [] for group_id in group_ids}
    if not group_ids:
        return grouped
    rows = (
        await session.execute(
            select(SubjectGroupMember.group_id, Subject)
            .join(Subject, Subject.id == SubjectGroupMember.subject_id)
            .where(SubjectGroupMember.group_id.in_(group_ids))
            .order_by(Subject.sort_order, Subject.name)
        )
    ).all()
    for group_id, subject in rows:
        grouped.setdefault(group_id, []).append(subject)
    return grouped


async def _validated_subjects(session: AsyncSession, subject_ids: list[uuid.UUID]) -> list[Subject]:
    unique_ids = list(dict.fromkeys(subject_ids))
    if not unique_ids:
        return []
    rows = (await session.execute(select(Subject).where(Subject.id.in_(unique_ids)))).scalars().all()
    by_id = {subject.id: subject for subject in rows}
    missing = [str(subject_id) for subject_id in unique_ids if subject_id not in by_id]
    if missing:
        raise ValidationFailed(
            "One or more selected subjects do not exist",
            message_key="error.academics.subject_missing",
            details={"subject_ids": missing},
        )
    return [by_id[subject_id] for subject_id in unique_ids]


async def _replace_members(session: AsyncSession, group_id: uuid.UUID, subject_ids: list[uuid.UUID]) -> None:
    await session.execute(delete(SubjectGroupMember).where(SubjectGroupMember.group_id == group_id))
    for subject_id in dict.fromkeys(subject_ids):
        session.add(SubjectGroupMember(group_id=group_id, subject_id=subject_id))
    await session.flush()


async def list_groups(
    session: AsyncSession,
    *,
    include_inactive: bool = False,
) -> SubjectGroupList:
    stmt = select(SubjectGroup)
    if not include_inactive:
        stmt = stmt.where(SubjectGroup.is_active.is_(True))
    groups = (
        (await session.execute(stmt.order_by(SubjectGroup.sort_order, SubjectGroup.name))).scalars().all()
    )
    members = await _members(session, [group.id for group in groups])
    items = [_group_out(group, members.get(group.id, [])) for group in groups]
    return SubjectGroupList(items=items, total=len(items))


async def get_group(session: AsyncSession, group_id: uuid.UUID) -> SubjectGroupOut:
    group = await _live_group(session, group_id)
    members = (await _members(session, [group.id])).get(group.id, [])
    return _group_out(group, members)


async def create_group(
    session: AsyncSession,
    principal: Principal,
    data: SubjectGroupCreate,
    *,
    via: str = "api",
) -> SubjectGroupOut:
    await _assert_code_free(session, data.code)
    members = await _validated_subjects(session, data.subject_ids)
    group = SubjectGroup(
        code=data.code,
        name=data.name,
        name_am=data.name_am,
        sort_order=data.sort_order if data.sort_order is not None else await _next_order(session),
        is_active=data.is_active,
    )
    session.add(group)
    await session.flush()
    await _replace_members(session, group.id, [subject.id for subject in members])
    members = await _validated_subjects(session, data.subject_ids)
    await record(
        session,
        action="academics.subject_groups.create",
        module=MODULE,
        entity_type="subject_group",
        entity_id=str(group.id),
        after=_group_state(group, members),
        actor=principal,
        via=via,
    )
    return _group_out(group, members)


async def update_group(
    session: AsyncSession,
    principal: Principal,
    group_id: uuid.UUID,
    data: SubjectGroupUpdate,
    *,
    via: str = "api",
    reason: str | None = None,
) -> SubjectGroupOut:
    group = await _live_group(session, group_id)
    members = (await _members(session, [group.id])).get(group.id, [])
    before = _group_state(group, members)
    ensure_row_version(group, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    changes: dict[str, Any] = {}
    for key in ("name", "name_am", "sort_order", "is_active"):
        if key not in payload:
            continue
        value = payload[key]
        if value is None and key != "name_am":
            continue
        if getattr(group, key) != value:
            setattr(group, key, value)
            changes[key] = value
    new_subject_ids = payload.get("subject_ids")
    if new_subject_ids is not None:
        await _replace_members(session, group.id, [uuid.UUID(str(item)) for item in new_subject_ids])
        changes["subject_ids"] = [str(item) for item in new_subject_ids]
    if changes:
        group.row_version = (group.row_version or 0) + 1
    await session.flush()
    members = (await _members(session, [group.id])).get(group.id, [])
    if changes:
        await record(
            session,
            action="academics.subject_groups.update",
            module=MODULE,
            entity_type="subject_group",
            entity_id=str(group.id),
            before=before,
            after=_group_state(group, members),
            actor=principal,
            reason=reason,
            via=via,
        )
    return _group_out(group, members)


async def delete_group(
    session: AsyncSession,
    principal: Principal,
    group_id: uuid.UUID,
    *,
    row_version: int | None = None,
    reason: str | None = None,
    via: str = "api",
) -> SubjectGroupOut:
    group = await _live_group(session, group_id)
    members = (await _members(session, [group.id])).get(group.id, [])
    if row_version is not None:
        ensure_row_version(group, row_version, current_state=_group_state(group, members))
    await soft_delete(
        session,
        group,
        action="academics.subject_groups.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="subject_group",
    )
    await session.flush()
    return _group_out(group, members)


async def restore_group(
    session: AsyncSession,
    principal: Principal,
    group_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> SubjectGroupOut:
    group = await get_including_deleted(session, SubjectGroup, group_id)
    if group is None:
        raise NotFound(
            "The subject group does not exist",
            message_key="error.academics.subject_group_not_found",
        )
    await _assert_code_free(session, group.code)
    await restore(
        session,
        group,
        action="academics.subject_groups.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="subject_group",
    )
    await session.flush()
    members = (await _members(session, [group.id])).get(group.id, [])
    return _group_out(group, members)


__all__ = [
    "create_group",
    "delete_group",
    "get_group",
    "list_groups",
    "restore_group",
    "update_group",
]
