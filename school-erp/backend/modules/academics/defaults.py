"""Shipped starter catalog for academic structure (ARCH §9.1).

These are defaults, not protected definitions: every row can be renamed,
re-ordered, re-scoped or deactivated. Shipped rows carry ``is_starter=True`` and
``is_verified=False`` so the setup screens can show the "verify against your
school's actual structure" hint until the school confirms them.

The hook only creates missing rows. A deliberately deleted starter row stays
deleted on the next restart (the lookup includes soft-deleted rows).
"""

from __future__ import annotations

from core.db.filters import INCLUDE_DELETED
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.curriculum_seed import ensure_default_curriculum
from modules.academics.models import GradeLevel, Stage, StageLevel

# code, English name, Amharic name, scope level, sort order
DEFAULT_LEVELS: tuple[tuple[str, str, str, int, int], ...] = (
    ("kg1", "KG 1", "ኬጂ 1", 0, 0),
    ("kg2", "KG 2", "ኬጂ 2", 0, 1),
    ("kg3", "KG 3", "ኬጂ 3", 0, 2),
    ("g1", "Grade 1", "ክፍል 1", 1, 3),
    ("g2", "Grade 2", "ክፍል 2", 2, 4),
    ("g3", "Grade 3", "ክፍል 3", 3, 5),
    ("g4", "Grade 4", "ክፍል 4", 4, 6),
    ("g5", "Grade 5", "ክፍል 5", 5, 7),
    ("g6", "Grade 6", "ክፍል 6", 6, 8),
    ("g7", "Grade 7", "ክፍል 7", 7, 9),
    ("g8", "Grade 8", "ክፍል 8", 8, 10),
    ("g9", "Grade 9", "ክፍል 9", 9, 11),
    ("g10", "Grade 10", "ክፍል 10", 10, 12),
    ("g11", "Grade 11", "ክፍል 11", 11, 13),
    ("g12", "Grade 12", "ክፍል 12", 12, 14),
)

# code, English name, Amharic name, sort order, member level codes
DEFAULT_STAGES: tuple[tuple[str, str, str, int, tuple[str, ...]], ...] = (
    ("kindergarten", "Kindergarten", "መዋለ ሕፃናት", 0, ("kg1", "kg2", "kg3")),
    ("primary_lower", "Primary 1–4", "የመጀመሪያ ደረጃ 1–4", 1, ("g1", "g2", "g3", "g4")),
    ("primary_upper", "Primary 5–8", "የመጀመሪያ ደረጃ 5–8", 2, ("g5", "g6", "g7", "g8")),
    ("secondary", "Secondary 9–10", "ሁለተኛ ደረጃ 9–10", 3, ("g9", "g10")),
    ("preparatory", "Preparatory 11–12", "የዝግጅት ደረጃ 11–12", 4, ("g11", "g12")),
)


async def _existing_levels(session: AsyncSession) -> dict[str, GradeLevel]:
    rows = (
        (
            await session.execute(
                select(GradeLevel)
                .where(GradeLevel.code.in_([item[0] for item in DEFAULT_LEVELS]))
                .execution_options(**{INCLUDE_DELETED: True})
            )
        )
        .scalars()
        .all()
    )
    return {row.code: row for row in rows}


async def ensure_default_academics(session: AsyncSession) -> None:
    """Create any missing starter levels and stages. Never overwrites edits."""
    levels = await _existing_levels(session)
    for code, name, name_am, scope_level, sort_order in DEFAULT_LEVELS:
        if code in levels:
            continue
        level = GradeLevel(
            code=code,
            name=name,
            name_am=name_am,
            scope_level=scope_level,
            sort_order=sort_order,
            is_active=True,
            is_starter=True,
            is_verified=False,
        )
        session.add(level)
        levels[code] = level
    await session.flush()

    stage_codes = [item[0] for item in DEFAULT_STAGES]
    existing_stages = {
        row.code: row
        for row in (
            (
                await session.execute(
                    select(Stage)
                    .where(Stage.code.in_(stage_codes))
                    .execution_options(**{INCLUDE_DELETED: True})
                )
            )
            .scalars()
            .all()
        )
    }
    for code, name, name_am, sort_order, member_codes in DEFAULT_STAGES:
        if code in existing_stages:
            continue
        stage = Stage(
            code=code,
            name=name,
            name_am=name_am,
            sort_order=sort_order,
            is_active=True,
            is_starter=True,
            is_verified=False,
        )
        session.add(stage)
        await session.flush()
        for member in member_codes:
            level = levels.get(member)
            if level is not None:
                session.add(StageLevel(stage_id=stage.id, level_id=level.id))
        existing_stages[code] = stage
    await session.flush()
    await ensure_default_curriculum(session)


__all__ = ["DEFAULT_LEVELS", "DEFAULT_STAGES", "ensure_default_academics"]
