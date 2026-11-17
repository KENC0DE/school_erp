"""P0-05: both migration branches apply to an empty database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from app.settings import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_upgrade_heads_on_empty_database(tmp_path, monkeypatch):
    database = tmp_path / "migrated.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database}")
    get_settings.cache_clear()

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")

    command.upgrade(config, "heads")

    connection = sqlite3.connect(database)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        triggers = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")
        }
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        live_index = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'ix_sample_notes_live'"
        ).fetchone()
        user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        role_columns = {row[1] for row in connection.execute("PRAGMA table_info(roles)")}
        override_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(user_permission_overrides)")
        }
        outbox_columns = {row[1] for row in connection.execute("PRAGMA table_info(audit_outbox)")}
    finally:
        connection.close()

    assert {
        "users",
        "audit_log",
        "instance_modules",
        "sample_notes",
        "idempotency_keys",
        "settings",
        "password_reset_tokens",
        "persons",
        "custom_field_defs",
    } <= tables
    assert {"audit_log_no_update", "audit_log_no_delete"} <= triggers
    assert version == "0010_custom_fields"

    assert {
        "failed_login_count",
        "locked_until",
        "totp_secret",
        "totp_enabled",
        "totp_recovery_hashes",
    } <= user_columns
    assert {"require_totp", "is_active"} <= role_columns
    assert {"reason", "granted_by"} <= override_columns
    assert {"available_at", "last_attempt_at", "last_error"} <= outbox_columns

    assert live_index is not None
    assert "WHERE deleted_at IS NULL" in live_index[0]
