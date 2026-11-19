from __future__ import annotations

from core.db.deps import get_session
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request, session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("select 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "down"})
    return {"status": "ok", "database": "up", "modules": len(request.app.state.registry.all())}
