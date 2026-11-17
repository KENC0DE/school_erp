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
SCHOOL_I18N_OVERRIDE_KEY = ("core", "dashboard.subtitle", "am")
SCHOOL_I18N_OVERRIDE_VALUE = "ይህ ጽሑፍ በትምህርት ቤቱ ተተክቷል። (school override)"
SAMPLE_NOTE = "Welcome to the demo school! This note was created by the seed."


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
                    modules=["sample"],
                )
                session.add(school)
                await session.flush()
            school.name = DEMO_SCHOOL_NAME
            school.api_base_url = DEMO_API_BASE_URL
            school.status = "active"
            school.modules = sorted(set(school.modules or []) | {"sample"})

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


# Role key -> (display name, permission codes). Permissions are intersected with
# the codes declared by core and by the loaded module manifests, so a typo can
# never silently grant access to something that does not exist.
ROLE_SPECS: dict[str, tuple[str, list[str]]] = {
    "super_admin": ("School Super Admin", ["*"]),
    "director": (
        "Director",
        [
            "users.view",
            "roles.view",
            "modules.view",
            "audit.activity.view",
            "audit.activity.view_admin_actions",
            "i18n.view",
            "themes.view",
            "jobs.view",
            "settings.view",
            "settings.manage",
            "ai.use",
            "sample.notes.view",
            "sample.notes.create",
        ],
    ),
    "academic_head": (
        "Academic Head",
        [
            "users.view",
            "roles.view",
            "modules.view",
            "audit.activity.view",
            "ai.use",
            "sample.notes.view",
            "sample.notes.create",
        ],
    ),
    "registrar": (
        "Registrar",
        ["users.view", "users.manage", "audit.activity.view", "ai.use", "sample.notes.view"],
    ),
    "teacher": (
        "Teacher",
        ["ai.use", "sample.notes.view", "sample.notes.create"],
    ),
    "accountant": (
        "Accountant",
        ["ai.use", "sample.notes.view"],
    ),
    "hr_officer": (
        "HR Officer",
        ["users.view", "ai.use", "sample.notes.view"],
    ),
    "limited": (
        "Limited User",
        ["ai.use", "sample.notes.view"],
    ),
    "parent": (
        "Parent",
        ["ai.use"],
    ),
    "student": (
        "Student",
        ["ai.use"],
    ),
}

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


async def seed_school(school_settings, controller_summary: dict) -> dict:
    from core.auth.models import User
    from core.auth.security import hash_password, verify_password
    from core.controller_link.service import identity
    from core.db.session import Database
    from core.i18n.models import TranslationEntry
    from core.i18n.service import load_defaults
    from core.modules.licensing import apply_license, ensure_module_rows
    from core.modules.models import InstanceModule
    from core.modules.registry import ModuleRegistry
    from core.rbac.models import Role, RolePermission, UserRole
    from core.themes.service import ensure_default_theme
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

            # The license module list is authoritative once a license exists.
            school_module = await session.get(InstanceModule, "sample")
            if school_module is None:
                school_module = InstanceModule(module_key="sample", enabled=True)
                session.add(school_module)
            else:
                school_module.enabled = True
            await session.flush()

            role_rows: dict[str, Role] = {}
            for key, (name, codes) in ROLE_SPECS.items():
                role = (await session.execute(select(Role).where(Role.key == key))).scalar_one_or_none()
                if role is None:
                    role = Role(key=key, name=name, is_system=True, description=f"Seeded {name} role")
                    session.add(role)
                    await session.flush()
                else:
                    role.name = name
                    role.is_system = True
                role_rows[key] = role

                granted = sorted(codes) if "*" in codes else sorted(set(codes) & declared)
                await session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
                for code in granted:
                    session.add(RolePermission(role_id=role.id, permission=code, scope="all"))
            await session.flush()

            user_rows: dict[str, User] = {}
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
                await session.execute(delete(UserRole).where(UserRole.user_id == user.id))
                session.add(UserRole(user_id=user.id, role_id=role_rows[role_key].id))
                user_rows[email] = user
            await session.flush()

            # School-layer translation override: proves default < central < school.
            namespace, key, locale = SCHOOL_I18N_OVERRIDE_KEY
            override = (
                await session.execute(
                    select(TranslationEntry).where(
                        TranslationEntry.namespace == namespace,
                        TranslationEntry.key == key,
                        TranslationEntry.locale == locale,
                        TranslationEntry.layer == "school",
                    )
                )
            ).scalar_one_or_none()
            if override is None:
                override = TranslationEntry(
                    namespace=namespace,
                    key=key,
                    locale=locale,
                    value=SCHOOL_I18N_OVERRIDE_VALUE,
                    layer="school",
                    status="approved",
                    source="human",
                )
                session.add(override)
            else:
                override.value = SCHOOL_I18N_OVERRIDE_VALUE
                override.status = "approved"
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
                superadmin = user_rows["superadmin@demo.school"]
                note = SampleNote(
                    content=SAMPLE_NOTE,
                    author_name=superadmin.display_name,
                    author_id=superadmin.id,
                    created_by=superadmin.id,
                )
                session.add(note)
                await session.flush()

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
                    "override_key": f"{namespace}.{key}",
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
    print(f" School i18n override: {school_summary['override_key']} (am, school layer)")
    print(f" Sample note ......... {school_summary['note_id']}")
    print(" " + "-" * 66)
    print(" All demo accounts use DevPass#2026. Never use these in production.")
    print()
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
