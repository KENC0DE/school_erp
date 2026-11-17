from __future__ import annotations

from core.auth.deps import public_access
from core.db.deps import get_session
from core.themes.models import Theme
from core.themes.service import active_theme
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get("/active", dependencies=[Depends(public_access)])
async def active(session: AsyncSession = Depends(get_session)) -> dict:
    return await active_theme(session)


@router.get("", dependencies=[Depends(public_access)])
async def list_themes(session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.execute(select(Theme).order_by(Theme.key))).scalars().all()
    return {
        "items": [
            {"key": row.key, "name": row.name, "is_default": row.is_default, "is_active": row.is_active}
            for row in rows
        ]
    }
