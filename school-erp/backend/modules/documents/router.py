"""HTTP routes for Document Studio (P5-02)."""

from __future__ import annotations

from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session as db_session
from core.documents.registry import FORMAT_OPTIONS
from core.documents.service import fields_for
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from modules.documents.schemas import (
    DocumentFieldOut,
    DocumentFieldsOut,
    DocumentFormatOptions,
)

router = APIRouter(tags=["documents"])


@router.get("/fields", response_model=DocumentFieldsOut)
async def list_fields_route(
    request: Request,
    principal: Principal = Depends(require("documents.template.design")),
    session: AsyncSession = Depends(db_session),
) -> DocumentFieldsOut:
    """Fields from enabled modules, with the formatting options they support."""
    registered = await fields_for(
        session,
        request.app.state.registry,
        request.app.state.settings,
    )
    return DocumentFieldsOut(
        items=[DocumentFieldOut(**item.to_dict()) for item in registered],
        format_options=DocumentFormatOptions(
            calendar=list(FORMAT_OPTIONS["calendar"]),
            script=list(FORMAT_OPTIONS["script"]),
            money=list(FORMAT_OPTIONS["money"]),
        ),
    )


__all__ = ["router"]
