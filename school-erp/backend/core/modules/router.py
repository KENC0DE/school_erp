from __future__ import annotations

from core.audit.service import record
from core.auth.deps import authenticated, public_access, require
from core.auth.principal import Principal
from core.db.deps import get_session
from core.modules.licensing import module_states, set_module_enabled
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info", dependencies=[Depends(public_access)])
async def info(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "api_version": settings.api_version,
        "app_version": settings.app_version,
        "min_client_version": settings.min_client_version,
        "name": settings.app_name,
        "environment": settings.app_env,
    }


@router.get("/capabilities", dependencies=[Depends(authenticated)])
async def capabilities(
    request: Request,
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> dict:
    registry = request.app.state.registry
    states = await module_states(session, registry, request.app.state.settings)
    features = []
    for manifest in registry.all():
        state = states[manifest.key]
        if not state["available"]:
            continue
        permitted = any(principal.can(perm.code) for perm in manifest.permissions) or not manifest.permissions
        features.append(
            {
                "key": manifest.key,
                "version": manifest.version,
                "permitted": permitted,
                "nav": [
                    {"key": nav.key, "path": nav.path, "label_key": nav.label_key} for nav in manifest.nav
                ],
            }
        )
    return {"features": features, "languages": ["en", "am"], "calendar": "ethiopian"}


@router.get("/modules", dependencies=[Depends(require("modules.view"))])
async def list_modules(
    request: Request,
    principal: Principal = Depends(require("modules.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    registry = request.app.state.registry
    states = await module_states(session, registry, request.app.state.settings)
    items = []
    for manifest in registry.all():
        state = states[manifest.key]
        permitted = any(principal.can(perm.code) for perm in manifest.permissions) or not manifest.permissions
        dependencies = [
            {
                "key": dependency,
                "name": states.get(dependency, {}).get("name", dependency),
                "available": bool(states.get(dependency, {}).get("available", False)),
            }
            for dependency in manifest.depends_on
        ]
        dependants = [
            {
                "key": other.key,
                "name": other.name,
                "enabled": bool(states.get(other.key, {}).get("enabled", False)),
            }
            for other in registry.all()
            if manifest.key in other.depends_on
        ]
        items.append(
            {
                "key": manifest.key,
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "core": manifest.core,
                "licensable": manifest.licensable,
                "depends_on": manifest.depends_on,
                "dependencies": dependencies,
                "dependants": dependants,
                "blocked_by": [item["key"] for item in dependencies if not item["available"]],
                "permitted": permitted,
                **{k: state[k] for k in ("licensed", "enabled", "available")},
            }
        )
    return {"items": items, "next_cursor": None}


class ModuleToggle(BaseModel):
    enabled: bool


@router.put("/modules/{key}", dependencies=[Depends(require("modules.manage"))])
async def toggle_module(
    key: str,
    payload: ModuleToggle,
    request: Request,
    principal: Principal = Depends(require("modules.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    registry = request.app.state.registry
    before = (await module_states(session, registry, request.app.state.settings)).get(key)
    await set_module_enabled(session, registry, key, payload.enabled, principal.actor_id)  # type: ignore[arg-type]
    after = (await module_states(session, registry, request.app.state.settings)).get(key)

    def snapshot(state: dict | None) -> dict | None:
        if state is None:
            return None
        return {k: state[k] for k in ("licensed", "enabled", "available")}

    await record(
        session,
        action="modules.toggle",
        module="core",
        entity_type="module",
        entity_id=key,
        before=snapshot(before),
        after=snapshot(after),
        actor=principal,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return {"key": key, **(after or {})}
