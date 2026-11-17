"""P1-07: invite, deactivate and role assignment for users."""

from __future__ import annotations

from core.audit.models import AuditLog
from sqlalchemy import select

from tests.conftest import create_role, create_user, login, unique_email

AUTH = "/api/v1/auth"
RBAC = "/api/v1/rbac"


async def _roles(client, headers) -> dict[str, dict]:
    response = await client.get(f"{RBAC}/roles", headers=headers)
    assert response.status_code == 200, response.text
    return {item["key"]: item for item in response.json()["items"]}


async def _user_id(client, headers, email: str) -> str:
    response = await client.get(f"{AUTH}/users", headers=headers)
    assert response.status_code == 200, response.text
    return next(item["id"] for item in response.json()["items"] if item["email"] == email)


async def _actions(app) -> set[str]:
    async with app.state.db.session() as session:
        return set((await session.execute(select(AuditLog.action))).scalars().all())


async def test_invite_user_sends_link_assigns_roles_and_audits(client, app, superadmin_headers) -> None:
    roles = await _roles(client, superadmin_headers)
    email = unique_email("invitee")
    response = await client.post(
        f"{AUTH}/users",
        headers=superadmin_headers,
        json={
            "email": email,
            "display_name": "Invited Teacher",
            "phone": "+251900000001",
            "role_ids": [roles["teacher"]["id"]],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == email
    assert body["roles"] == ["teacher"]
    assert body["must_change_password"] is True
    assert body["invitation_sent"] is True
    assert "/reset-password?token=" in body["invitation_link"]

    assert app.state.mailer.outbox[-1].to == email
    assert "reset-password?token=" in app.state.mailer.outbox[-1].body

    listed = await client.get(f"{AUTH}/users", headers=superadmin_headers)
    row = next(item for item in listed.json()["items"] if item["email"] == email)
    assert row["roles"] == ["teacher"]
    assert row["is_active"] is True

    # Duplicate addresses and phone numbers are rejected.
    duplicate = await client.post(
        f"{AUTH}/users",
        headers=superadmin_headers,
        json={"email": email, "display_name": "Again"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"
    phone_duplicate = await client.post(
        f"{AUTH}/users",
        headers=superadmin_headers,
        json={"email": unique_email("phone"), "display_name": "Again", "phone": "+251900000001"},
    )
    assert phone_duplicate.status_code == 409

    assert "auth.user.invited" in await _actions(app)


async def test_invite_with_roles_requires_roles_manage_and_grantable_permissions(
    client, app, superadmin_headers
) -> None:
    await create_role(
        app,
        "user_admin",
        [("users.view", "all"), ("users.manage", "all")],
    )
    await create_user(app, "useradmin@demo.school", roles=["user_admin"])
    user_headers = await login(client, "useradmin@demo.school")
    roles = await _roles(client, superadmin_headers)

    denied = await client.post(
        f"{AUTH}/users",
        headers=user_headers,
        json={
            "email": unique_email("needs_roles"),
            "display_name": "Needs Roles",
            "role_ids": [roles["teacher"]["id"]],
        },
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

    await create_role(
        app,
        "role_admin2",
        [
            ("users.view", "all"),
            ("users.manage", "all"),
            ("roles.view", "all"),
            ("roles.manage", "all"),
        ],
    )
    await create_user(app, "roleadmin2@demo.school", roles=["role_admin2"])
    role_headers = await login(client, "roleadmin2@demo.school")

    cannot_grant = await client.post(
        f"{AUTH}/users",
        headers=role_headers,
        json={
            "email": unique_email("cannot_grant"),
            "display_name": "Cannot Grant",
            "role_ids": [roles["teacher"]["id"]],
        },
    )
    assert cannot_grant.status_code == 403
    assert cannot_grant.json()["error"]["code"] == "CANNOT_GRANT"

    # A user can still be invited without roles by a users.manage holder.
    plain = await client.post(
        f"{AUTH}/users",
        headers=user_headers,
        json={"email": unique_email("plain"), "display_name": "Plain Invite"},
    )
    assert plain.status_code == 201, plain.text
    assert plain.json()["roles"] == []


async def test_deactivation_revokes_sessions_and_blocks_login(
    client, app, seeded, superadmin_headers
) -> None:
    email = unique_email("deactivate")
    await create_user(app, email, roles=["limited"])
    user_headers = await login(client, email)
    user_id = await _user_id(client, superadmin_headers, email)

    deactivated = await client.patch(
        f"{AUTH}/users/{user_id}",
        headers=superadmin_headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False

    me = await client.get(f"{AUTH}/me", headers=user_headers)
    assert me.status_code == 401
    relogin = await client.post(f"{AUTH}/login", json={"email": email, "password": "DevPass#2026"})
    assert relogin.status_code == 401

    reactivated = await client.patch(
        f"{AUTH}/users/{user_id}",
        headers=superadmin_headers,
        json={"is_active": True},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True
    assert (await login(client, email))["Authorization"].startswith("Bearer ")

    assert "auth.user.updated" in await _actions(app)


async def test_cannot_deactivate_your_own_account(client, superadmin_headers) -> None:
    me = await client.get(f"{AUTH}/me", headers=superadmin_headers)
    response = await client.patch(
        f"{AUTH}/users/{me.json()['id']}",
        headers=superadmin_headers,
        json={"is_active": False},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CANNOT_DEACTIVATE_SELF"


async def test_navigation_reveals_users_and_roles_only_with_permission(client, seeded) -> None:
    super_headers = await login(client, "superadmin@demo.school")
    manager_headers = await login(client, "manager@demo.school")
    limited_headers = await login(client, "limited@demo.school")

    super_nav = await client.get(f"{AUTH}/me/navigation", headers=super_headers)
    super_keys = {item["key"] for item in super_nav.json()["items"]}
    assert {"users", "roles", "settings"} <= super_keys

    manager_nav = await client.get(f"{AUTH}/me/navigation", headers=manager_headers)
    manager_keys = {item["key"] for item in manager_nav.json()["items"]}
    assert "users" in manager_keys
    assert "roles" not in manager_keys

    limited_nav = await client.get(f"{AUTH}/me/navigation", headers=limited_headers)
    limited_keys = {item["key"] for item in limited_nav.json()["items"]}
    assert "users" not in limited_keys
    assert "roles" not in limited_keys
    assert "settings" not in limited_keys
