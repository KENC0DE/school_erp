"""The live document-field registry (P5-02)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from core.documents.registry import RegisteredField, collect_fields
from core.modules.licensing import module_states

if TYPE_CHECKING:
    from app.settings import Settings

    from core.modules.registry import ModuleRegistry


async def fields_for(
    session: AsyncSession,
    registry: ModuleRegistry,
    settings: Settings,
) -> list[RegisteredField]:
    """Resolve the three module gates once, then collect every offered field."""
    states = await module_states(session, registry, settings)
    return collect_fields(registry.all(), states)


__all__ = ["fields_for"]
