"""RBAC management API (ARCH §5.3, P1-05)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.errors import Conflict, Forbidden, NotFound, ValidationFailed
from core.audit.service import record
from core.auth.deps import require
from core.auth.models import User
from core.auth.principal import Principal
from core.db.deps import get_session
from core.rbac.models import (
    Role,
    RolePermission,
    UserPermissionOverride,
    UserRole,
)
from core.rbac.schemas import (
    OverrideCreate,
    RoleAssignment,
    RoleCreate,
    RolePermissionSet,
    RoleUpdate,
)
from core.rbac.service import (
    effective_permissions,
    holds,
    role_permission_pairs,
    roles_for_user,
)
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/rbac", tags=["rbac"])


def _declared(request: Request) -> dict[str, set[str]]:
    return {item["code"]: set(item["scopes"]) for item in request.app.state.registry.permissions()}


def _request_meta(request: Request) -> dict[str, Any]:
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


def _validate_pairs(declared: dict[str, set[str]], pairs: list[tuple[str, str]]) -> None:
    for permission, scope in pairs:
        if permission not in declared:
            raise ValidationFailed(
                f"Unknown permission: {permission}",
                code="UNKNOWN_PERMISSION",
                message_key="error.unknown_permission",
                details={"permission": permission},
            )
        if scope not in declared[permission]:
            raise ValidationFailed(
                f"Scope '{scope}' is not accepted by {permission}",
                code="INVALID_SCOPE",
                message_key="error.invalid_scope",
                details={"permission": permission, "scope": scope},
            )


def _assert_grantable(principal: Principal, pairs: list[tuple[str, str]]) -> None:
    for permission, scope in pairs:
        if not holds(principal, permission, scope):
            raise Forbidden(
                f"You cannot grant {permission} ({scope}) because you do not hold it",
                message_key="error.cannot_grant",
                code="CANNOT_GRANT",
                details={"permission": permission, "scope": scope},
            )


def _role_out(role: Role, pairs: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": str(role.id),
        "key": role.key,
        "name": role.name,
        "description": role.description,
        "is_system": role.is_system,
        "is_active": role.is_active,
        "require_totp": role.require_totp,
    }
    if pairs is not None:
        body["permissions"] = [
            {"permission": permission, "scope": scope} for permission, scope in sorted(pairs)
        ]
    return body


async def _get_role(session: AsyncSession, role_id: uuid.UUID) -> Role:
    role = await session.get(Role, role_id)
    if role is None:
        raise NotFound("The role does not exist", message_key="error.role_not_found")
    return role


async def _get_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("The user does not exist", message_key="error.user_not_found")
    return user


async def _role_pairs_for_roles(session: AsyncSession, role_ids: list[uuid.UUID]) -> list[tuple[str, str]]:
    if not role_ids:
        return []
    rows = await session.execute(
        select(RolePermission.permission, RolePermission.scope).where(RolePermission.role_id.in_(role_ids))
    )
    return [(permission, scope) for permission, scope in rows.all()]


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
        "items": [{**_role_out(role), "permissions": by_role.get(str(role.id), [])} for role in roles],
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


@router.get("/roles/{role_id}", dependencies=[Depends(require("roles.view"))])
async def get_role(role_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    role = await _get_role(session, role_id)
    pairs = await role_permission_pairs(session, role.id)
    users = (
        (await session.execute(select(UserRole.user_id).where(UserRole.role_id == role.id))).scalars().all()
    )
    return {**_role_out(role, pairs), "user_count": len(users)}


@router.post("/roles", status_code=201, dependencies=[Depends(require("roles.manage"))])
async def create_role(
    payload: RoleCreate,
    request: Request,
    principal: Principal = Depends(require("roles.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    existing = (await session.execute(select(Role).where(Role.key == payload.key))).scalar_one_or_none()
    if existing is not None:
        raise Conflict("A role with that key already exists", message_key="error.role_exists")
    pairs = [(grant.permission, grant.scope) for grant in payload.permissions]
    declared = _declared(request)
    _validate_pairs(declared, pairs)
    _assert_grantable(principal, pairs)

    role = Role(
        key=payload.key,
        name=payload.name,
        description=payload.description,
        require_totp=payload.require_totp,
        is_system=False,
        is_active=True,
    )
    session.add(role)
    await session.flush()
    for permission, scope in pairs:
        session.add(RolePermission(role_id=role.id, permission=permission, scope=scope))
    await record(
        session,
        action="rbac.role.create",
        module="core",
        entity_type="role",
        entity_id=str(role.id),
        after=_role_out(role, pairs),
        actor=principal,
        via=principal.via,
        **_request_meta(request),
    )
    await session.commit()
    return _role_out(role, pairs)


@router.patch("/roles/{role_id}", dependencies=[Depends(require("roles.manage"))])
async def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    request: Request,
    principal: Principal = Depends(require("roles.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    role = await _get_role(session, role_id)
    before = _role_out(role)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(role, key, value)
    await record(
        session,
        action="rbac.role.update",
        module="core",
        entity_type="role",
        entity_id=str(role.id),
        before=before,
        after={**_role_out(role), "changed": sorted(changes)},
        actor=principal,
        via=principal.via,
        **_request_meta(request),
    )
    await session.commit()
    return _role_out(role, await role_permission_pairs(session, role.id))


@router.delete("/roles/{role_id}", dependencies=[Depends(require("roles.manage"))])
async def deactivate_role(
    role_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require("roles.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Deactivate instead of deleting; users immediately lose its permissions."""
    role = await _get_role(session, role_id)
    if not role.is_active:
        return _role_out(role)
    before = _role_out(role)
    role.is_active = False
    await record(
        session,
        action="rbac.role.deactivate",
        module="core",
        entity_type="role",
        entity_id=str(role.id),
        before=before,
        after=_role_out(role),
        actor=principal,
        via=principal.via,
        reason="Role deactivated",
        **_request_meta(request),
    )
    await session.commit()
    return _role_out(role)


@router.put("/roles/{role_id}/permissions", dependencies=[Depends(require("roles.manage"))])
async def set_role_permissions(
    role_id: uuid.UUID,
    payload: RolePermissionSet,
    request: Request,
    principal: Principal = Depends(require("roles.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    role = await _get_role(session, role_id)
    new_pairs = [(grant.permission, grant.scope) for grant in payload.permissions]
    declared = _declared(request)
    _validate_pairs(declared, new_pairs)

    current = set(await role_permission_pairs(session, role.id))
    added = sorted(set(new_pairs) - current)
    _assert_grantable(principal, added)

    before = _role_out(role, sorted(current))
    for row in (
        (await session.execute(select(RolePermission).where(RolePermission.role_id == role.id)))
        .scalars()
        .all()
    ):
        await session.delete(row)
    for permission, scope in sorted(set(new_pairs)):
        session.add(RolePermission(role_id=role.id, permission=permission, scope=scope))
    await record(
        session,
        action="rbac.role.permissions",
        module="core",
        entity_type="role",
        entity_id=str(role.id),
        before=before,
        after=_role_out(role, sorted(set(new_pairs))),
        actor=principal,
        via=principal.via,
        reason="Role permissions changed",
        **_request_meta(request),
    )
    await session.commit()
    return _role_out(role, sorted(set(new_pairs)))


@router.get("/users/{user_id}/permissions", dependencies=[Depends(require("roles.view"))])
async def user_permissions(user_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    user = await _get_user(session, user_id)
    permissions, scopes = await effective_permissions(session, user.id)
    role_rows = (
        await session.execute(
            select(Role.key, RolePermission.permission, RolePermission.scope)
            .join(UserRole, UserRole.role_id == Role.id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .where(UserRole.user_id == user.id)
            .order_by(Role.key, RolePermission.permission)
        )
    ).all()
    overrides = (
        (
            await session.execute(
                select(UserPermissionOverride)
                .where(UserPermissionOverride.user_id == user.id)
                .order_by(UserPermissionOverride.permission)
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    return {
        "user_id": str(user.id),
        "roles": await roles_for_user(session, user.id),
        "role_permissions": [
            {"role": role, "permission": permission, "scope": scope} for role, permission, scope in role_rows
        ],
        "overrides": [
            {
                "id": str(item.id),
                "permission": item.permission,
                "scope": item.scope,
                "effect": item.effect,
                "expires_at": item.expires_at.isoformat() if item.expires_at else None,
                "expired": bool(
                    item.expires_at
                    and (item.expires_at if item.expires_at.tzinfo else item.expires_at.replace(tzinfo=UTC))
                    < now
                ),
                "reason": item.reason,
            }
            for item in overrides
        ],
        "effective": {
            "permissions": sorted(permissions),
            "scopes": {key: sorted(value) for key, value in sorted(scopes.items())},
        },
    }


@router.get("/users/{user_id}/roles", dependencies=[Depends(require("roles.view"))])
async def user_roles(user_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    user = await _get_user(session, user_id)
    rows = (
        (
            await session.execute(
                select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    return {"items": [_role_out(role) for role in rows], "next_cursor": None}


@router.post("/users/{user_id}/roles", status_code=201, dependencies=[Depends(require("roles.manage"))])
async def assign_role(
    user_id: uuid.UUID,
    payload: RoleAssignment,
    request: Request,
    principal: Principal = Depends(require("roles.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await _get_user(session, user_id)
    role = await _get_role(session, uuid.UUID(payload.role_id))
    if not role.is_active:
        raise Conflict("That role is deactivated", message_key="error.role_inactive")
    pairs = await _role_pairs_for_roles(session, [role.id])
    _assert_grantable(principal, pairs)

    existing = (
        await session.execute(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {"ok": True, "already_assigned": True}
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await record(
        session,
        action="rbac.user.role_assigned",
        module="core",
        entity_type="user",
        entity_id=str(user.id),
        after={"role": role.key, "role_id": str(role.id)},
        actor=principal,
        via=principal.via,
        reason="Role assigned",
        **_request_meta(request),
    )
    await session.commit()
    return {"ok": True, "role": _role_out(role)}


@router.delete("/users/{user_id}/roles/{role_id}", dependencies=[Depends(require("roles.manage"))])
async def remove_role(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require("roles.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await _get_user(session, user_id)
    role = await _get_role(session, role_id)
    row = (
        await session.execute(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("That role is not assigned", message_key="error.role_not_assigned")
    await session.delete(row)
    await record(
        session,
        action="rbac.user.role_removed",
        module="core",
        entity_type="user",
        entity_id=str(user.id),
        before={"role": role.key, "role_id": str(role.id)},
        actor=principal,
        via=principal.via,
        reason="Role removed",
        **_request_meta(request),
    )
    await session.commit()
    return {"ok": True}


@router.get("/users/{user_id}/overrides", dependencies=[Depends(require("roles.view"))])
async def list_overrides(user_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict:
    user = await _get_user(session, user_id)
    rows = (
        (
            await session.execute(
                select(UserPermissionOverride)
                .where(UserPermissionOverride.user_id == user.id)
                .order_by(UserPermissionOverride.permission)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "permission": row.permission,
                "scope": row.scope,
                "effect": row.effect,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "reason": row.reason,
            }
            for row in rows
        ],
        "next_cursor": None,
    }


@router.post("/users/{user_id}/overrides", status_code=201, dependencies=[Depends(require("roles.manage"))])
async def upsert_override(
    user_id: uuid.UUID,
    payload: OverrideCreate,
    request: Request,
    principal: Principal = Depends(require("roles.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await _get_user(session, user_id)
    scope = "all" if payload.effect == "deny" else payload.scope
    declared = _declared(request)
    if payload.permission not in declared:
        raise ValidationFailed(
            f"Unknown permission: {payload.permission}",
            code="UNKNOWN_PERMISSION",
            message_key="error.unknown_permission",
            details={"permission": payload.permission},
        )
    if payload.effect != "deny":
        _validate_pairs(declared, [(payload.permission, scope)])
    _assert_grantable(principal, [(payload.permission, scope)])

    expires_at = payload.expires_at
    if expires_at is not None:
        aware = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        if aware <= datetime.now(UTC):
            raise ValidationFailed(
                "The expiry must be in the future",
                code="INVALID_EXPIRY",
                message_key="error.invalid_expiry",
            )
        expires_at = aware

    row = (
        await session.execute(
            select(UserPermissionOverride).where(
                UserPermissionOverride.user_id == user.id,
                UserPermissionOverride.permission == payload.permission,
                UserPermissionOverride.scope == scope,
            )
        )
    ).scalar_one_or_none()
    before = None
    if row is None:
        row = UserPermissionOverride(
            user_id=user.id,
            permission=payload.permission,
            scope=scope,
            effect=payload.effect,
        )
        session.add(row)
    else:
        before = {
            "effect": row.effect,
            "scope": row.scope,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "reason": row.reason,
        }
    row.effect = payload.effect
    row.expires_at = expires_at
    row.reason = payload.reason
    row.granted_by = uuid.UUID(principal.actor_id) if principal.actor_type == "user" else None
    await session.flush()
    after = {
        "effect": row.effect,
        "scope": row.scope,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "reason": row.reason,
    }
    await record(
        session,
        action="rbac.user.override_set",
        module="core",
        entity_type="user",
        entity_id=str(user.id),
        before=before,
        after={"permission": row.permission, **after},
        actor=principal,
        via=principal.via,
        reason=payload.reason,
        **_request_meta(request),
    )
    await session.commit()
    return {"id": str(row.id), "permission": row.permission, **after}


@router.delete(
    "/users/{user_id}/overrides/{override_id}",
    dependencies=[Depends(require("roles.manage"))],
)
async def delete_override(
    user_id: uuid.UUID,
    override_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require("roles.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await _get_user(session, user_id)
    row = await session.get(UserPermissionOverride, override_id)
    if row is None or row.user_id != user.id:
        raise NotFound("That override does not exist", message_key="error.override_not_found")
    _assert_grantable(principal, [(row.permission, row.scope)])
    before = {
        "permission": row.permission,
        "scope": row.scope,
        "effect": row.effect,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }
    await session.delete(row)
    await record(
        session,
        action="rbac.user.override_cleared",
        module="core",
        entity_type="user",
        entity_id=str(user.id),
        before=before,
        actor=principal,
        via=principal.via,
        reason="Permission override cleared",
        **_request_meta(request),
    )
    await session.commit()
    return {"ok": True}
