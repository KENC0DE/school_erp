"""Curriculum profiles: starter bundles, duplication, editing and applying."""

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

from modules.academics import service as catalog
from modules.academics.curriculum_schemas import (
    CurriculumApply,
    CurriculumApplyOut,
    CurriculumLevelOut,
    CurriculumLevelReplace,
    CurriculumProfileCreate,
    CurriculumProfileDuplicate,
    CurriculumProfileList,
    CurriculumProfileOut,
    CurriculumProfileUpdate,
)
from modules.academics.models import (
    AcademicYear,
    CurriculumLevelSubject,
    CurriculumProfile,
    GradeLevel,
    LevelSubject,
    Subject,
)
from modules.academics.subject_schemas import LevelSubjectOut

MODULE = "academics"


def _profile_state(profile: CurriculumProfile) -> dict[str, Any]:
    return {
        "code": profile.code,
        "name": profile.name,
        "name_am": profile.name_am,
        "description": profile.description,
        "term_system": profile.term_system,
        "sort_order": profile.sort_order,
        "is_active": profile.is_active,
        "is_starter": profile.is_starter,
        "is_verified": profile.is_verified,
        "row_version": profile.row_version,
        "deleted": profile.deleted_at is not None,
    }


def _entry_state(rows: list[tuple[CurriculumLevelSubject, GradeLevel, Subject]]) -> list[dict[str, Any]]:
    return [
        {"level": level.code, "subject": subject.code, "credit": entry.credit}
        for entry, level, subject in rows
    ]


async def _profile_rows(
    session: AsyncSession, profile_id: uuid.UUID
) -> list[tuple[CurriculumLevelSubject, GradeLevel, Subject]]:
    rows = (
        await session.execute(
            select(CurriculumLevelSubject, GradeLevel, Subject)
            .join(GradeLevel, GradeLevel.id == CurriculumLevelSubject.level_id)
            .join(Subject, Subject.id == CurriculumLevelSubject.subject_id)
            .where(CurriculumLevelSubject.profile_id == profile_id)
            .order_by(GradeLevel.sort_order, GradeLevel.name, Subject.sort_order, Subject.name)
        )
    ).all()
    return [(row[0], row[1], row[2]) for row in rows]


async def _in_use_ids(session: AsyncSession, profile_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not profile_ids:
        return set()
    rows = (
        (
            await session.execute(
                select(AcademicYear.curriculum_profile_id)
                .where(AcademicYear.curriculum_profile_id.in_(profile_ids))
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    return {row for row in rows if row is not None}


def _profile_out(
    profile: CurriculumProfile,
    rows: list[tuple[CurriculumLevelSubject, GradeLevel, Subject]],
    *,
    in_use: bool,
) -> CurriculumProfileOut:
    levels: list[CurriculumLevelOut] = []
    grouped: dict[uuid.UUID, tuple[GradeLevel, list[LevelSubjectOut]]] = {}
    for entry, level, subject in rows:
        if level.id not in grouped:
            grouped[level.id] = (level, [])
        grouped[level.id][1].append(
            LevelSubjectOut(
                subject_id=str(subject.id),
                code=subject.code,
                name=subject.name,
                name_am=subject.name_am,
                credit=entry.credit,
                is_active=subject.is_active,
            )
        )
    for level, subjects in grouped.values():
        levels.append(
            CurriculumLevelOut(
                level_id=str(level.id),
                level_code=level.code,
                level_name=level.name,
                subjects=subjects,
                total=len(subjects),
            )
        )
    return CurriculumProfileOut(
        id=str(profile.id),
        code=profile.code,
        name=profile.name,
        name_am=profile.name_am,
        description=profile.description,
        term_system=profile.term_system,  # type: ignore[arg-type]
        sort_order=profile.sort_order,
        is_active=profile.is_active,
        is_starter=profile.is_starter,
        is_verified=profile.is_verified,
        in_use=in_use,
        levels=levels,
        row_version=profile.row_version,
    )


async def _live_profile(session: AsyncSession, profile_id: uuid.UUID) -> CurriculumProfile:
    profile = (
        await session.execute(select(CurriculumProfile).where(CurriculumProfile.id == profile_id))
    ).scalar_one_or_none()
    if profile is None:
        raise NotFound(
            "The curriculum profile does not exist",
            message_key="error.academics.curriculum_not_found",
        )
    return profile


async def _assert_code_free(session: AsyncSession, code: str, *, current_id: uuid.UUID | None = None) -> None:
    stmt = select(CurriculumProfile.id).where(CurriculumProfile.code == code)
    if current_id is not None:
        stmt = stmt.where(CurriculumProfile.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "A curriculum profile with that code already exists",
            message_key="error.academics.curriculum_code_taken",
            details={"code": code},
        )


async def _next_order(session: AsyncSession) -> int:
    current = (await session.execute(select(func.max(CurriculumProfile.sort_order)))).scalar_one_or_none()
    return int(current) + 1 if current is not None else 0


async def _out(session: AsyncSession, profile: CurriculumProfile) -> CurriculumProfileOut:
    in_use = await _in_use_ids(session, [profile.id])
    return _profile_out(
        profile,
        await _profile_rows(session, profile.id),
        in_use=profile.id in in_use,
    )


async def list_profiles(
    session: AsyncSession,
    *,
    include_inactive: bool = False,
) -> CurriculumProfileList:
    stmt = select(CurriculumProfile)
    if not include_inactive:
        stmt = stmt.where(CurriculumProfile.is_active.is_(True))
    profiles = (
        (await session.execute(stmt.order_by(CurriculumProfile.sort_order, CurriculumProfile.name)))
        .scalars()
        .all()
    )
    in_use = await _in_use_ids(session, [profile.id for profile in profiles])
    return CurriculumProfileList(
        items=[
            _profile_out(
                profile,
                await _profile_rows(session, profile.id),
                in_use=profile.id in in_use,
            )
            for profile in profiles
        ],
        total=len(profiles),
    )


async def get_profile(session: AsyncSession, profile_id: uuid.UUID) -> CurriculumProfileOut:
    return await _out(session, await _live_profile(session, profile_id))


async def create_profile(
    session: AsyncSession,
    principal: Principal,
    data: CurriculumProfileCreate,
    *,
    via: str = "api",
) -> CurriculumProfileOut:
    await _assert_code_free(session, data.code)
    profile = CurriculumProfile(
        code=data.code,
        name=data.name,
        name_am=data.name_am,
        description=data.description,
        term_system=data.term_system,
        sort_order=data.sort_order if data.sort_order is not None else await _next_order(session),
        is_active=data.is_active,
        is_starter=False,
        is_verified=True,
    )
    session.add(profile)
    await session.flush()
    await record(
        session,
        action="academics.curriculum.create",
        module=MODULE,
        entity_type="academic_curriculum_profile",
        entity_id=str(profile.id),
        after=_profile_state(profile),
        actor=principal,
        via=via,
    )
    return await _out(session, profile)


async def update_profile(
    session: AsyncSession,
    principal: Principal,
    profile_id: uuid.UUID,
    data: CurriculumProfileUpdate,
    *,
    via: str = "api",
    reason: str | None = None,
) -> CurriculumProfileOut:
    profile = await _live_profile(session, profile_id)
    before = _profile_state(profile)
    ensure_row_version(profile, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    changes: dict[str, Any] = {}
    for key in ("name", "name_am", "description", "term_system", "sort_order", "is_active", "is_verified"):
        if key not in payload:
            continue
        value = payload[key]
        if value is None and key not in ("name_am", "description"):
            continue
        if getattr(profile, key) != value:
            setattr(profile, key, value)
            changes[key] = value
    if changes:
        profile.row_version = (profile.row_version or 0) + 1
    await session.flush()
    if changes:
        await record(
            session,
            action="academics.curriculum.update",
            module=MODULE,
            entity_type="academic_curriculum_profile",
            entity_id=str(profile.id),
            before=before,
            after=_profile_state(profile),
            actor=principal,
            reason=reason,
            via=via,
        )
    return await _out(session, profile)


async def duplicate_profile(
    session: AsyncSession,
    principal: Principal,
    profile_id: uuid.UUID,
    data: CurriculumProfileDuplicate,
    *,
    via: str = "api",
) -> CurriculumProfileOut:
    source = await _live_profile(session, profile_id)
    await _assert_code_free(session, data.code)
    copy = CurriculumProfile(
        code=data.code,
        name=data.name,
        name_am=data.name_am,
        description=data.description if data.description is not None else source.description,
        term_system=source.term_system,
        sort_order=await _next_order(session),
        is_active=True,
        is_starter=False,
        is_verified=True,
    )
    session.add(copy)
    await session.flush()
    for entry, _level, _subject in await _profile_rows(session, source.id):
        session.add(
            CurriculumLevelSubject(
                profile_id=copy.id,
                level_id=entry.level_id,
                subject_id=entry.subject_id,
                credit=entry.credit,
            )
        )
    await session.flush()
    await record(
        session,
        action="academics.curriculum.duplicate",
        module=MODULE,
        entity_type="academic_curriculum_profile",
        entity_id=str(copy.id),
        before={"source": source.code},
        after=_profile_state(copy),
        actor=principal,
        reason=data.reason,
        via=via,
    )
    return await _out(session, copy)


async def delete_profile(
    session: AsyncSession,
    principal: Principal,
    profile_id: uuid.UUID,
    *,
    row_version: int | None = None,
    reason: str | None = None,
    via: str = "api",
) -> CurriculumProfileOut:
    profile = await _live_profile(session, profile_id)
    if profile.is_starter:
        raise Conflict(
            "A shipped starter profile cannot be deleted; deactivate or edit it instead",
            message_key="error.academics.curriculum_starter_protected",
        )
    if row_version is not None:
        ensure_row_version(profile, row_version, current_state=_profile_state(profile))
    if profile.id in await _in_use_ids(session, [profile.id]):
        raise Conflict(
            "The curriculum profile is applied to an academic year",
            message_key="error.academics.curriculum_in_use",
        )
    await soft_delete(
        session,
        profile,
        action="academics.curriculum.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="academic_curriculum_profile",
    )
    await session.flush()
    return await _out(session, profile)


async def restore_profile(
    session: AsyncSession,
    principal: Principal,
    profile_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> CurriculumProfileOut:
    profile = await get_including_deleted(session, CurriculumProfile, profile_id)
    if profile is None:
        raise NotFound(
            "The curriculum profile does not exist",
            message_key="error.academics.curriculum_not_found",
        )
    await _assert_code_free(session, profile.code, current_id=profile.id)
    await restore(
        session,
        profile,
        action="academics.curriculum.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="academic_curriculum_profile",
    )
    await session.flush()
    return await _out(session, profile)


async def replace_level_subjects(
    session: AsyncSession,
    principal: Principal,
    profile_id: uuid.UUID,
    level_id: uuid.UUID,
    data: CurriculumLevelReplace,
    *,
    via: str = "api",
) -> CurriculumProfileOut:
    profile = await _live_profile(session, profile_id)
    level = await catalog.scoped_level(session, level_id)
    if not level.is_active:
        raise ValidationFailed(
            "An inactive grade level cannot receive subjects",
            message_key="error.academics.level_inactive",
        )
    before = [
        {"level": row_level.code, "subject": subject.code, "credit": entry.credit}
        for entry, row_level, subject in await _profile_rows(session, profile.id)
    ]
    unique_ids = list(dict.fromkeys(entry.subject_id for entry in data.subjects))
    subjects = {
        subject.id: subject
        for subject in (
            (await session.execute(select(Subject).where(Subject.id.in_(unique_ids)))).scalars().all()
        )
    }
    missing = [str(subject_id) for subject_id in unique_ids if subject_id not in subjects]
    if missing:
        raise ValidationFailed(
            "One or more selected subjects do not exist",
            message_key="error.academics.subject_missing",
            details={"subject_ids": missing},
        )
    inactive = [
        subjects[entry.subject_id].code for entry in data.subjects if not subjects[entry.subject_id].is_active
    ]
    if inactive:
        raise ValidationFailed(
            "Inactive subjects cannot be assigned to a curriculum profile",
            message_key="error.academics.subject_inactive",
            details={"codes": sorted(set(inactive))},
        )
    credits = {entry.subject_id: entry.credit for entry in data.subjects}
    await session.execute(
        delete(CurriculumLevelSubject).where(
            CurriculumLevelSubject.profile_id == profile.id,
            CurriculumLevelSubject.level_id == level.id,
        )
    )
    for subject_id in unique_ids:
        session.add(
            CurriculumLevelSubject(
                profile_id=profile.id,
                level_id=level.id,
                subject_id=subject_id,
                credit=credits[subject_id],
            )
        )
    await session.flush()
    after = [
        {"level": row_level.code, "subject": subject.code, "credit": entry.credit}
        for entry, row_level, subject in await _profile_rows(session, profile.id)
    ]
    if before != after:
        await record(
            session,
            action="academics.curriculum.subjects.replace",
            module=MODULE,
            entity_type="academic_curriculum_profile",
            entity_id=str(profile.id),
            before={"profile": profile.code, "subjects": before},
            after={"profile": profile.code, "subjects": after},
            actor=principal,
            reason=data.reason,
            via=via,
        )
    return await _out(session, profile)


async def _scope_levels(session: AsyncSession) -> list[GradeLevel]:
    first, last = await catalog.academic_scope(session)
    return list(
        (
            await session.execute(
                select(GradeLevel)
                .where(
                    GradeLevel.is_active.is_(True),
                    GradeLevel.scope_level.between(first, last),
                )
                .order_by(GradeLevel.sort_order, GradeLevel.name)
            )
        )
        .scalars()
        .all()
    )


async def profile_assignments(session: AsyncSession, profile_id: uuid.UUID) -> list[CurriculumLevelSubject]:
    """Profile entries for active, in-scope levels, with the profile's credits."""
    levels = await _scope_levels(session)
    level_ids = [level.id for level in levels]
    if not level_ids:
        return []
    rows = (
        (
            await session.execute(
                select(CurriculumLevelSubject)
                .join(Subject, Subject.id == CurriculumLevelSubject.subject_id)
                .where(
                    CurriculumLevelSubject.profile_id == profile_id,
                    CurriculumLevelSubject.level_id.in_(level_ids),
                    Subject.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def seed_assignments(session: AsyncSession, profile_id: uuid.UUID) -> int:
    """Replace the in-scope level-subject map with a profile's assignments.

    Used when a year is created with a profile; the map is school-global, so it
    is replaced rather than merged to avoid leftovers from the previous bundle.
    """
    entries = await profile_assignments(session, profile_id)
    level_ids = {level.id for level in await _scope_levels(session)}
    if level_ids:
        await session.execute(delete(LevelSubject).where(LevelSubject.level_id.in_(level_ids)))
    for entry in entries:
        session.add(
            LevelSubject(
                level_id=entry.level_id,
                subject_id=entry.subject_id,
                credit=entry.credit,
            )
        )
    await session.flush()
    return len(entries)


async def _current_assignments(session: AsyncSession) -> dict[uuid.UUID, dict[uuid.UUID, int]]:
    levels = await _scope_levels(session)
    if not levels:
        return {}
    rows = (
        await session.execute(
            select(LevelSubject).where(LevelSubject.level_id.in_([level.id for level in levels]))
        )
    ).scalars()
    current: dict[uuid.UUID, dict[uuid.UUID, int]] = {}
    for row in rows:
        current.setdefault(row.level_id, {})[row.subject_id] = row.credit
    return current


async def _preview(
    session: AsyncSession,
    year: AcademicYear,
    profile: CurriculumProfile,
) -> tuple[dict[str, Any], list[CurriculumLevelSubject]]:
    levels = await _scope_levels(session)
    level_codes = {level.id: level.code for level in levels}
    current = await _current_assignments(session)
    entries = await profile_assignments(session, profile.id)
    target: dict[uuid.UUID, dict[uuid.UUID, int]] = {level.id: {} for level in levels}
    for entry in entries:
        target[entry.level_id][entry.subject_id] = entry.credit
    assignment_codes = {
        subject.id: subject.code
        for subject in (
            (
                await session.execute(
                    select(Subject).where(
                        Subject.id.in_({subject_id for level in target.values() for subject_id in level})
                    )
                )
            )
            .scalars()
            .all()
        )
    }
    added = 0
    removed = 0
    credits_changed = 0
    changed_levels: list[str] = []
    for level_id in target:
        before = current.get(level_id, {})
        after = target[level_id]
        level_added = set(after) - set(before)
        level_removed = set(before) - set(after)
        level_credit = {
            subject_id for subject_id in set(before) & set(after) if before[subject_id] != after[subject_id]
        }
        added += len(level_added)
        removed += len(level_removed)
        credits_changed += len(level_credit)
        if level_added or level_removed or level_credit:
            changed_levels.append(level_codes.get(level_id, str(level_id)))
    skipped = [
        assignment_codes.get(entry.subject_id, str(entry.subject_id))
        for entry in (
            (
                await session.execute(
                    select(CurriculumLevelSubject)
                    .join(Subject, Subject.id == CurriculumLevelSubject.subject_id)
                    .where(
                        CurriculumLevelSubject.profile_id == profile.id,
                        Subject.is_active.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
    ]
    preview = {
        "applied": False,
        "term_system_matches": profile.term_system == year.term_system,
        "levels_changed": len(changed_levels),
        "assignments_added": added,
        "assignments_removed": removed,
        "credits_changed": credits_changed,
        "changed_levels": changed_levels,
        "skipped_inactive_subjects": sorted(set(skipped)),
    }
    return preview, entries


async def apply_profile(
    session: AsyncSession,
    principal: Principal,
    profile_id: uuid.UUID,
    data: CurriculumApply,
    *,
    via: str = "api",
) -> CurriculumApplyOut:
    profile = await _live_profile(session, profile_id)
    year = (
        await session.execute(select(AcademicYear).where(AcademicYear.id == data.year_id))
    ).scalar_one_or_none()
    if year is None:
        raise NotFound(
            "The academic year does not exist",
            message_key="error.academics.year_not_found",
        )
    if year.status == "closed":
        raise Conflict(
            "A closed academic year cannot be edited",
            message_key="error.academics.year_closed",
        )
    if not profile.is_active:
        raise Conflict(
            "An inactive curriculum profile cannot be applied",
            message_key="error.academics.curriculum_inactive",
        )
    preview, entries = await _preview(session, year, profile)
    if not data.confirm:
        return CurriculumApplyOut(
            year_id=str(year.id),
            year_code=year.code,
            profile_id=str(profile.id),
            profile_code=profile.code,
            profile_name=profile.name,
            profile_term_system=profile.term_system,  # type: ignore[arg-type]
            year_term_system=year.term_system,  # type: ignore[arg-type]
            **preview,
        )
    if profile.term_system != year.term_system:
        raise Conflict(
            "The profile's term system does not match the year; create the year with this profile instead",
            message_key="error.academics.curriculum_term_mismatch",
            details={
                "profile_term_system": profile.term_system,
                "year_term_system": year.term_system,
            },
        )
    if data.row_version is not None:
        ensure_row_version(year, data.row_version, current_state={"row_version": year.row_version})
    before_state = {
        "year": year.code,
        "profile": None,
        "assignments": await _assignment_state(session, await _current_assignments(session)),
    }
    if year.curriculum_profile_id is not None:
        previous = (
            await session.execute(
                select(CurriculumProfile).where(CurriculumProfile.id == year.curriculum_profile_id)
            )
        ).scalar_one_or_none()
        before_state["profile"] = previous.code if previous is not None else None
    current = await _current_assignments(session)
    for level_id, subjects in current.items():
        if subjects:
            await session.execute(delete(LevelSubject).where(LevelSubject.level_id == level_id))
    for entry in entries:
        session.add(
            LevelSubject(
                level_id=entry.level_id,
                subject_id=entry.subject_id,
                credit=entry.credit,
            )
        )
    if year.curriculum_profile_id != profile.id:
        year.curriculum_profile_id = profile.id
        year.row_version = (year.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="academics.curriculum.apply",
        module=MODULE,
        entity_type="academic_year",
        entity_id=str(year.id),
        before=before_state,
        after={
            "year": year.code,
            "profile": profile.code,
            "assignments": await _assignment_state(
                session,
                {entry.level_id: {entry.subject_id: entry.credit} for entry in entries},
            ),
        },
        actor=principal,
        reason=data.reason,
        via=via,
    )
    return CurriculumApplyOut(
        year_id=str(year.id),
        year_code=year.code,
        profile_id=str(profile.id),
        profile_code=profile.code,
        profile_name=profile.name,
        profile_term_system=profile.term_system,  # type: ignore[arg-type]
        year_term_system=year.term_system,  # type: ignore[arg-type]
        **{**preview, "applied": True},
    )


async def _assignment_state(
    session: AsyncSession, assignments: dict[uuid.UUID, dict[uuid.UUID, int]]
) -> list[dict[str, Any]]:
    level_ids = set(assignments)
    subject_ids = {subject_id for subjects in assignments.values() for subject_id in subjects}
    level_codes = {
        level.id: level.code
        for level in (
            (await session.execute(select(GradeLevel).where(GradeLevel.id.in_(level_ids)))).scalars().all()
            if level_ids
            else []
        )
    }
    subject_codes = {
        subject.id: subject.code
        for subject in (
            (await session.execute(select(Subject).where(Subject.id.in_(subject_ids)))).scalars().all()
            if subject_ids
            else []
        )
    }
    return [
        {
            "level": level_codes.get(level_id, str(level_id)),
            "subjects": {
                subject_codes.get(subject_id, str(subject_id)): credit
                for subject_id, credit in sorted(subjects.items(), key=lambda item: str(item[0]))
            },
        }
        for level_id, subjects in sorted(assignments.items(), key=lambda item: str(item[0]))
    ]


__all__ = [
    "apply_profile",
    "create_profile",
    "delete_profile",
    "duplicate_profile",
    "get_profile",
    "list_profiles",
    "profile_assignments",
    "replace_level_subjects",
    "restore_profile",
    "seed_assignments",
    "update_profile",
]
