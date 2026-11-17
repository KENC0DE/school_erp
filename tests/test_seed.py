"""P1-SEED: the demo seed creates every account, theme, override and audit trail.

The seed is a script for the owner, so this test runs it in a subprocess against
throwaway SQLite databases and inspects the result. Running it twice proves the
upserts are idempotent: no duplicate rows and no extra audit entries.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from erp_shared.audit import compute_hash

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "scripts" / "seed.py"

DEMO_ACCOUNTS = {
    "superadmin@demo.school": "super_admin",
    "director@demo.school": "director",
    "academichead@demo.school": "academic_head",
    "registrar@demo.school": "registrar",
    "teacher1@demo.school": "teacher",
    "teacher2@demo.school": "teacher",
    "accountant@demo.school": "accountant",
    "hr@demo.school": "hr_officer",
    "limited@demo.school": "limited",
    "parent1@demo.school": "parent",
    "student1@demo.school": "student",
}

DEFAULT_ROLE_KEYS = {
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


def _env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "development",
            "DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'school.db'}",
            "CONTROLLER_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'controller.db'}",
            "STORAGE_DIR": str(tmp_path / "storage"),
        }
    )
    return env


def _run_seed(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SEED)],
        cwd=ROOT,
        env=_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Demo seed complete" in result.stdout
    return result


def _query(db: Path, sql: str, parameters: tuple = ()) -> list[sqlite3.Row]:
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(sql, parameters).fetchall()
    finally:
        connection.close()


def _counts(db: Path) -> dict[str, int]:
    tables = (
        "users",
        "roles",
        "user_roles",
        "translation_entries",
        "themes",
        "settings",
        "sample_notes",
        "audit_log",
    )
    return {table: _query(db, f"select count(*) as total from {table}")[0]["total"] for table in tables}


def _verify_chain(db: Path) -> int:
    rows = _query(db, "select * from audit_log order by seq")
    previous: str | None = None
    for row in rows:
        entry = dict(row)
        entry["ts"] = str(entry["ts"]).replace(" ", "T", 1)
        for field in ("before", "after"):
            raw = entry.get(field)
            entry[field] = json.loads(raw) if raw not in (None, "") else None
        assert row["prev_hash"] == previous
        assert row["hash"] == compute_hash(previous, entry)
        previous = row["hash"]
    return len(rows)


def test_seed_refuses_production(tmp_path: Path) -> None:
    env = _env(tmp_path)
    env["APP_ENV"] = "production"
    result = subprocess.run(
        [sys.executable, str(SEED)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 2
    assert "refusing to run" in result.stderr
    assert not (tmp_path / "school.db").exists()


def test_seed_creates_the_documented_demo_and_is_idempotent(tmp_path: Path) -> None:
    _run_seed(tmp_path)
    school = tmp_path / "school.db"
    controller = tmp_path / "controller.db"

    # Every §1 account exists exactly once with its documented role.
    assignments = {
        row["email"]: row["role_key"]
        for row in _query(
            school,
            """
            select users.email as email, roles.key as role_key
            from users
            join user_roles on user_roles.user_id = users.id
            join roles on roles.id = user_roles.role_id
            """,
        )
    }
    assert assignments == DEMO_ACCOUNTS

    roles = {row["key"] for row in _query(school, "select key from roles")}
    assert DEFAULT_ROLE_KEYS <= roles
    assert roles - DEFAULT_ROLE_KEYS == {"limited"}

    limited = _query(
        school,
        """
        select role_permissions.permission as permission
        from role_permissions
        join roles on roles.id = role_permissions.role_id
        where roles.key = 'limited'
        order by permission
        """,
    )
    assert [row["permission"] for row in limited] == ["ai.use", "sample.notes.view"]

    # School-layer overrides prove default < central < school precedence.
    overrides = _query(
        school,
        "select namespace, key, locale from translation_entries where layer = 'school' order by key",
    )
    assert len(overrides) == 4
    assert {(row["namespace"], row["locale"]) for row in overrides} == {("core", "am")}
    assert "dashboard.subtitle" in {row["key"] for row in overrides}

    themes = {row["key"]: row for row in _query(school, "select * from themes order by key")}
    assert set(themes) == {"default", "highlands", "sunset"}
    assert [key for key, row in themes.items() if row["is_default"]] == ["default"]
    assert all(row["is_active"] for row in themes.values())
    assert themes["default"]["is_builtin"] == 1

    setting = _query(
        school,
        "select value from settings where layer = 'instance' and module = 'core' and key = 'school_profile.name'",
    )
    assert len(setting) == 1
    assert json.loads(setting[0]["value"]) == "Demo Academy"

    actions = {row["action"] for row in _query(school, "select distinct action from audit_log")}
    assert {
        "rbac.user.role_assigned",
        "rbac.role.permissions",
        "i18n.create",
        "theme.import",
        "settings.update",
        "sample.notes.create",
    } <= actions
    first_audit_count = _verify_chain(school)
    assert first_audit_count >= 19

    controller_users = {row["email"] for row in _query(controller, "select email from cp_users")}
    assert controller_users == {"owner@controller.local", "support@controller.local"}
    assert _query(controller, "select count(*) as total from schools")[0]["total"] == 1

    # The seed must register every mapper before create_all; a missing table
    # only shows up when the running server first touches it.
    tables = {row["name"] for row in _query(school, "select name from sqlite_master where type = 'table'")}
    assert {
        "notification_templates",
        "notifications",
        "files",
        "jobs",
        "themes",
        "audit_log",
    } <= tables

    before = _counts(school)
    _run_seed(tmp_path)
    after = _counts(school)

    assert after == before
    assert _verify_chain(school) == first_audit_count
