"""Idempotent bootstrap for the shipped curriculum starter profiles."""

from __future__ import annotations

from core.db.filters import INCLUDE_DELETED
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.curriculum_defaults import (
    STARTER_PROFILES,
    STARTER_SUBJECTS,
    StarterProfile,
)
from modules.academics.models import (
    CurriculumLevelSubject,
    CurriculumProfile,
    GradeLevel,
    Subject,
)


async def _live_subjects(session: AsyncSession) -> dict[str, Subject]:
    rows = (
        (
            await session.execute(
                select(Subject)
                .where(Subject.code.in_([item.code for item in STARTER_SUBJECTS]))
                .execution_options(**{INCLUDE_DELETED: True})
            )
        )
        .scalars()
        .all()
    )
    return {row.code: row for row in rows}


async def _ensure_subjects(session: AsyncSession) -> dict[str, Subject]:
    subjects = await _live_subjects(session)
    missing = [item for item in STARTER_SUBJECTS if item.code not in subjects]
    if not missing:
        return subjects
    current = (await session.execute(select(func.max(Subject.sort_order)))).scalar_one_or_none()
    next_order = int(current) + 1 if current is not None else 0
    for offset, item in enumerate(missing):
        subject = Subject(
            code=item.code,
            name=item.name,
            name_am=item.name_am,
            sort_order=next_order + offset,
            is_active=True,
        )
        session.add(subject)
        subjects[item.code] = subject
    await session.flush()
    return subjects


async def _levels_by_code(session: AsyncSession) -> dict[str, GradeLevel]:
    rows = (await session.execute(select(GradeLevel))).scalars().all()
    return {row.code: row for row in rows}


async def _existing_profiles(session: AsyncSession) -> set[str]:
    rows = (
        (
            await session.execute(
                select(CurriculumProfile.code)
                .where(CurriculumProfile.code.in_([item.code for item in STARTER_PROFILES]))
                .execution_options(**{INCLUDE_DELETED: True})
            )
        )
        .scalars()
        .all()
    )
    return set(rows)


async def _add_entries(
    session: AsyncSession,
    profile: CurriculumProfile,
    spec: StarterProfile,
    *,
    subjects: dict[str, Subject],
    levels: dict[str, GradeLevel],
) -> None:
    for level_code, subject_codes in spec.levels.items():
        level = levels.get(level_code)
        if level is None or level.deleted_at is not None:
            continue
        for subject_code in subject_codes:
            subject = subjects.get(subject_code)
            if subject is None or subject.deleted_at is not None:
                continue
            session.add(
                CurriculumLevelSubject(
                    profile_id=profile.id,
                    level_id=level.id,
                    subject_id=subject.id,
                    credit=1,
                )
            )


async def ensure_default_curriculum(session: AsyncSession) -> None:
    """Create missing starter subjects and profiles. Never overwrites edits."""
    subjects = await _ensure_subjects(session)
    existing = await _existing_profiles(session)
    missing = [item for item in STARTER_PROFILES if item.code not in existing]
    if not missing:
        return
    levels = await _levels_by_code(session)
    for spec in missing:
        profile = CurriculumProfile(
            code=spec.code,
            name=spec.name,
            name_am=spec.name_am,
            description=spec.description,
            term_system=spec.term_system,
            sort_order=spec.sort_order,
            is_active=True,
            is_starter=True,
            is_verified=False,
        )
        session.add(profile)
        await session.flush()
        await _add_entries(session, profile, spec, subjects=subjects, levels=levels)
    await session.flush()


__all__ = ["ensure_default_curriculum"]
