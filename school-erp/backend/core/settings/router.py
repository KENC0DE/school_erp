"""Settings API and generated settings form metadata (ARCH §5.10)."""

from __future__ import annotations

from typing import Any

from app.errors import NotFound
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.service import record
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from core.settings.schema import require_field
from core.settings.service import (
    all_settings,
    clear_setting,
    effective_map,
    module_model,
    set_setting,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _model(request: Request, module: str) -> type:
    model = module_model(request.app.state.registry, module)
    if model is None:
        raise NotFound(
            f"Unknown settings module {module}",
            message_key="error.unknown_settings_module",
            details={"module": module},
        )
    return model


@router.get("", dependencies=[Depends(require("settings.view"))])
async def list_settings(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {
        "items": await all_settings(session, request.app.state.registry),
        "next_cursor": None,
    }


class SettingUpdate(BaseModel):
    value: Any


def _view(effective) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        **effective.spec.as_dict(),
        "value": effective.value,
        "source": effective.source,
    }


@router.put("/{module}/{key}", dependencies=[Depends(require("settings.manage"))])
async def update_setting(
    module: str,
    key: str,
    payload: SettingUpdate,
    request: Request,
    principal: Principal = Depends(require("settings.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    model = _model(request, module)
    require_field(module, model, key)
    before = (await effective_map(session, module, model)).get(key)
    after = await set_setting(session, module, model, key, payload.value, actor=principal)
    await record(
        session,
        action="settings.update",
        module="core",
        entity_type="setting",
        entity_id=f"{module}.{key}",
        before={"value": before.value if before else None, "source": before.source if before else None},
        after={"value": after.value, "source": after.source},
        actor=principal,
        via=principal.via,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return _view(after)


@router.delete("/{module}/{key}", dependencies=[Depends(require("settings.manage"))])
async def reset_setting(
    module: str,
    key: str,
    request: Request,
    principal: Principal = Depends(require("settings.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    model = _model(request, module)
    require_field(module, model, key)
    before = (await effective_map(session, module, model)).get(key)
    changed = await clear_setting(session, module, model, key, actor=principal)
    after = (await effective_map(session, module, model))[key]
    if changed:
        await record(
            session,
            action="settings.clear",
            module="core",
            entity_type="setting",
            entity_id=f"{module}.{key}",
            before={"value": before.value if before else None, "source": before.source if before else None},
            after={"value": after.value, "source": after.source},
            actor=principal,
            via=principal.via,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    await session.commit()
    return _view(after)


__all__ = ["router"]
