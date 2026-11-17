"""P1-05: scoped RBAC, management APIs, delegation and the route × role matrix."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.errors import Forbidden
from core.audit.models import AuditLog
from core.auth.models import User
from core.auth.principal import Principal
from core.rbac.models import Role, UserPermissionOverride
from core.rbac.service import effective_permissions, holds, roles_for_user
from fastapi.routing import APIRoute
from sqlalchemy import select
from starlette.requests import Request

from tests.conftest import DEV_PASSWORD, create_role, create_user, login, unique_email

RBAC = "/api/v1/rbac"


def _fake_request(method: str = "GET", path: str = "/api/v1/test") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "state": {},
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
        }
    )


async def _user_id(app, email: str) -> str:
    async with app.state.db.session() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        return str(user.id)


async def _principal(app, email: str) -> Principal:
    async with app.state.db.session() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        permissions, scopes = await effective_permissions(session, user.id)
        roles = await roles_for_user(session, user.id)
    return Principal(
        actor_id=str(user.id),
        email=user.email,
        roles=roles,
        permissions=permissions,
        scopes=scopes,
    )


def _guards(dependant) -> list:
    found = []
    call = getattr(dependant, "call", None)
    if call is not None and getattr(call, "__permission__", None):
        found.append(call)
    for child in dependant.dependencies:
        found.extend(_guards(child))
    return found


# ---------------------------------------------------------------- scope checks


def test_scopes_narrow_a_permission():
    own_class = Principal(
        actor_id="u1",
        permissions={"assessment.marks.enter"},
        scopes={"assessment.marks.enter": {"own_class"}},
    )
    assert own_class.can("assessment.marks.enter")
    assert own_class.can("assessment.marks.enter", "own_class")
    assert not own_class.can("assessment.marks.enter", "all")
    assert not own_class.can("assessment.marks.enter", "department")

    broad = Principal(
        actor_id="u2",
        permissions={"assessment.marks.enter"},
        scopes={"assessment.marks.enter": {"all"}},
    )
    assert broad.can("assessment.marks.enter", "own_class")
    assert broad.can("assessment.marks.enter", "department")


def test_prefix_wildcards_and_holds():
    wildcard = Principal(
        actor_id="u1",
        permissions={"sample.*"},
        scopes={"sample.*": {"all"}},
    )
    assert wildcard.can("sample.notes.view")
    assert wildcard.can("sample.notes.create", "all")

    manager = Principal(
        actor_id="u2",
        permissions={"sample.notes.view"},
        scopes={"sample.notes.view": {"own_class"}},
    )
    assert holds(manager, "sample.notes.view", "own_class")
    assert not holds(manager, "sample.notes.view", "all")
    assert not holds(manager, "sample.notes.create", "all")


# ------------------------------------------------------------ effective access


async def test_denies_win_expiry_and_multiple_roles(app):
    await create_role(app, "reader", [("sample.notes.view", "all")])
    await create_role(app, "writer", [("sample.notes.create", "all")])
    email = unique_email("multi")
    await create_user(app, email, roles=["reader", "writer"])
    user_id = uuid.UUID(await _user_id(app, email))

    async with app.state.db.session() as session:
        permissions, scopes = await effective_permissions(session, user_id)
        assert permissions == {"sample.notes.view", "sample.notes.create"}
        assert scopes["sample.notes.view"] == {"all"}

        # An expired deny is ignored.
        session.add(
            UserPermissionOverride(
                user_id=user_id,
                permission="sample.notes.view",
                scope="all",
                effect="deny",
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        await session.commit()
    async with app.state.db.session() as session:
        permissions, _ = await effective_permissions(session, user_id)
        assert "sample.notes.view" in permissions

        # A live deny wins even though a role grants the permission.
        row = (
            await session.execute(
                select(UserPermissionOverride).where(
                    UserPermissionOverride.user_id == user_id,
                    UserPermissionOverride.permission == "sample.notes.view",
                )
            )
        ).scalar_one()
        row.expires_at = datetime.now(UTC) + timedelta(hours=1)
        await session.commit()
    async with app.state.db.session() as session:
        permissions, scopes = await effective_permissions(session, user_id)
        assert "sample.notes.view" not in permissions
        assert "sample.notes.view" not in scopes
        assert "sample.notes.create" in permissions

        # A future grant is a delegated permission; an expired one is not.
        session.add(
            UserPermissionOverride(
                user_id=user_id,
                permission="sample.notes.create",
                scope="own_class",
                effect="deny",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        session.add(
            UserPermissionOverride(
                user_id=user_id,
                permission="users.view",
                scope="all",
                effect="grant",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        await session.commit()
    async with app.state.db.session() as session:
        permissions, scopes = await effective_permissions(session, user_id)
        assert "sample.notes.create" not in permissions
        assert "users.view" in permissions
        assert scopes["users.view"] == {"all"}


async def test_inactive_roles_contribute_nothing(app):
    await create_role(app, "temp_role", [("sample.notes.view", "all")])
    email = unique_email("inactive")
    await create_user(app, email, roles=["temp_role"])
    user_id = uuid.UUID(await _user_id(app, email))
    async with app.state.db.session() as session:
        role = (await session.execute(select(Role).where(Role.key == "temp_role"))).scalar_one()
        role.is_active = False
        await session.commit()
    async with app.state.db.session() as session:
        permissions, _ = await effective_permissions(session, user_id)
        assert permissions == set()
        assert await roles_for_user(session, user_id) == []


# ------------------------------------------------------------- management API


async def test_role_crud_validation_and_cannot_grant_unheld(client, app, seeded):
    headers = await login(client, "superadmin@demo.school")

    created = await client.post(
        f"{RBAC}/roles",
        headers=headers,
        json={
            "key": "assistant",
            "name": "Assistant",
            "permissions": [{"permission": "sample.notes.view", "scope": "all"}],
        },
    )
    assert created.status_code == 201, created.text
    role = created.json()
    assert role["key"] == "assistant"
    assert role["permissions"] == [{"permission": "sample.notes.view", "scope": "all"}]

    duplicate = await client.post(
        f"{RBAC}/roles",
        headers=headers,
        json={"key": "assistant", "name": "Again"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"

    unknown = await client.post(
        f"{RBAC}/roles",
        headers=headers,
        json={
            "key": "bad_perm",
            "name": "Bad",
            "permissions": [{"permission": "does.not.exist", "scope": "all"}],
        },
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "UNKNOWN_PERMISSION"

    bad_scope = await client.post(
        f"{RBAC}/roles",
        headers=headers,
        json={
            "key": "bad_scope",
            "name": "Bad scope",
            "permissions": [{"permission": "sample.notes.view", "scope": "own_class"}],
        },
    )
    assert bad_scope.status_code == 422
    assert bad_scope.json()["error"]["code"] == "INVALID_SCOPE"

    # A role manager without sample.notes.view cannot hand it out.
    await create_role(
        app,
        "role_admin",
        [("roles.view", "all"), ("roles.manage", "all")],
    )
    await create_user(app, "roleadmin@demo.school", roles=["role_admin"])
    role_admin_headers = await login(client, "roleadmin@demo.school")

    escalation = await client.post(
        f"{RBAC}/roles",
        headers=role_admin_headers,
        json={
            "key": "escalated",
            "name": "Escalated",
            "permissions": [{"permission": "sample.notes.view", "scope": "all"}],
        },
    )
    assert escalation.status_code == 403
    assert escalation.json()["error"]["code"] == "CANNOT_GRANT"

    empty = await client.post(
        f"{RBAC}/roles",
        headers=role_admin_headers,
        json={"key": "empty", "name": "Empty"},
    )
    assert empty.status_code == 201


async def test_assignments_overrides_and_me(client, app, seeded):
    headers = await login(client, "superadmin@demo.school")
    email = unique_email("delegate")
    await create_user(app, email, roles=["limited"])
    user_id = await _user_id(app, email)
    user_headers = await login(client, email, DEV_PASSWORD)

    created = await client.post(
        f"{RBAC}/roles",
        headers=headers,
        json={
            "key": "delegated_reader",
            "name": "Delegated reader",
            "permissions": [{"permission": "sample.notes.view", "scope": "all"}],
        },
    )
    assert created.status_code == 201
    role_id = created.json()["id"]

    assigned = await client.post(
        f"{RBAC}/users/{user_id}/roles",
        headers=headers,
        json={"role_id": role_id},
    )
    assert assigned.status_code == 201, assigned.text

    me = await client.get("/api/v1/auth/me", headers=user_headers)
    assert "delegated_reader" in me.json()["roles"]
    assert "sample.notes.view" in me.json()["permissions"]
    assert me.json()["scopes"]["sample.notes.view"] == ["all"]

    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    granted = await client.post(
        f"{RBAC}/users/{user_id}/overrides",
        headers=headers,
        json={
            "permission": "sample.notes.create",
            "scope": "all",
            "effect": "grant",
            "expires_at": future,
            "reason": "Covering for a colleague",
        },
    )
    assert granted.status_code == 201, granted.text
    grant_id = granted.json()["id"]

    denied = await client.post(
        f"{RBAC}/users/{user_id}/overrides",
        headers=headers,
        json={
            "permission": "sample.notes.view",
            "scope": "all",
            "effect": "deny",
            "reason": "Temporarily suspended",
        },
    )
    assert denied.status_code == 201, denied.text

    me = await client.get("/api/v1/auth/me", headers=user_headers)
    permissions = me.json()["permissions"]
    assert "sample.notes.create" in permissions
    assert "sample.notes.view" not in permissions

    listed = await client.get(f"{RBAC}/users/{user_id}/overrides", headers=headers)
    assert len(listed.json()["items"]) == 2

    details = await client.get(f"{RBAC}/users/{user_id}/permissions", headers=headers)
    body = details.json()
    assert body["roles"] == ["delegated_reader", "limited"]
    assert "sample.notes.view" not in body["effective"]["permissions"]
    assert any(item["effect"] == "deny" for item in body["overrides"])

    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    expired = await client.post(
        f"{RBAC}/users/{user_id}/overrides",
        headers=headers,
        json={
            "permission": "users.view",
            "scope": "all",
            "effect": "grant",
            "expires_at": past,
        },
    )
    assert expired.status_code == 422
    assert expired.json()["error"]["code"] == "INVALID_EXPIRY"

    cleared = await client.delete(f"{RBAC}/users/{user_id}/overrides/{grant_id}", headers=headers)
    assert cleared.status_code == 200
    me = await client.get("/api/v1/auth/me", headers=user_headers)
    assert "sample.notes.create" not in me.json()["permissions"]

    deactivated = await client.patch(f"{RBAC}/roles/{role_id}", headers=headers, json={"is_active": False})
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    me = await client.get("/api/v1/auth/me", headers=user_headers)
    assert "delegated_reader" not in me.json()["roles"]

    actions = await _audit_actions(app)
    assert {
        "rbac.role.create",
        "rbac.user.role_assigned",
        "rbac.user.override_set",
        "rbac.user.override_cleared",
        "rbac.role.update",
    } <= actions


async def _audit_actions(app) -> set[str]:
    async with app.state.db.session() as session:
        rows = (await session.execute(select(AuditLog.action))).scalars().all()
    return set(rows)


async def test_cannot_assign_a_role_you_could_not_grant(client, app, seeded):
    await create_role(app, "role_admin2", [("roles.view", "all"), ("roles.manage", "all")])
    await create_user(app, "roleadmin2@demo.school", roles=["role_admin2"])
    admin_headers = await login(client, "roleadmin2@demo.school")
    super_headers = await login(client, "superadmin@demo.school")
    email = unique_email("victim")
    await create_user(app, email, roles=["limited"])
    user_id = await _user_id(app, email)

    roles = await client.get(f"{RBAC}/roles", headers=super_headers)
    super_admin_role = next(item for item in roles.json()["items"] if item["key"] == "super_admin")

    forbidden = await client.post(
        f"{RBAC}/users/{user_id}/roles",
        headers=admin_headers,
        json={"role_id": super_admin_role["id"]},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "CANNOT_GRANT"


# --------------------------------------------------------------- route × role


async def test_permission_matrix_covers_every_route_and_seeded_role(app, seeded):
    declared = {item["code"] for item in app.state.registry.permissions()}
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    seeded = {
        "super_admin": "superadmin@demo.school",
        "limited": "limited@demo.school",
        "sample_manager": "manager@demo.school",
        "auditor": "auditor@demo.school",
    }
    principals = {role: await _principal(app, email) for role, email in seeded.items()}

    checked = 0
    for route in routes:
        if not route.path.startswith("/api/v1"):
            continue
        guards = _guards(route.dependant)
        for guard in guards:
            permission = guard.__permission__
            scope = guard.__scope__
            assert permission in declared, f"{route.path} declares unknown {permission}"
            for role, principal in principals.items():
                expected = principal.can(permission, scope)
                request = _fake_request(next(iter(route.methods)), route.path)
                try:
                    await guard(request, principal)
                except Forbidden:
                    allowed = False
                else:
                    allowed = True
                assert allowed == expected, (
                    f"{role} on {route.path} {permission}/{scope}: expected {expected}, got {allowed}"
                )
                checked += 1

    assert checked >= len(routes)
    # The matrix really has both outcomes for a narrow role.
    assert not principals["limited"].can("users.view")
    assert principals["auditor"].can("roles.view")


async def test_wildcard_permission_is_only_grantable_by_a_wildcard_holder(
    client, app, seeded, superadmin_headers
) -> None:
    roles = await client.get(f"{RBAC}/roles", headers=superadmin_headers)
    super_admin = next(item for item in roles.json()["items"] if item["key"] == "super_admin")
    kept = await client.put(
        f"{RBAC}/roles/{super_admin['id']}/permissions",
        headers=superadmin_headers,
        json={"permissions": [{"permission": "*", "scope": "all"}]},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["permissions"] == [{"permission": "*", "scope": "all"}]

    await create_role(app, "role_admin3", [("roles.view", "all"), ("roles.manage", "all")])
    await create_user(app, "roleadmin3@demo.school", roles=["role_admin3"])
    headers = await login(client, "roleadmin3@demo.school")
    own = next(
        item
        for item in (await client.get(f"{RBAC}/roles", headers=headers)).json()["items"]
        if item["key"] == "role_admin3"
    )
    denied = await client.put(
        f"{RBAC}/roles/{own['id']}/permissions",
        headers=headers,
        json={"permissions": [{"permission": "*", "scope": "all"}]},
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["error"]["code"] == "CANNOT_GRANT"
