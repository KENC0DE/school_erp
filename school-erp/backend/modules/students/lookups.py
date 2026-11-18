"""Resolve academic labels through the academics module's public services.

The students module never imports another module's tables. Names and codes for
years, levels and sections come from its service layer, cached per request.
"""

from __future__ import annotations

import uuid

from app.errors import NotFound
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics import section_service
from modules.academics import service as catalog
from modules.academics import years as year_service
from modules.academics.schemas import LevelOut, YearOut
from modules.academics.section_schemas import SectionOut


class AcademicLabels:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._years: dict[str, YearOut] = {}
        self._levels: dict[str, LevelOut] = {}
        self._sections: dict[str, SectionOut] = {}

    async def year(self, year_id: uuid.UUID | str) -> YearOut | None:
        key = str(year_id)
        if key not in self._years:
            try:
                self._years[key] = await year_service.get_year(self.session, uuid.UUID(key))
            except (NotFound, ValueError):
                return None
        return self._years[key]

    async def level(self, level_id: uuid.UUID | str) -> LevelOut | None:
        key = str(level_id)
        if key not in self._levels:
            try:
                self._levels[key] = await catalog.get_level(self.session, uuid.UUID(key), all_scope=True)
            except (NotFound, ValueError):
                return None
        return self._levels[key]

    async def section(self, section_id: uuid.UUID | str) -> SectionOut | None:
        key = str(section_id)
        if key not in self._sections:
            try:
                self._sections[key] = await section_service.get_section(
                    self.session, uuid.UUID(key), all_scope=True
                )
            except (NotFound, ValueError):
                return None
        return self._sections[key]


__all__ = ["AcademicLabels"]
