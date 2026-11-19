from __future__ import annotations

from app.logging import request_id_var
from core.actions.registry import ActionContext, registry
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from core.modules.licensing import module_states
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str


@router.get("/tools", dependencies=[Depends(require("ai.use"))])
async def tools(
    request: Request,
    principal: Principal = Depends(require("ai.use")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    states = await module_states(session, request.app.state.registry, request.app.state.settings)
    visible = registry.visible(principal, states)
    return {"items": [action.to_tool() for action in visible]}


@router.post("/chat", dependencies=[Depends(require("ai.use"))])
async def chat(
    payload: ChatRequest,
    request: Request,
    principal: Principal = Depends(require("ai.use")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    states = await module_states(session, request.app.state.registry, request.app.state.settings)
    visible = registry.visible(principal, states)
    settings = request.app.state.settings
    return {
        "provider": settings.ai_provider,
        "model": settings.ai_model,
        "configured": bool(settings.ai_api_key) and settings.ai_provider != "fake",
        "reply": f"Echo: {payload.message}",
        "request_id": request_id_var.get(),
        "tools": [action.to_tool() for action in visible],
        "note_key": "ai.stub_note",
    }


@router.post("/actions/{key}/preview", dependencies=[Depends(require("ai.use"))])
async def preview_action(
    key: str,
    payload: dict,
    principal: Principal = Depends(require("ai.use")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.errors import NotFound

    action = registry.get(key)
    if action is None:
        raise NotFound("Unknown action")
    if not principal.can(action.permission):
        from app.errors import Forbidden

        raise Forbidden("You do not hold this action's permission")
    if action.preview is None:
        return {"key": key, "preview": None, "requires_confirmation": action.risk != "read"}
    ctx = ActionContext(principal=principal, session=session, via="ai", request_id=request_id_var.get())
    result = await action.preview(ctx, payload)
    return {"key": key, "preview": result, "requires_confirmation": action.risk != "read"}
