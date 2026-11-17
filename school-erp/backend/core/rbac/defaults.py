"""Shipped default roles (ARCH §5.3, P1-06).

These are *starting points*, not protected definitions: a school may rename,
re-scope, deactivate or re-permission any of them through the RBAC API. The
bootstrap step only creates a role when it is missing, so local edits survive
restarts. The demo seed deliberately resets them (`reset_permissions=True`) so
the owner always starts from the documented matrix.

Permission codes for modules that are not installed yet are simply skipped: the
list is intersected with the codes the loaded manifests declare.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.modules.registry import ModuleRegistry
from core.rbac.models import Role, RolePermission
from core.rbac.scopes import ALL
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class DefaultRole:
    key: str
    name: str
    description: str
    permissions: tuple[str, ...] = ()
    require_totp: bool = False
    scoped: dict[str, str] = field(default_factory=dict)

    def pairs(self) -> list[tuple[str, str]]:
        pairs = [(code, ALL) for code in self.permissions]
        pairs.extend(self.scoped.items())
        return pairs


DEFAULT_ROLES: tuple[DefaultRole, ...] = (
    DefaultRole(
        key="super_admin",
        name="Super Admin",
        description="Owns the instance: every module, role, setting and audit trail.",
        permissions=("*",),
    ),
    DefaultRole(
        key="director",
        name="Director",
        description="Runs the school: approvals, reports, settings and staffing.",
        permissions=(
            "users.view",
            "roles.view",
            "modules.view",
            "custom_fields.view",
            "custom_fields.manage",
            "audit.activity.view",
            "audit.rollback",
            "i18n.view",
            "i18n.manage",
            "themes.view",
            "jobs.view",
            "settings.view",
            "settings.manage",
            "ai.use",
            "sample.notes.view",
            "sample.notes.create",
        ),
    ),
    DefaultRole(
        key="academic_head",
        name="Academic Head",
        description="Owns academic structure, grade rules and mark approval.",
        permissions=(
            "users.view",
            "roles.view",
            "modules.view",
            "audit.activity.view",
            "i18n.view",
            "jobs.view",
            "custom_fields.view",
            "settings.view",
            "ai.use",
            "sample.notes.view",
            "sample.notes.create",
        ),
    ),
    DefaultRole(
        key="department_head",
        name="Department Head",
        description="Leads a department: reviews its staff and results.",
        permissions=(
            "users.view",
            "audit.activity.view",
            "ai.use",
            "sample.notes.view",
            "sample.notes.create",
        ),
    ),
    DefaultRole(
        key="registrar",
        name="Registrar",
        description="Admissions, student records, guardians and documents.",
        permissions=(
            "users.view",
            "users.manage",
            "people.view",
            "people.manage",
            "custom_fields.view",
            "custom_fields.manage",
            "roles.view",
            "audit.activity.view",
            "ai.use",
            "sample.notes.view",
        ),
    ),
    DefaultRole(
        key="teacher",
        name="Teacher",
        description="Teaches assigned subjects and sections; enters marks and attendance.",
        permissions=("ai.use", "sample.notes.view", "sample.notes.create"),
    ),
    DefaultRole(
        key="homeroom_teacher",
        name="Homeroom Teacher",
        description="A teacher who also owns one section's records and guardians.",
        permissions=(
            "users.view",
            "ai.use",
            "sample.notes.view",
            "sample.notes.create",
        ),
    ),
    DefaultRole(
        key="accountant",
        name="Accountant",
        description="Fees, invoices, payments, receipts and arrears.",
        permissions=("ai.use", "sample.notes.view"),
    ),
    DefaultRole(
        key="hr_officer",
        name="HR Officer",
        description="Staff records, contracts, leave and payroll inputs.",
        permissions=("users.view", "ai.use", "sample.notes.view"),
    ),
    DefaultRole(
        key="librarian",
        name="Librarian",
        description="Library catalogue, borrowing and fines.",
        permissions=("ai.use", "sample.notes.view"),
    ),
    DefaultRole(
        key="parent",
        name="Parent",
        description="Sees their own children's published information only.",
        permissions=("ai.use",),
    ),
    DefaultRole(
        key="student",
        name="Student",
        description="Sees their own published results, timetable and documents.",
        permissions=("ai.use",),
    ),
)


def declared_pairs(role: DefaultRole, declared: set[str]) -> list[tuple[str, str]]:
    """Intersect the shipped role with installed permissions.

    The wildcard role keeps ``*``; every other unknown code is dropped.
    """
    result: list[tuple[str, str]] = []
    for permission, scope in role.pairs():
        if permission == "*":
            result.append((permission, scope))
        elif permission in declared:
            result.append((permission, scope))
    return sorted(set(result))


async def ensure_default_roles(
    session: AsyncSession,
    registry: ModuleRegistry,
    *,
    reset_permissions: bool = False,
) -> list[Role]:
    """Create any missing shipped role without overwriting local edits.

    Bootstrap runs with ``reset_permissions=False``: an existing role keeps its
    name, active flag and permission set. The demo seed passes ``True`` so the
    documented matrix is restored deterministically on every reset. Permission
    codes that the loaded manifests do not declare are skipped, which also makes
    the operation safe before optional modules are installed.
    """
    declared = {item["code"] for item in registry.permissions()}
    roles: list[Role] = []
    for spec in DEFAULT_ROLES:
        role = (await session.execute(select(Role).where(Role.key == spec.key))).scalar_one_or_none()
        created = role is None
        if role is None:
            role = Role(
                key=spec.key,
                name=spec.name,
                description=spec.description,
                is_system=True,
                is_active=True,
                require_totp=spec.require_totp,
            )
            session.add(role)
            await session.flush()
        elif reset_permissions:
            role.name = spec.name
            role.description = spec.description
            role.is_system = True
            role.is_active = True
            role.require_totp = spec.require_totp

        if created or reset_permissions:
            if reset_permissions:
                await session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
            for permission, scope in declared_pairs(spec, declared):
                session.add(RolePermission(role_id=role.id, permission=permission, scope=scope))
        roles.append(role)

    await session.flush()
    return roles


__all__ = ["DEFAULT_ROLES", "DefaultRole", "declared_pairs", "ensure_default_roles"]
