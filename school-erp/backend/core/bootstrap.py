from __future__ import annotations

from fastapi import FastAPI

from core.i18n.service import load_defaults
from core.modules.licensing import ensure_module_rows
from core.themes.service import ensure_default_theme


async def bootstrap(app: FastAPI) -> None:
    """Idempotent startup work: modules, translations, builtin theme."""
    async with app.state.db.session() as session:
        await ensure_module_rows(session, app.state.registry)
        await load_defaults(session, app.state.registry)
        await ensure_default_theme(session)
        await session.commit()
