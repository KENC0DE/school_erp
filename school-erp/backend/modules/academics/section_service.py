"""Sections (class groups) per level and academic year (ARCH §9.1)."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.models import User
from core.auth.principal import Principal
from core.db.soft_delete import get_including_deleted, restore, soft_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics import service as catalog
from modules.academics.models import AcademicYear, GradeLevel, Section
from modules.academics.section_schemas import (
    SectionCreate,
    SectionList,
    SectionOut,
    SectionUpdate,
)

MODULE = "academics"


def _section_state(section: Section) -> dict[str, Any]:
    return {
        "year_id": str(section.year_id),
        "level_id": str(section.level_id),
        "code": section.code,
        "name": section.name,
        "name_am": section.name_am,
        "capacity": section.capacity,
        "homeroom_user_id": str(section.homeroom_user_id) if section.homeroom_user_id else None,
        "is_active": section.is_active,
        "row_version": section.row_version,
        "deleted": section.deleted_at is not None,
    }


def _section_out(
    section: Section, year: AcademicYear, level: GradeLevel, homeroom: User | None
) -> SectionOut:
    return SectionOut(
        id=str(section.id),
        year_id=str(section.year_id),
        year_code=year.code,
        level_id=str(section.level_id),
        level_code=level.code,
        level_name=level.name,
        code=section.code,
        name=section.name,
        name_am=section.name_am,
        capacity=section.capacity,
        homeroom_user_id=str(section.homeroom_user_id) if section.homeroom_user_id else None,
        homeroom_name=homeroom.display_name if homeroom is not None else None,
        is_active=section.is_active,
        row_version=section.row_version,
    )


def _select_sections():
    return (
        select(Section, AcademicYear, GradeLevel, User)
        .join(AcademicYear, AcademicYear.id == Section.year_id)
        .join(GradeLevel, GradeLevel.id == Section.level_id)
        .outerjoin(User, User.id == Section.homeroom_user_id)
    )


async def _live_year(session: AsyncSession, year_id: uuid.UUID) -> AcademicYear:
    year = (
        await session.execute(select(AcademicYear).where(AcademicYear.id == year_id))
    ).scalar_one_or_none()
    if year is None:
        raise NotFound(
            "The academic year does not exist",
            message_key="error.academics.year_not_found",
        )
    return year


async def _live_section(
    session: AsyncSession, section_id: uuid.UUID
) -> tuple[Section, AcademicYear, GradeLevel, User | None]:
    row = (await session.execute(_select_sections().where(Section.id == section_id))).first()
    if row is None:
        raise NotFound(
            "The section does not exist",
            message_key="error.academics.section_not_found",
        )
    return row[0], row[1], row[2], row[3]


async def _homeroom_user(session: AsyncSession, user_id: uuid.UUID | None) -> User | None:
    if user_id is None:
        return None
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise ValidationFailed(
            "The homeroom teacher must be an active user",
            message_key="error.academics.homeroom_invalid",
            details={"user_id": str(user_id)},
        )
    return user


async def _assert_code_free(
    session: AsyncSession,
    year_id: uuid.UUID,
    level_id: uuid.UUID,
    code: str,
    *,
    current_id: uuid.UUID | None = None,
) -> None:
    stmt = select(Section.id).where(
        Section.year_id == year_id,
        Section.level_id == level_id,
        Section.code == code,
    )
    if current_id is not None:
        stmt = stmt.where(Section.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "A section with that code already exists for this level and year",
            message_key="error.academics.section_code_taken",
            details={"code": code},
        )


def _assert_year_editable(year: AcademicYear) -> None:
    if year.status == "closed":
        raise Conflict(
            "A closed academic year cannot be edited",
            message_key="error.academics.year_closed",
        )


async def list_sections(
    session: AsyncSession,
    *,
    year_id: uuid.UUID | None = None,
    level_id: uuid.UUID | None = None,
    include_inactive: bool = False,
    all_scope: bool = False,
) -> SectionList:
    stmt = _select_sections()
    if year_id is not None:
        stmt = stmt.where(Section.year_id == year_id)
    if level_id is not None:
        stmt = stmt.where(Section.level_id == level_id)
    if not include_inactive:
        stmt = stmt.where(Section.is_active.is_(True))
    if not all_scope:
        first, last = await catalog.academic_scope(session)
        stmt = stmt.where(GradeLevel.scope_level.between(first, last))
    rows = (
        await session.execute(
            stmt.order_by(
                AcademicYear.start_date.desc(),
                GradeLevel.sort_order,
                Section.code,
            )
        )
    ).all()
    items = [_section_out(row[0], row[1], row[2], row[3]) for row in rows]
    return SectionList(items=items, total=len(items))


async def get_section(session: AsyncSession, section_id: uuid.UUID, *, all_scope: bool = False) -> SectionOut:
    section, year, level, homeroom = await _live_section(session, section_id)
    if not all_scope:
        await catalog.scoped_level(session, level.id)
    return _section_out(section, year, level, homeroom)


async def create_section(
    session: AsyncSession,
    principal: Principal,
    data: SectionCreate,
    *,
    via: str = "api",
) -> SectionOut:
    year = await _live_year(session, data.year_id)
    _assert_year_editable(year)
    level = await catalog.scoped_level(session, data.level_id)
    if not level.is_active:
        raise ValidationFailed(
            "An inactive grade level cannot receive sections",
            message_key="error.academics.level_inactive",
        )
    homeroom = await _homeroom_user(session, data.homeroom_user_id)
    await _assert_code_free(session, year.id, level.id, data.code)
    section = Section(
        year_id=year.id,
        level_id=level.id,
        code=data.code,
        name=data.name,
        name_am=data.name_am,
        capacity=data.capacity,
        homeroom_user_id=homeroom.id if homeroom is not None else None,
        is_active=data.is_active,
    )
    session.add(section)
    await session.flush()
    await record(
        session,
        action="academics.sections.create",
        module=MODULE,
        entity_type="academic_section",
        entity_id=str(section.id),
        after=_section_state(section),
        actor=principal,
        via=via,
    )
    return _section_out(section, year, level, homeroom)


async def update_section(
    session: AsyncSession,
    principal: Principal,
    section_id: uuid.UUID,
    data: SectionUpdate,
    *,
    via: str = "api",
    reason: str | None = None,
) -> SectionOut:
    section, year, level, homeroom = await _live_section(session, section_id)
    _assert_year_editable(year)
    before = _section_state(section)
    ensure_row_version(section, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    changes: dict[str, Any] = {}
    if "code" in payload and payload["code"] != section.code:
        await _assert_code_free(
            session,
            section.year_id,
            section.level_id,
            payload["code"],
            current_id=section.id,
        )
    if "homeroom_user_id" in payload:
        new_homeroom = await _homeroom_user(
            session,
            uuid.UUID(str(payload["homeroom_user_id"])) if payload["homeroom_user_id"] else None,
        )
        if new_homeroom is None and homeroom is not None:
            changes["homeroom_user_id"] = None
            homeroom = None
        elif new_homeroom is not None and (homeroom is None or new_homeroom.id != homeroom.id):
            changes["homeroom_user_id"] = str(new_homeroom.id)
            homeroom = new_homeroom
    for key in ("code", "name", "name_am", "capacity", "is_active"):
        if key not in payload:
            continue
        value = payload[key]
        if value is None and key not in ("name", "name_am"):
            continue
        if getattr(section, key) != value:
            setattr(section, key, value)
            changes[key] = value
    if changes:
        section.row_version = (section.row_version or 0) + 1
    await session.flush()
    if changes:
        await record(
            session,
            action="academics.sections.update",
            module=MODULE,
            entity_type="academic_section",
            entity_id=str(section.id),
            before=before,
            after=_section_state(section),
            actor=principal,
            reason=reason,
            via=via,
        )
    return _section_out(section, year, level, homeroom)


async def delete_section(
    session: AsyncSession,
    principal: Principal,
    section_id: uuid.UUID,
    *,
    row_version: int | None = None,
    reason: str | None = None,
    via: str = "api",
) -> SectionOut:
    section, year, level, homeroom = await _live_section(session, section_id)
    _assert_year_editable(year)
    if row_version is not None:
        ensure_row_version(section, row_version, current_state=_section_state(section))
    await soft_delete(
        session,
        section,
        action="academics.sections.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="academic_section",
    )
    await session.flush()
    return _section_out(section, year, level, homeroom)


async def restore_section(
    session: AsyncSession,
    principal: Principal,
    section_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> SectionOut:
    section = await get_including_deleted(session, Section, section_id)
    if section is None:
        raise NotFound(
            "The section does not exist",
            message_key="error.academics.section_not_found",
        )
    year = await _live_year(session, section.year_id)
    _assert_year_editable(year)
    await _assert_code_free(
        session,
        section.year_id,
        section.level_id,
        section.code,
        current_id=section.id,
    )
    await restore(
        session,
        section,
        action="academics.sections.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="academic_section",
    )
    await session.flush()
    _, live_year, level, homeroom = await _live_section(session, section.id)
    return _section_out(section, live_year, level, homeroom)


__all__ = [
    "create_section",
    "delete_section",
    "get_section",
    "list_sections",
    "restore_section",
    "update_section",
]
