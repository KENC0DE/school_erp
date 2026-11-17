from __future__ import annotations

from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from core.rbac.models import Role, RolePermission
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/rbac", tags=["rbac"])


@router.get("/roles", dependencies=[Depends(require("roles.view"))])
async def list_roles(session: AsyncSession = Depends(get_session)) -> dict:
    roles = (await session.execute(select(Role).order_by(Role.key))).scalars().all()
    permissions = (await session.execute(select(RolePermission))).scalars().all()
    by_role: dict = {}
    for permission in permissions:
        by_role.setdefault(str(permission.role_id), []).append(
            {"permission": permission.permission, "scope": permission.scope}
        )
    return {
        "items": [
            {
                "id": str(role.id),
                "key": role.key,
                "name": role.name,
                "is_system": role.is_system,
                "permissions": by_role.get(str(role.id), []),
            }
            for role in roles
        ],
        "next_cursor": None,
    }


@router.get("/permissions", dependencies=[Depends(require("roles.view"))])
async def list_permissions(request: Request, principal: Principal = Depends(require("roles.view"))) -> dict:
    declared = request.app.state.registry.permissions()
    return {
        "items": declared,
        "next_cursor": None,
        "can_grant": sorted(principal.permissions) if "*" not in principal.permissions else ["*"],
    }
