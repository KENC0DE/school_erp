#!/usr/bin/env python3
"""Idempotent development seed for the school instance and the control plane.

Run through ``./scripts/dev.sh seed``. It refuses to touch any data when
``APP_ENV=production``. Both SQLite databases are written in-process (no running
server is required) and every entity is an upsert, so re-running is safe.

The demo school is licensed by signing a license with the controller's own
license key (the exact code path used by ``POST /controller/v1/enroll``) rather
than calling the HTTP endpoint. That keeps seeding deterministic and offline.
A canonical, one-time enrollment token is still provisioned so the real
enrollment flow can be exercised manually.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (
    REPO_ROOT / "shared" / "py",
    REPO_ROOT / "school-erp" / "backend",
    REPO_ROOT / "owner" / "controller-api",
):
    sys.path.insert(0, str(_path))

# Allow `./scripts/seed.py` to be run directly: re-exec with the workspace venv
# instead of dying on a bare system interpreter.
try:  # noqa: SIM105 - the fallback below explains the failure
    import sqlalchemy  # noqa: F401
except ModuleNotFoundError:
    for _candidate in (
        REPO_ROOT / ".venv" / "bin" / "python",
        REPO_ROOT / ".venv" / "Scripts" / "python.exe",
    ):
        if _candidate.exists() and _candidate.resolve() != Path(sys.executable).resolve():
            os.execv(str(_candidate), [str(_candidate), *sys.argv])
    print(
        "seed: SQLAlchemy is not installed. Run 'uv sync --all-packages' "
        "or set ERP_PYTHON to an interpreter with the backend dependencies.",
        file=sys.stderr,
    )
    raise SystemExit(1) from None

DEV_PASSWORD = "DevPass#2026"
DEMO_SCHOOL_CODE = "DEMO"
DEMO_SCHOOL_NAME = "Demo Academy"
DEMO_API_BASE_URL = "http://localhost:8000"
CANONICAL_ENROLLMENT_TOKEN = "dev-enroll-DEMO-2026"
# Modules enabled on the demo school. The controller signs this list into the
# license, so an addition here also proves the module gate end to end.
DEMO_MODULES: tuple[str, ...] = ("academics", "students", "sample")
# School-layer translation overrides. They prove the default < central < school
# precedence and give the activity history real i18n entries to show.
SCHOOL_I18N_OVERRIDES: tuple[tuple[str, str, str, str], ...] = (
    (
        "core",
        "dashboard.subtitle",
        "am",
        "ይህ ጽሑፍ በትምህርት ቤቱ ተተክቷል። (school override)",
    ),
    (
        "core",
        "app.tagline",
        "am",
        "ትምህርት ቤትዎን በግልጽ ያስተዳድሩ",
    ),
    (
        "core",
        "dashboard.welcome",
        "am",
        "እንኳን ደህና መጡ፣ {{name}}",
    ),
    (
        "core",
        "dashboard.language_hint",
        "am",
        "ቋንቋውን ቀይረው ተመሳሳዩን ገጽ በአማርኛ ይመልከቱ።",
    ),
)

# Two selectable themes prove that imported themes survive a reset and appear in
# the Theme Manager next to the builtin default. Colours are checked against the
# same WCAG contrast pairs as every imported theme.
DEMO_THEMES: tuple[dict, ...] = (
    {
        "key": "highlands",
        "name": "Highlands",
        "description": "Cool blue highlights inspired by the Ethiopian highlands.",
        "light": {
            "primary": "oklch(0.42 0.12 250)",
            "primary-foreground": "oklch(0.985 0 0)",
            "accent": "oklch(0.95 0.04 250)",
            "accent-foreground": "oklch(0.205 0 0)",
        },
        "dark": {
            "primary": "oklch(0.72 0.13 250)",
            "primary-foreground": "oklch(0.145 0 0)",
            "accent": "oklch(0.3 0.05 250)",
            "accent-foreground": "oklch(0.985 0 0)",
        },
        "radius": "0.75rem",
    },
    {
        "key": "sunset",
        "name": "Sunset",
        "description": "Warm amber highlights for a softer evening palette.",
        "light": {
            "primary": "oklch(0.48 0.12 60)",
            "primary-foreground": "oklch(0.985 0 0)",
            "accent": "oklch(0.95 0.05 60)",
            "accent-foreground": "oklch(0.205 0 0)",
        },
        "dark": {
            "primary": "oklch(0.75 0.14 60)",
            "primary-foreground": "oklch(0.145 0 0)",
            "accent": "oklch(0.32 0.06 60)",
            "accent-foreground": "oklch(0.985 0 0)",
        },
        "radius": "0.5rem",
    },
)

SAMPLE_NOTE = "Welcome to the demo school! This note was created by the seed."
SAMPLE_SETTING_KEY = "school_profile.name"


def fail(message: str, code: int = 1) -> None:
    print(f"seed: {message}", file=sys.stderr)
    raise SystemExit(code)


def _normalise_sqlite_url(url: str) -> str:
    """Make relative SQLite paths independent of the caller's working directory."""
    prefix = "sqlite+aiosqlite:///"
    if url.startswith(prefix):
        path = url[len(prefix) :]
        if path and not path.startswith("/"):
            path = str((REPO_ROOT / path).resolve())
        return f"{prefix}{path}"
    return url


async def seed_controller(controller_settings) -> dict:
    from controller_api.db import Database
    from controller_api.directory import token_hash
    from controller_api.keys import ensure_signing_keys
    from controller_api.licenses import issue_license
    from controller_api.models import (
        CPUser,
        EnrollmentToken,
        LicenseRecord,
        School,
    )
    from controller_api.security import hash_password, verify_password
    from sqlalchemy import select

    database = Database(controller_settings.controller_database_url)
    await database.create_all()
    summary: dict = {}
    try:
        async with database.session() as session:
            cp_users = [
                ("owner@controller.local", "Platform Owner", "owner"),
                ("support@controller.local", "Controller Support", "support"),
            ]
            for email, display_name, role in cp_users:
                user = (
                    await session.execute(select(CPUser).where(CPUser.email == email))
                ).scalar_one_or_none()
                if user is None:
                    user = CPUser(
                        email=email,
                        display_name=display_name,
                        role=role,
                        password_hash=hash_password(DEV_PASSWORD),
                        is_active=True,
                    )
                    session.add(user)
                else:
                    user.display_name = display_name
                    user.role = role
                    user.is_active = True
                    if not verify_password(DEV_PASSWORD, user.password_hash):
                        user.password_hash = hash_password(DEV_PASSWORD)
            await session.flush()

            school = (
                await session.execute(select(School).where(School.school_code == DEMO_SCHOOL_CODE))
            ).scalar_one_or_none()
            if school is None:
                school = School(
                    name=DEMO_SCHOOL_NAME,
                    school_code=DEMO_SCHOOL_CODE,
                    api_base_url=DEMO_API_BASE_URL,
                    status="active",
                    plan="standard",
                    modules=list(DEMO_MODULES),
                )
                session.add(school)
                await session.flush()
            school.name = DEMO_SCHOOL_NAME
            school.api_base_url = DEMO_API_BASE_URL
            school.status = "active"
            school.modules = sorted(set(school.modules or []) | set(DEMO_MODULES))

            license_key, directory_key = await ensure_signing_keys(session, controller_settings)

            # The canonical token is provisioned once. It is deliberately never
            # consumed by the seed; the first manual enrollment may use it.
            enrollment = (
                await session.execute(
                    select(EnrollmentToken).where(
                        EnrollmentToken.token_hash == token_hash(CANONICAL_ENROLLMENT_TOKEN)
                    )
                )
            ).scalar_one_or_none()
            enrollment_created = enrollment is None
            if enrollment is None:
                enrollment = EnrollmentToken(
                    school_id=school.id,
                    token_hash=token_hash(CANONICAL_ENROLLMENT_TOKEN),
                    expires_at=datetime.now(UTC) + timedelta(days=3650),
                )
                session.add(enrollment)
                await session.flush()

            # Reuse the latest still-valid license when the module list matches;
            # otherwise issue a fresh one (same function the enroll endpoint uses).
            latest = (
                (
                    await session.execute(
                        select(LicenseRecord)
                        .where(LicenseRecord.school_id == school.id)
                        .order_by(LicenseRecord.issued_at.desc())
                        .limit(1)
                    )
                )
                .scalars()
                .first()
            )
            latest_valid = (
                latest is not None
                and latest.valid_until is not None
                and (
                    latest.valid_until.replace(tzinfo=UTC)
                    if latest.valid_until.tzinfo is None
                    else latest.valid_until
                )
                > datetime.now(UTC) + timedelta(days=1)
                and sorted(latest.modules or []) == sorted(school.modules or [])
                and latest.status == school.status
            )
            license_token = (
                latest.token
                if latest_valid
                else await issue_license(session, school, license_key, controller_settings)
            )

            await session.commit()
            summary.update(
                {
                    "school_id": school.id,
                    "license_token": license_token,
                    "license_public_key": license_key.public_pem,
                    "directory_public_key": directory_key.public_pem,
                    "enrollment_token": CANONICAL_ENROLLMENT_TOKEN,
                    "enrollment_created": enrollment_created,
                    "enrollment_used": enrollment.used_at is not None,
                    "modules": list(school.modules or []),
                }
            )
    finally:
        await database.dispose()
    return summary


# Demo-only custom role, deliberately outside the shipped defaults. It proves
# that a school can add a role with a narrow permission set.
DEMO_LIMITED_PERMISSIONS = ("ai.use", "sample.notes.view")

DEMO_USERS: list[tuple[str, str, str]] = [
    ("superadmin@demo.school", "Super Admin", "super_admin"),
    ("director@demo.school", "Director", "director"),
    ("academichead@demo.school", "Academic Head", "academic_head"),
    ("registrar@demo.school", "Registrar", "registrar"),
    ("teacher1@demo.school", "Teacher One (Math, Grade 5)", "teacher"),
    ("teacher2@demo.school", "Teacher Two (English, Grade 6)", "teacher"),
    ("accountant@demo.school", "Accountant", "accountant"),
    ("hr@demo.school", "HR Officer", "hr_officer"),
    ("limited@demo.school", "Limited User", "limited"),
    ("parent1@demo.school", "Parent One", "parent"),
    ("student1@demo.school", "Student One", "student"),
]


def _demo_theme_tokens(spec: dict) -> dict:
    """Build a full token map from the shipped palette plus the demo accents."""
    from core.themes.tokens import DARK, LIGHT

    light = {**LIGHT, **spec["light"], "radius": spec["radius"]}
    dark = {**DARK, **spec["dark"], "radius": spec["radius"]}
    for values in (light, dark):
        values["sidebar-primary"] = values["primary"]
        values["sidebar-primary-foreground"] = values["primary-foreground"]
    return {"light": light, "dark": dark}


def _school_principal(user) -> object:
    """A Super Admin principal used to run audited service functions in the seed."""
    from core.auth.principal import Principal

    return Principal(
        actor_id=str(user.id),
        actor_type="user",
        via="api",
        display_name=user.display_name,
        email=user.email,
        roles=["super_admin"],
        permissions={"*"},
        scopes={"*": {"all"}},
    )


async def seed_school(school_settings, controller_summary: dict) -> dict:
    # Importing the app factory module registers every core and module ORM mapper
    # with Base.metadata, so create_all() makes every table the running server
    # expects (notifications, files, jobs, ...).
    import app.main  # noqa: F401
    from core.actions.registry import ActionContext
    from core.audit.service import record
    from core.auth.models import User
    from core.auth.security import hash_password, verify_password
    from core.controller_link.service import identity
    from core.db.session import Database
    from core.i18n.editor import set_entry
    from core.i18n.service import load_defaults
    from core.modules.licensing import apply_license, ensure_module_rows
    from core.modules.models import InstanceModule
    from core.modules.registry import ModuleRegistry
    from core.rbac.defaults import ensure_default_roles
    from core.rbac.models import Role, RolePermission, UserRole
    from core.settings.core_schema import CoreSettings
    from core.settings.models import INSTANCE, Setting
    from core.settings.service import set_setting
    from core.themes.importers import ImportedTheme
    from core.themes.models import Theme
    from core.themes.service import ensure_default_theme, import_theme
    from modules.sample.actions import create_note
    from modules.sample.models import SampleNote
    from sqlalchemy import delete, select

    registry = ModuleRegistry.load()
    declared = {item["code"] for item in registry.permissions()}

    database = Database(school_settings.database_url)
    await database.create_all()
    summary: dict = {}
    try:
        async with database.session() as session:
            await ensure_module_rows(session, registry)
            await load_defaults(session, registry)
            await ensure_default_theme(session)
            for manifest in registry.all():
                if manifest.bootstrap is not None:
                    await manifest.bootstrap(session)

            # The license module list is authoritative once a license exists.
            for module_key in DEMO_MODULES:
                school_module = await session.get(InstanceModule, module_key)
                if school_module is None:
                    school_module = InstanceModule(module_key=module_key, enabled=True)
                    session.add(school_module)
                else:
                    school_module.enabled = True
            await session.flush()

            # Restore the documented default matrix on every demo reset. Local
            # edits to *names* still survive a plain boot (bootstrap only
            # creates missing roles); this reset exists for the demo instance.
            role_rows = {
                role.key: role
                for role in await ensure_default_roles(session, registry, reset_permissions=True)
            }

            limited = (await session.execute(select(Role).where(Role.key == "limited"))).scalar_one_or_none()
            if limited is None:
                limited = Role(
                    key="limited",
                    name="Limited User",
                    description="Demo-only role with a deliberately narrow permission set.",
                    is_system=True,
                )
                session.add(limited)
                await session.flush()
            else:
                limited.name = "Limited User"
                limited.description = "Demo-only role with a deliberately narrow permission set."
                limited.is_system = True
                limited.is_active = True
            limited_permissions_changed: tuple[list[tuple[str, str]], list[tuple[str, str]]] | None = None
            desired_limited = {(code, "all") for code in sorted(set(DEMO_LIMITED_PERMISSIONS) & declared)}
            current_limited = {
                (row.permission, row.scope)
                for row in (
                    await session.execute(select(RolePermission).where(RolePermission.role_id == limited.id))
                )
                .scalars()
                .all()
            }
            if current_limited != desired_limited:
                limited_permissions_changed = (sorted(current_limited), sorted(desired_limited))
                await session.execute(delete(RolePermission).where(RolePermission.role_id == limited.id))
                for permission, scope in sorted(desired_limited):
                    session.add(RolePermission(role_id=limited.id, permission=permission, scope=scope))
            role_rows["limited"] = limited
            await session.flush()

            user_rows: dict[str, User] = {}
            role_changes: list[tuple[User, Role]] = []
            for email, display_name, role_key in DEMO_USERS:
                user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
                if user is None:
                    user = User(
                        email=email,
                        display_name=display_name,
                        password_hash=hash_password(DEV_PASSWORD),
                        locale="en",
                        is_active=True,
                    )
                    session.add(user)
                    await session.flush()
                else:
                    user.display_name = display_name
                    user.locale = "en"
                    user.is_active = True
                    if not verify_password(DEV_PASSWORD, user.password_hash):
                        user.password_hash = hash_password(DEV_PASSWORD)
                target_role = role_rows[role_key]
                current_roles = {
                    row.role_id
                    for row in (await session.execute(select(UserRole).where(UserRole.user_id == user.id)))
                    .scalars()
                    .all()
                }
                if current_roles != {target_role.id}:
                    await session.execute(delete(UserRole).where(UserRole.user_id == user.id))
                    session.add(UserRole(user_id=user.id, role_id=target_role.id))
                    role_changes.append((user, target_role))
                user_rows[email] = user
            await session.flush()

            superadmin = user_rows["superadmin@demo.school"]
            principal = _school_principal(superadmin)

            # Every change below goes through the audited service function, so a
            # fresh demo instance already has representative activity history.
            if limited_permissions_changed is not None:
                before, after = limited_permissions_changed
                await record(
                    session,
                    action="rbac.role.permissions",
                    module="core",
                    entity_type="role",
                    entity_id=str(limited.id),
                    before={"permissions": [f"{code}@{scope}" for code, scope in before]},
                    after={"permissions": [f"{code}@{scope}" for code, scope in after]},
                    actor=principal,
                    via="api",
                    reason="Demo seed limited role",
                )
            for user, role in role_changes:
                await record(
                    session,
                    action="rbac.user.role_assigned",
                    module="core",
                    entity_type="user",
                    entity_id=str(user.id),
                    after={"role": role.key, "role_id": str(role.id)},
                    actor=principal,
                    via="api",
                    reason="Demo seed role assignment",
                )
            await session.flush()

            for namespace, key, locale, value in SCHOOL_I18N_OVERRIDES:
                await set_entry(session, principal, namespace, key, locale, value)

            theme_created: list[str] = []
            for spec in DEMO_THEMES:
                tokens = _demo_theme_tokens(spec)
                existing = (
                    await session.execute(
                        select(Theme).where(Theme.key == spec["key"]).execution_options(include_deleted=True)
                    )
                ).scalar_one_or_none()
                if (
                    existing is not None
                    and existing.deleted_at is None
                    and existing.is_active
                    and existing.name == spec["name"]
                    and existing.tokens == tokens
                ):
                    continue
                await import_theme(
                    session,
                    principal,
                    ImportedTheme(
                        key=spec["key"],
                        name=spec["name"],
                        tokens=tokens,
                        source="json",
                    ),
                    description=spec["description"],
                )
                theme_created.append(spec["key"])

            setting_row = (
                await session.execute(
                    select(Setting).where(
                        Setting.layer == INSTANCE,
                        Setting.module == "core",
                        Setting.key == SAMPLE_SETTING_KEY,
                    )
                )
            ).scalar_one_or_none()
            if (
                setting_row is None
                or setting_row.deleted_at is not None
                or setting_row.value != DEMO_SCHOOL_NAME
            ):
                before = {"value": setting_row.value if setting_row else None}
                await set_setting(
                    session,
                    "core",
                    CoreSettings,
                    SAMPLE_SETTING_KEY,
                    DEMO_SCHOOL_NAME,
                    layer=INSTANCE,
                    actor=principal,
                )
                await record(
                    session,
                    action="settings.update",
                    module="core",
                    entity_type="setting",
                    entity_id=f"core.{SAMPLE_SETTING_KEY}",
                    before=before,
                    after={"value": DEMO_SCHOOL_NAME, "source": "instance"},
                    actor=principal,
                    via="api",
                )
                await session.flush()

            note = (
                (
                    await session.execute(
                        select(SampleNote).where(
                            SampleNote.content == SAMPLE_NOTE, SampleNote.deleted_at.is_(None)
                        )
                    )
                )
                .scalars()
                .first()
            )
            if note is None:
                note = await create_note(
                    ActionContext(principal=principal, session=session, via="api"),
                    {"content": SAMPLE_NOTE},
                )

            # Instance identity + license. Signing the license with the controller
            # key mirrors the enroll endpoint and avoids an HTTP dependency.
            inst = await identity(session)
            inst.enrolled_at = datetime.now(UTC)
            school_settings_identity = inst.public_key

            await apply_license(
                session,
                controller_summary["license_token"],
                controller_summary["license_public_key"],
                school_settings,
            )
            await session.commit()

            summary.update(
                {
                    "instance_id": controller_summary["school_id"],
                    "instance_public_key": school_settings_identity,
                    "roles": sorted(role_rows),
                    "users": [email for email, _, _ in DEMO_USERS],
                    "note_id": str(note.id),
                    "override_key": f"{SCHOOL_I18N_OVERRIDES[0][0]}.{SCHOOL_I18N_OVERRIDES[0][1]}",
                    "override_count": len(SCHOOL_I18N_OVERRIDES),
                    "themes": ["default", *(spec["key"] for spec in DEMO_THEMES)],
                    "themes_created": theme_created,
                    "licensed_modules": controller_summary["modules"],
                }
            )
    finally:
        await database.dispose()
    return summary


async def attach_instance(controller_settings, school_id: str, public_key: str, app_version: str) -> None:
    """Record the seeded instance key so real heartbeats verify after seeding."""
    from controller_api.db import Database
    from controller_api.models import School

    database = Database(controller_settings.controller_database_url)
    try:
        async with database.session() as session:
            school = await session.get(School, school_id)
            if school is None:
                return
            school.instance_public_key = public_key
            school.app_version = app_version
            await session.commit()
    finally:
        await database.dispose()


async def _run() -> int:
    if os.environ.get("APP_ENV", "").lower() == "production":
        fail("refusing to run with APP_ENV=production (demo credentials must never reach production)", 2)

    from app.settings import get_settings
    from controller_api.settings import get_controller_settings

    school_settings = get_settings()
    controller_settings = get_controller_settings()
    if school_settings.is_production or controller_settings.app_env.lower() == "production":
        fail("refusing to run in production (APP_ENV=production)", 2)

    # Align both sides on the same resolved paths, even when the caller's cwd differs.
    controller_settings.controller_database_url = _normalise_sqlite_url(
        controller_settings.controller_database_url
    )
    school_settings.database_url = _normalise_sqlite_url(school_settings.database_url)
    school_settings.storage_dir = (
        str((REPO_ROOT / school_settings.storage_dir).resolve())
        if not os.path.isabs(school_settings.storage_dir)
        else school_settings.storage_dir
    )

    controller_summary = await seed_controller(controller_settings)
    school_summary = await seed_school(school_settings, controller_summary)
    await attach_instance(
        controller_settings,
        school_summary["instance_id"],
        school_summary["instance_public_key"],
        school_settings.app_version,
    )

    print()
    print("=" * 68)
    print(" Demo seed complete")
    print("=" * 68)
    print(f" School code .......... {DEMO_SCHOOL_CODE} ({DEMO_SCHOOL_NAME})")
    print(
        f" Enrollment token ..... {controller_summary['enrollment_token']}"
        + ("  [created]" if controller_summary["enrollment_created"] else "  [already provisioned]")
    )
    if controller_summary["enrollment_used"]:
        print("                        (already used by a previous enrollment)")
    print(f" Licensed modules ..... {', '.join(controller_summary['modules'])}")
    print(f" Instance id .......... {school_summary['instance_id']}")
    print()
    print(" Controller (http://localhost:5174, API :8100)")
    print("   owner@controller.local     Platform Owner   DevPass#2026")
    print("   support@controller.local   Controller Support DevPass#2026")
    print()
    print(" Demo Academy (http://localhost:5173, API :8000)")
    for email, display_name, role_key in DEMO_USERS:
        print(f"   {email:<28} {display_name:<30} {role_key:<14} DevPass#2026")
    print()
    print(" Ports: API 8000 · Controller API 8100 · Web 5173 · Controller web 5174 · Expo 8081")
    print(
        f" School i18n overrides: {school_summary['override_count']} "
        f"(first: {school_summary['override_key']}, am, school layer)"
    )
    print(f" Themes ............... {', '.join(school_summary['themes'])}")
    if school_summary["themes_created"]:
        print(f"                        created: {', '.join(school_summary['themes_created'])}")
    print(f" Sample note ......... {school_summary['note_id']}")
    print(
        " Activity history ..... seeded through audited service calls (roles, i18n, themes, settings, note)"
    )
    print(" " + "-" * 66)
    print(" All demo accounts use DevPass#2026. Never use these in production.")
    print()
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
