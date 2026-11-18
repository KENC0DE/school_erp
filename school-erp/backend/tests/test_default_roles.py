"""P1-06: shipped default roles are seeded, editable and reset on demand."""

from __future__ import annotations

from core.bootstrap import bootstrap
from core.rbac.defaults import (
    DEFAULT_ROLES,
    DefaultRole,
    declared_pairs,
    ensure_default_roles,
)
from core.rbac.models import Role
from sqlalchemy import func, select

RBAC = "/api/v1/rbac"

DEFAULT_KEYS = {
    "super_admin",
    "director",
    "academic_head",
    "department_head",
    "registrar",
    "teacher",
    "homeroom_teacher",
    "accountant",
    "hr_officer",
    "librarian",
    "parent",
    "student",
}


def test_declared_pairs_intersects_unknown_codes_and_keeps_wildcard() -> None:
    role = DefaultRole(
        key="probe",
        name="Probe",
        description="",
        permissions=("sample.notes.view", "future.module.view", "*"),
    )
    assert declared_pairs(role, {"sample.notes.view"}) == [
        ("*", "all"),
        ("sample.notes.view", "all"),
    ]


async def _roles(client, headers) -> dict[str, dict]:
    response = await client.get(f"{RBAC}/roles", headers=headers)
    assert response.status_code == 200, response.text
    return {item["key"]: item for item in response.json()["items"]}


async def test_all_default_roles_are_seeded_with_declared_permissions(
    client, app, superadmin_headers
) -> None:
    roles = await _roles(client, superadmin_headers)
    assert DEFAULT_KEYS <= set(roles)

    declared = {item["code"] for item in app.state.registry.permissions()}
    for key in DEFAULT_KEYS:
        role = roles[key]
        assert role["is_system"] is True
        assert role["is_active"] is True
        assert role["description"]
        for grant in role["permissions"]:
            assert grant["permission"] == "*" or grant["permission"] in declared

    # Seeded roles never force 2FA on a fresh instance; the Super Admin enables
    # it per role after the first login (a locked-out owner is unrecoverable).
    assert roles["super_admin"]["require_totp"] is False
    assert roles["super_admin"]["permissions"] == [{"permission": "*", "scope": "all"}]
    assert roles["teacher"]["permissions"] == [
        {"permission": "academics.view", "scope": "all"},
        {"permission": "ai.use", "scope": "all"},
        {"permission": "attendance.record", "scope": "assigned_subjects"},
        {"permission": "attendance.view", "scope": "assigned_subjects"},
        {"permission": "sample.notes.create", "scope": "all"},
        {"permission": "sample.notes.view", "scope": "all"},
        {"permission": "staff.attendance.view", "scope": "self"},
        {"permission": "staff.leave.request", "scope": "self"},
        {"permission": "staff.leave.view", "scope": "self"},
        {"permission": "students.view", "scope": "assigned_subjects"},
    ]


async def test_default_role_can_be_renamed_repermissioned_and_deactivated(client, superadmin_headers) -> None:
    roles = await _roles(client, superadmin_headers)
    director = roles["director"]

    renamed = await client.patch(
        f"{RBAC}/roles/{director['id']}",
        headers=superadmin_headers,
        json={"name": "Head of School", "description": "Locally renamed role"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Head of School"

    replaced = await client.put(
        f"{RBAC}/roles/{director['id']}/permissions",
        headers=superadmin_headers,
        json={"permissions": [{"permission": "sample.notes.view", "scope": "all"}]},
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["permissions"] == [{"permission": "sample.notes.view", "scope": "all"}]

    deactivated = await client.delete(f"{RBAC}/roles/{director['id']}", headers=superadmin_headers)
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False

    roles = await _roles(client, superadmin_headers)
    assert roles["director"]["name"] == "Head of School"
    assert roles["director"]["is_active"] is False


async def test_bootstrap_preserves_local_edits(client, app, superadmin_headers) -> None:
    roles = await _roles(client, superadmin_headers)
    librarian = roles["librarian"]

    renamed = await client.patch(
        f"{RBAC}/roles/{librarian['id']}",
        headers=superadmin_headers,
        json={"name": "Library Lead"},
    )
    assert renamed.status_code == 200, renamed.text
    replaced = await client.put(
        f"{RBAC}/roles/{librarian['id']}/permissions",
        headers=superadmin_headers,
        json={"permissions": [{"permission": "ai.use", "scope": "all"}]},
    )
    assert replaced.status_code == 200, replaced.text

    await bootstrap(app)
    await bootstrap(app)

    roles = await _roles(client, superadmin_headers)
    assert roles["librarian"]["name"] == "Library Lead"
    assert roles["librarian"]["permissions"] == [{"permission": "ai.use", "scope": "all"}]
    assert DEFAULT_KEYS <= set(roles)
    async with app.state.db.session() as session:
        count = (
            await session.execute(select(func.count()).select_from(Role).where(Role.key == "librarian"))
        ).scalar_one()
    assert count == 1


async def test_reset_permissions_restores_the_shipped_matrix(client, app, superadmin_headers) -> None:
    roles = await _roles(client, superadmin_headers)
    teacher = roles["teacher"]
    edited = await client.put(
        f"{RBAC}/roles/{teacher['id']}/permissions",
        headers=superadmin_headers,
        json={"permissions": []},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["permissions"] == []

    async with app.state.db.session() as session:
        await ensure_default_roles(session, app.state.registry, reset_permissions=True)
        await session.commit()

    roles = await _roles(client, superadmin_headers)
    assert roles["teacher"]["permissions"] == [
        {"permission": "academics.view", "scope": "all"},
        {"permission": "ai.use", "scope": "all"},
        {"permission": "attendance.record", "scope": "assigned_subjects"},
        {"permission": "attendance.view", "scope": "assigned_subjects"},
        {"permission": "sample.notes.create", "scope": "all"},
        {"permission": "sample.notes.view", "scope": "all"},
        {"permission": "staff.attendance.view", "scope": "self"},
        {"permission": "staff.leave.request", "scope": "self"},
        {"permission": "staff.leave.view", "scope": "self"},
        {"permission": "students.view", "scope": "assigned_subjects"},
    ]
    assert roles["teacher"]["name"] == "Teacher"
    assert len(DEFAULT_ROLES) == len(DEFAULT_KEYS)
