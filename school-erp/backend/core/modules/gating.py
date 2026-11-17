from __future__ import annotations

from collections.abc import Callable

from app.errors import ModuleDisabled
from core.db.deps import get_session
from core.modules.licensing import module_states
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


def module_gate(key: str) -> Callable:
    """Mount once per module router: hit the three gates before any handler."""

    async def dependency(request: Request, session: AsyncSession = Depends(get_session)) -> None:
        registry = request.app.state.registry
        states = await module_states(session, registry, request.app.state.settings)
        state = states.get(key)
        if state is None or not state["available"]:
            raise ModuleDisabled(
                f"Module '{key}' is not available",
                message_key="error.module_disabled",
                details={"module": key},
            )

    dependency.__module_gate__ = key  # type: ignore[attr-defined]
    return dependency
