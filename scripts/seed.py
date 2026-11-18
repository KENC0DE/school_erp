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
from datetime import UTC, date, datetime, timedelta
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
DEMO_MODULES: tuple[str, ...] = ("academics", "students", "admissions", "staff", "attendance", "sample")
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


# ---------------------------------------------------------------------------
# P2-SEED: demo academic structure, staff placeholders and student roster
# ---------------------------------------------------------------------------

DEMO_YEAR_CODE = "2026-2027"
DEMO_YEAR_NAME = "2026/27"
DEMO_YEAR_NAME_AM = "2019 ዓ.ም"
DEMO_YEAR_START = date(2026, 9, 11)
DEMO_YEAR_END = date(2027, 6, 30)
DEMO_CURRICULUM_CODE = "ethiopian_national"
# The demo school teaches kindergarten through Grade 8. Scope is narrowed before
# the year is created so the curriculum map only contains the levels it teaches.
DEMO_SCOPE = (0, 8)

# (code, English name, Amharic name). Names are combined deterministically into
# three-part names; Amharic and Latin are carried side by side on every person.
MALE_NAMES: tuple[tuple[str, str], ...] = (
    ("Abebe", "አበበ"),
    ("Bekele", "በቀለ"),
    ("Tesfaye", "ተስፋዬ"),
    ("Dawit", "ዳዊት"),
    ("Yonas", "ዮናስ"),
    ("Samuel", "ሳሙኤል"),
    ("Henok", "ሄኖክ"),
    ("Bereket", "በረከት"),
    ("Nahom", "ናሆም"),
    ("Mikias", "ሚኪያስ"),
    ("Eyob", "ኢዮብ"),
    ("Girmay", "ግርማይ"),
    ("Haile", "ኃይሌ"),
    ("Kebede", "ከበደ"),
    ("Solomon", "ሰለሞን"),
    ("Tewodros", "ተወድሮስ"),
    ("Mulugeta", "ሙሉጌታ"),
    ("Fikru", "ፍቅሩ"),
    ("Getachew", "ጌታቸው"),
    ("Abera", "አበራ"),
    ("Chala", "ቻላ"),
    ("Desta", "ደስታ"),
    ("Elias", "ኤልያስ"),
    ("Fitsum", "ፍጹም"),
    ("Gebre", "ገብሬ"),
    ("Hailu", "ሃይሉ"),
    ("Isayas", "ኢሳያስ"),
    ("Jemal", "ጀማል"),
    ("Kassa", "ካሳ"),
    ("Lemma", "ለማ"),
)

FEMALE_NAMES: tuple[tuple[str, str], ...] = (
    ("Marta", "ማርታ"),
    ("Hana", "ሐና"),
    ("Selam", "ሰላም"),
    ("Meron", "ሜሮን"),
    ("Tigist", "ትግስት"),
    ("Aster", "አስተር"),
    ("Genet", "ገነት"),
    ("Hirut", "ሂሩት"),
    ("Almaz", "አልማዝ"),
    ("Bethlehem", "ቤተልሔም"),
    ("Rahel", "ራሔል"),
    ("Sara", "ሳራ"),
    ("Sofia", "ሶፊያ"),
    ("Eden", "ኤደን"),
    ("Feven", "ፌቨን"),
    ("Mahlet", "ማህሌት"),
    ("Meseret", "መሰረት"),
    ("Netsanet", "ነጻነት"),
    ("Tsion", "ጽዮን"),
    ("Zewditu", "ዘውዲቱ"),
    ("Lulit", "ሉሊት"),
    ("Blen", "ብለን"),
    ("Eyerusalem", "እየሩሳሌም"),
    ("Frehiwot", "ፍሬሕይወት"),
    ("Gelila", "ገሊላ"),
    ("Helen", "ሄለን"),
    ("Kalkidan", "ቅልቅዳን"),
    ("Lidya", "ሊድያ"),
    ("Mekdes", "መቅደስ"),
    ("Ruth", "ሩት"),
)

DEMO_ADDRESSES: tuple[str, ...] = (
    "Addis Ababa",
    "Adama",
    "Bahir Dar",
    "Hawassa",
    "Mekelle",
    "Gondar",
    "Jimma",
    "Dire Dawa",
)

# One section entry per class; the count is the number of demo students placed
# in that section. Grades 1–8 have an A and B stream, kindergarten has one.
DEMO_SECTION_PLAN: tuple[tuple[str, str, int], ...] = (
    ("kg1", "A", 4),
    ("kg2", "A", 4),
    ("kg3", "A", 4),
    ("g1", "A", 3),
    ("g1", "B", 3),
    ("g2", "A", 3),
    ("g2", "B", 3),
    ("g3", "A", 3),
    ("g3", "B", 3),
    ("g4", "A", 3),
    ("g4", "B", 3),
    ("g5", "A", 3),
    ("g5", "B", 3),
    ("g6", "A", 3),
    ("g6", "B", 3),
    ("g7", "A", 3),
    ("g7", "B", 3),
    ("g8", "A", 3),
    ("g8", "B", 3),
)

# Staff placeholders until the staff module lands in Phase 3. Each person uses
# the same email as the demo user account so P3 can link them without renaming.
# (email, sex, given_en, father_en, grandfather_en, given_am, father_am, grandfather_am)
DEMO_STAFF: tuple[tuple[str, str, str, str, str, str, str, str], ...] = (
    (
        "director@demo.school",
        "male",
        "Alemayehu",
        "Bekele",
        "Wondimu",
        "አለማየሁ",
        "በቀለ",
        "ወንድሙ",
    ),
    (
        "academichead@demo.school",
        "female",
        "Tigist",
        "Hailu",
        "Mekonnen",
        "ትግስት",
        "ሃይሉ",
        "መኮንን",
    ),
    (
        "registrar@demo.school",
        "female",
        "Marta",
        "Girma",
        "Assefa",
        "ማርታ",
        "ግርማ",
        "አሰፋ",
    ),
    (
        "teacher1@demo.school",
        "male",
        "Solomon",
        "Tesfaye",
        "Gebre",
        "ሰለሞን",
        "ተስፋዬ",
        "ገብሬ",
    ),
    (
        "teacher2@demo.school",
        "female",
        "Hana",
        "Desta",
        "Alemu",
        "ሐና",
        "ደስታ",
        "አለሙ",
    ),
    (
        "hr@demo.school",
        "male",
        "Yohannes",
        "Kebede",
        "Tadesse",
        "ዮሐንስ",
        "ከበደ",
        "ታደሰ",
    ),
)

# Where each demo staff member works and which position they hold.
DEMO_STAFF_PLACEMENT: dict[str, tuple[str, str]] = {
    "director@demo.school": ("administration", "administrator"),
    "academichead@demo.school": ("administration", "administrator"),
    "registrar@demo.school": ("administration", "administrator"),
    "teacher1@demo.school": ("teaching", "teacher"),
    "teacher2@demo.school": ("teaching", "teacher"),
    "hr@demo.school": ("administration", "administrator"),
}

# (code, English name, Amharic name)
DEMO_DEPARTMENTS: tuple[tuple[str, str, str], ...] = (
    ("administration", "Administration", "አስተዳደር"),
    ("teaching", "Teaching", "ማስተማር"),
)

# (code, English name, Amharic name, is_teaching, department code)
DEMO_POSITIONS: tuple[tuple[str, str, str, bool, str], ...] = (
    ("administrator", "Administrator", "አስተዳዳሪ", False, "administration"),
    ("teacher", "Teacher", "አስተማሪ", True, "teaching"),
)

# A normal school week of staff attendance, with two exceptions so the demo
# shows an absence, a late arrival and an approved leave in the same week.
DEMO_STAFF_ATTENDANCE_WEEK: tuple[date, ...] = (
    date(2026, 9, 14),
    date(2026, 9, 15),
    date(2026, 9, 16),
    date(2026, 9, 17),
    date(2026, 9, 18),
)

# (email, level, section, subject codes). The two demo teachers cover one
# homeroom each, which is what the scope resolvers use in the owner script.
DEMO_TEACHING: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "teacher1@demo.school",
        "g5",
        "A",
        ("mathematics", "science", "ict"),
    ),
    (
        "teacher2@demo.school",
        "g6",
        "A",
        ("english", "amharic", "social_studies"),
    ),
)

# (staff email, leave type, start, end, reason, approve)
DEMO_LEAVE_REQUESTS: tuple[tuple[str, str, date, date, str, bool], ...] = (
    (
        "teacher1@demo.school",
        "annual",
        date(2026, 10, 12),
        date(2026, 10, 13),
        "Demo seed: family event",
        True,
    ),
    (
        "teacher2@demo.school",
        "sick",
        date(2026, 10, 15),
        date(2026, 10, 15),
        "Demo seed: medical appointment",
        False,
    ),
)


def _level_scope(level_code: str) -> int:
    """Grade 1–12 map to their number; every KG level maps to 0."""
    return int(level_code[1:]) if level_code.startswith("g") else 0


def _guardian_specs(index: int, family_group: int) -> list[dict]:
    father = MALE_NAMES[(family_group * 7 + 3) % len(MALE_NAMES)]
    grandfather = MALE_NAMES[(family_group * 11 + 5) % len(MALE_NAMES)]
    great_grandfather = MALE_NAMES[(family_group * 23 + 17) % len(MALE_NAMES)]
    mother = FEMALE_NAMES[(family_group * 13 + 7) % len(FEMALE_NAMES)]
    mother_father = MALE_NAMES[(family_group * 17 + 11) % len(MALE_NAMES)]
    mother_grandfather = MALE_NAMES[(family_group * 19 + 13) % len(MALE_NAMES)]
    father_email = "parent1@demo.school" if family_group == 0 else f"guardian.{family_group:03d}@demo.school"
    mother_email = f"guardian.mother.{family_group:03d}@demo.school"
    place = DEMO_ADDRESSES[index % len(DEMO_ADDRESSES)]
    return [
        {
            "relationship": "father",
            "email": father_email,
            "person": {
                "given_name_en": father[0],
                "father_name_en": grandfather[0],
                "grandfather_name_en": great_grandfather[0],
                "given_name_am": father[1],
                "father_name_am": grandfather[1],
                "grandfather_name_am": great_grandfather[1],
                "sex": "male",
                "phone": f"+2519{family_group:08d}",
                "address": place,
            },
        },
        {
            "relationship": "mother",
            "email": mother_email,
            "person": {
                "given_name_en": mother[0],
                "father_name_en": mother_father[0],
                "grandfather_name_en": mother_grandfather[0],
                "given_name_am": mother[1],
                "father_name_am": mother_father[1],
                "grandfather_name_am": mother_grandfather[1],
                "sex": "female",
                "phone": f"+2519{family_group + 500:08d}",
                "address": place,
            },
        },
    ]


def demo_student_roster() -> list[dict]:
    """Build the deterministic 60-student roster used by the seed and its tests.

    The first two students are siblings: they share the same father and mother
    guardians, and the father is the person behind ``parent1@demo.school``.
    """
    roster: list[dict] = []
    index = 0
    for level_code, section_code, count in DEMO_SECTION_PLAN:
        scope_level = _level_scope(level_code)
        for roll in range(1, count + 1):
            male = index % 2 == 0
            pool = MALE_NAMES if male else FEMALE_NAMES
            given = pool[(index // 2) % len(pool)]
            family_group = 0 if index < 2 else index
            father = MALE_NAMES[(family_group * 7 + 3) % len(MALE_NAMES)]
            grandfather = MALE_NAMES[(family_group * 11 + 5) % len(MALE_NAMES)]
            year = DEMO_YEAR_START.year
            roster.append(
                {
                    "index": index,
                    "level_code": level_code,
                    "section_code": section_code,
                    "roll_number": str(roll),
                    "student_number": f"STU-{year}-{index + 1:04d}",
                    "person": {
                        "given_name_en": given[0],
                        "father_name_en": father[0],
                        "grandfather_name_en": grandfather[0],
                        "given_name_am": given[1],
                        "father_name_am": father[1],
                        "grandfather_name_am": grandfather[1],
                        "sex": "male" if male else "female",
                        "date_of_birth": date(
                            year - (5 + scope_level),
                            1 + (index % 12),
                            1 + (index % 27),
                        ),
                        "address": DEMO_ADDRESSES[index % len(DEMO_ADDRESSES)],
                    },
                    "guardians": _guardian_specs(index, family_group),
                }
            )
            index += 1
    return roster


async def _ensure_demo_person(
    session,
    principal,
    email: str,
    person: dict,
    summary: dict,
) -> object:
    """Find a demo person by email, or create it through the audited service."""
    from core.people.models import Person
    from core.people.service import create_person
    from sqlalchemy import select

    existing = (
        (await session.execute(select(Person).where(Person.email == email, Person.deleted_at.is_(None))))
        .scalars()
        .first()
    )
    if existing is not None:
        return existing.id
    created, _warnings = await create_person(
        session,
        principal,
        {**person, "email": email},
        via="api",
        reason="Demo seed person",
        commit=False,
    )
    summary["people_created"] = summary.get("people_created", 0) + 1
    return created.id


async def seed_demo_data(session, principal, *, users_by_email: dict | None = None) -> dict:
    """Seed the Phase 2 demo academic year, crew and 60-student roster.

    Every write goes through the audited service functions, so a fresh demo
    instance also carries realistic activity history. Re-running is a no-op:
    the year, sections, staff persons, guardians and students are matched on
    stable codes/emails/numbers before anything is created.
    """
    import uuid

    from modules.academics import curriculum_service, section_service
    from modules.academics import service as academics
    from modules.academics import years as year_service
    from modules.academics.curriculum_schemas import CurriculumApply
    from modules.academics.models import AcademicYear, LevelSubject, Subject
    from modules.academics.schemas import ScopeUpdate, YearCreate
    from modules.academics.section_schemas import SectionCreate
    from modules.students import service as student_service
    from modules.students.models import StudentProfile
    from modules.students.schemas import EnrollmentInput, GuardianInput, StudentRegister
    from sqlalchemy import func, select

    users_by_email = users_by_email or {}
    summary: dict = {
        "year_code": DEMO_YEAR_CODE,
        "scope": DEMO_SCOPE,
        "sections_created": 0,
        "students_created": 0,
        "staff_created": 0,
        "people_created": 0,
    }

    # Narrow the scope before creating the year: the profile application only
    # maps levels that are inside the school's current scope.
    await academics.update_scope(
        session,
        principal,
        ScopeUpdate(
            first_level=DEMO_SCOPE[0],
            last_level=DEMO_SCOPE[1],
            reason="Demo school: kindergarten through Grade 8",
        ),
        via="api",
    )

    year = (
        await session.execute(
            select(AcademicYear).where(
                AcademicYear.code == DEMO_YEAR_CODE,
                AcademicYear.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if year is None:
        profiles = await curriculum_service.list_profiles(session)
        profile = next(
            (item for item in profiles.items if item.code == DEMO_CURRICULUM_CODE),
            None,
        )
        created_year = await year_service.create_year(
            session,
            principal,
            YearCreate(
                code=DEMO_YEAR_CODE,
                name=DEMO_YEAR_NAME,
                name_am=DEMO_YEAR_NAME_AM,
                start_date=DEMO_YEAR_START,
                end_date=DEMO_YEAR_END,
                curriculum_profile_id=uuid.UUID(profile.id) if profile is not None else None,
            ),
            via="api",
        )
        year_id = uuid.UUID(created_year.id)
    else:
        year_id = year.id

    year = await session.get(AcademicYear, year_id)
    year_out = await year_service.get_year(session, year_id)
    summary["year_id"] = str(year_id)
    summary["year_status"] = year_out.status

    if year.curriculum_profile_id is None:
        profiles = await curriculum_service.list_profiles(session)
        profile = next(
            (item for item in profiles.items if item.code == DEMO_CURRICULUM_CODE),
            None,
        )
        if profile is not None:
            await curriculum_service.apply_profile(
                session,
                principal,
                uuid.UUID(profile.id),
                CurriculumApply(year_id=year_id, confirm=True, reason="Demo curriculum"),
                via="api",
            )

    if year_out.status == "draft":
        years = await year_service.list_years(session)
        if years.current_year_id is None:
            year_out = await year_service.open_year(
                session, principal, year_id, reason="Demo academic year", via="api"
            )
    if year_out.status == "open" and not any(term.status == "open" for term in year_out.terms):
        first_term = next((term for term in year_out.terms if term.number == 1), None)
        if first_term is not None:
            year_out = await year_service.open_term(
                session,
                principal,
                year_id,
                uuid.UUID(first_term.id),
                reason="Demo first semester",
                via="api",
            )
    summary["year_status"] = year_out.status

    levels = {
        item.code: uuid.UUID(item.id) for item in (await academics.list_levels(session, all_scope=True)).items
    }

    staff_ids: dict[str, object] = {}
    for (
        email,
        sex,
        given_en,
        father_en,
        grandfather_en,
        given_am,
        father_am,
        grandfather_am,
    ) in DEMO_STAFF:
        before = summary["people_created"]
        staff_ids[email] = await _ensure_demo_person(
            session,
            principal,
            email,
            {
                "given_name_en": given_en,
                "father_name_en": father_en,
                "grandfather_name_en": grandfather_en,
                "given_name_am": given_am,
                "father_name_am": father_am,
                "grandfather_name_am": grandfather_am,
                "sex": sex,
                "address": "Addis Ababa",
            },
            summary,
        )
        if summary["people_created"] > before:
            summary["staff_created"] += 1

    existing_sections = await section_service.list_sections(
        session,
        year_id=year_id,
        include_inactive=True,
        all_scope=True,
    )
    section_ids = {(item.level_code, item.code): uuid.UUID(item.id) for item in existing_sections.items}
    homerooms = {
        ("g5", "A"): users_by_email.get("teacher1@demo.school"),
        ("g6", "A"): users_by_email.get("teacher2@demo.school"),
    }
    for level_code, section_code, _count in DEMO_SECTION_PLAN:
        if (level_code, section_code) in section_ids:
            continue
        homeroom = homerooms.get((level_code, section_code))
        created_section = await section_service.create_section(
            session,
            principal,
            SectionCreate(
                year_id=year_id,
                level_id=levels[level_code],
                code=section_code,
                name=f"Section {section_code}",
                name_am=f"ክፍል {section_code}",
                capacity=40,
                homeroom_user_id=getattr(homeroom, "id", None),
            ),
            via="api",
        )
        section_ids[(level_code, section_code)] = uuid.UUID(created_section.id)
        summary["sections_created"] += 1
    summary["sections"] = len(section_ids)

    existing_numbers = set(
        (
            await session.execute(
                select(StudentProfile.student_number).where(
                    StudentProfile.deleted_at.is_(None),
                    StudentProfile.student_number.like(f"STU-{DEMO_YEAR_START.year}-%"),
                )
            )
        )
        .scalars()
        .all()
    )
    roster = demo_student_roster()
    for student in roster:
        if student["student_number"] in existing_numbers:
            continue
        guardians = []
        for guardian in student["guardians"]:
            person_id = await _ensure_demo_person(
                session,
                principal,
                guardian["email"],
                guardian["person"],
                summary,
            )
            guardians.append(
                GuardianInput(
                    person_id=person_id,
                    relationship=guardian["relationship"],
                    is_primary=guardian["relationship"] == "father",
                    can_pickup=True,
                )
            )
        await student_service.register_student(
            session,
            principal,
            StudentRegister(
                person=student["person"],
                student_number=student["student_number"],
                status="active",
                admission_date=DEMO_YEAR_START,
                enrollment=EnrollmentInput(
                    year_id=year_id,
                    level_id=levels[student["level_code"]],
                    section_id=section_ids[(student["level_code"], student["section_code"])],
                    roll_number=student["roll_number"],
                    status="active",
                ),
                guardians=guardians,
            ),
            via="api",
        )
        summary["students_created"] += 1

    summary["students"] = int(
        (
            await session.execute(
                select(func.count())
                .select_from(StudentProfile)
                .where(
                    StudentProfile.deleted_at.is_(None),
                    StudentProfile.student_number.like(f"STU-{DEMO_YEAR_START.year}-%"),
                )
            )
        ).scalar_one()
    )
    summary["subjects"] = int((await session.execute(select(func.count()).select_from(Subject))).scalar_one())
    summary["level_subjects"] = int(
        (await session.execute(select(func.count()).select_from(LevelSubject))).scalar_one()
    )
    summary["staff_demo"] = await seed_staff_demo(
        session,
        principal,
        users_by_email=users_by_email,
        year_id=year_id,
        section_ids=section_ids,
    )
    await session.commit()
    return summary


async def seed_staff_demo(
    session,
    principal,
    *,
    users_by_email: dict,
    year_id,
    section_ids: dict[tuple[str, str], object],
) -> dict:
    """P3-SEED: staff profiles, teaching assignments, a week of attendance and leave.

    Every write goes through the audited service functions. Re-running matches
    the person, staff number, assignment, day row and leave request before
    creating anything, so the second pass writes no audit rows.
    """
    import uuid

    from core.auth.models import User
    from core.people.models import Person
    from modules.academics.models import Subject
    from modules.staff import attendance_service, leave_requests, structure, teaching
    from modules.staff.attendance_schemas import StaffAttendanceBulkInput, StaffAttendanceInput
    from modules.staff.leave_schemas import LeaveRequestInput, LeaveTypeInput
    from modules.staff.leave_types import create_leave_type, list_leave_types
    from modules.staff.models import StaffAttendance, StaffProfile
    from modules.staff.profiles import create_staff, link_account
    from modules.staff.schemas import (
        AccountLink,
        DepartmentInput,
        PositionInput,
        StaffCreate,
        TeachingAssignmentInput,
    )
    from sqlalchemy import func, select

    summary: dict = {
        "departments_created": 0,
        "positions_created": 0,
        "staff_created": 0,
        "accounts_linked": 0,
        "teaching_assignments_created": 0,
        "attendance_days": 0,
        "attendance_records_created": 0,
        "leave_types_created": 0,
        "leave_requests_created": 0,
    }

    departments = await structure.list_departments(session)
    department_ids = {item.code: uuid.UUID(item.id) for item in departments.items}
    for code, name, name_am in DEMO_DEPARTMENTS:
        if code in department_ids:
            continue
        created = await structure.create_department(
            session,
            principal,
            DepartmentInput(code=code, name=name, name_am=name_am),
            via="api",
        )
        department_ids[code] = uuid.UUID(created.id)
        summary["departments_created"] += 1

    positions = await structure.list_positions(session)
    position_ids = {item.code: uuid.UUID(item.id) for item in positions.items}
    for code, name, name_am, is_teaching, department_code in DEMO_POSITIONS:
        if code in position_ids:
            continue
        created = await structure.create_position(
            session,
            principal,
            PositionInput(
                code=code,
                name=name,
                name_am=name_am,
                department_id=department_ids[department_code],
                is_teaching=is_teaching,
            ),
            via="api",
        )
        position_ids[code] = uuid.UUID(created.id)
        summary["positions_created"] += 1

    staff_ids: dict[str, uuid.UUID] = {}
    for index, row in enumerate(DEMO_STAFF):
        email = row[0]
        person = (
            await session.execute(select(Person).where(Person.email == email, Person.deleted_at.is_(None)))
        ).scalar_one_or_none()
        if person is None:
            continue
        profile = (
            await session.execute(
                select(StaffProfile).where(
                    StaffProfile.person_id == person.id,
                    StaffProfile.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if profile is None:
            department_code, position_code = DEMO_STAFF_PLACEMENT.get(
                email, ("administration", "administrator")
            )
            created = await create_staff(
                session,
                principal,
                StaffCreate(
                    person_id=person.id,
                    staff_number=f"STF-{DEMO_YEAR_START.year}-{index + 1:03d}",
                    department_id=department_ids[department_code],
                    position_id=position_ids[position_code],
                    hire_date=DEMO_YEAR_START,
                ),
                via="api",
            )
            profile = (
                await session.execute(select(StaffProfile).where(StaffProfile.id == uuid.UUID(created.id)))
            ).scalar_one()
            summary["staff_created"] += 1
        staff_ids[email] = profile.id

        user = users_by_email.get(email)
        if user is None:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is not None and profile.user_id != user.id:
            await link_account(
                session,
                principal,
                profile.id,
                AccountLink(user_id=user.id),
                via="api",
            )
            profile.user_id = user.id
            summary["accounts_linked"] += 1

    summary["staff"] = int(
        (
            await session.execute(
                select(func.count()).select_from(StaffProfile).where(StaffProfile.deleted_at.is_(None))
            )
        ).scalar_one()
    )

    wanted_codes = {code for _, _, _, codes in DEMO_TEACHING for code in codes}
    subject_ids = {
        subject.code: subject.id
        for subject in (await session.execute(select(Subject).where(Subject.code.in_(wanted_codes))))
        .scalars()
        .all()
    }
    for email, level_code, section_code, subject_codes in DEMO_TEACHING:
        staff_id = staff_ids.get(email)
        section_id = section_ids.get((level_code, section_code))
        if staff_id is None or section_id is None:
            continue
        existing = await teaching.list_assignments(
            session,
            staff_id=staff_id,
            year_id=uuid.UUID(str(year_id)),
        )
        assigned = {(item.section_id, item.subject_id) for item in existing.items}
        for code in subject_codes:
            subject_id = subject_ids.get(code)
            if subject_id is None:
                continue
            if (str(section_id), str(subject_id)) in assigned:
                continue
            await teaching.create_assignment(
                session,
                principal,
                staff_id,
                TeachingAssignmentInput(
                    year_id=uuid.UUID(str(year_id)),
                    section_id=uuid.UUID(str(section_id)),
                    subject_id=subject_id,
                ),
                via="api",
            )
            summary["teaching_assignments_created"] += 1

    attendance_before = int(
        (await session.execute(select(func.count()).select_from(StaffAttendance))).scalar_one()
    )
    for on_date in DEMO_STAFF_ATTENDANCE_WEEK:
        items: list[StaffAttendanceInput] = []
        for email in staff_ids:
            status, reason, note = "present", None, None
            if on_date == DEMO_STAFF_ATTENDANCE_WEEK[0] and email == "hr@demo.school":
                status, note = "late", "Arrived 20 minutes late"
            if on_date == DEMO_STAFF_ATTENDANCE_WEEK[2] and email == "teacher2@demo.school":
                status, reason = "absent", "Sick"
            if on_date == DEMO_STAFF_ATTENDANCE_WEEK[4] and email == "teacher2@demo.school":
                status, reason = "leave", "Approved annual leave"
            items.append(
                StaffAttendanceInput(
                    staff_id=staff_ids[email],
                    status=status,
                    reason=reason,
                    note=note,
                )
            )
        await attendance_service.upsert_day(
            session,
            principal,
            StaffAttendanceBulkInput(date=on_date, items=items),
            via="api",
        )
        summary["attendance_days"] += 1
    attendance_after = int(
        (await session.execute(select(func.count()).select_from(StaffAttendance))).scalar_one()
    )
    summary["attendance_records_created"] = attendance_after - attendance_before

    leave_types = {item.code: item for item in (await list_leave_types(session)).items}
    for code, name, name_am, days in (
        ("annual", "Annual leave", "ዓመታዊ ፈቃድ", 20),
        ("sick", "Sick leave", "የሕመም ፈቃድ", 10),
    ):
        if code in leave_types:
            continue
        created = await create_leave_type(
            session,
            principal,
            LeaveTypeInput(
                code=code,
                name=name,
                name_am=name_am,
                annual_entitlement_days=days,
            ),
            via="api",
        )
        leave_types[code] = created
        summary["leave_types_created"] += 1

    existing_requests = (
        await leave_requests.list_leave_requests(
            session,
            principal,
            year_id=uuid.UUID(str(year_id)),
        )
    ).items
    for email, type_code, start, end, reason, approve in DEMO_LEAVE_REQUESTS:
        staff_id = staff_ids.get(email)
        leave_type = leave_types.get(type_code)
        if staff_id is None or leave_type is None:
            continue
        row = next(
            (
                item
                for item in existing_requests
                if item.staff_id == str(staff_id)
                and item.start_date == start
                and item.end_date == end
                and item.reason == reason
            ),
            None,
        )
        if row is None:
            row = await leave_requests.create_leave_request(
                session,
                principal,
                LeaveRequestInput(
                    staff_id=staff_id,
                    year_id=uuid.UUID(str(year_id)),
                    leave_type_id=uuid.UUID(leave_type.id),
                    start_date=start,
                    end_date=end,
                    reason=reason,
                ),
                via="api",
            )
            existing_requests.append(row)
            summary["leave_requests_created"] += 1
        if row.status == "draft":
            row = await leave_requests.submit_leave_request(session, principal, uuid.UUID(row.id), via="api")
        if approve and row.status == "submitted":
            await leave_requests.approve_leave_request(session, principal, uuid.UUID(row.id), via="api")

    return summary


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

            # Phase 2 demo data: KG–Grade 8 year, sections, subjects applied
            # through the starter curriculum, staff placeholders and 60 students.
            demo = await seed_demo_data(session, principal, users_by_email=user_rows)

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
                    "demo": demo,
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
    demo = school_summary.get("demo", {})
    if demo:
        print(
            f" Academic year ....... {demo['year_code']} "
            f"({demo['year_status']}, semester, {demo['sections']} sections)"
        )
        print(
            f" Demo roster .......... {demo['students']} students, "
            f"{demo['subjects']} subjects, {demo['level_subjects']} level-subject rows"
        )
        print(
            f"                        created now: {demo['students_created']} students, "
            f"{demo['sections_created']} sections, {demo['people_created']} people"
        )
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
