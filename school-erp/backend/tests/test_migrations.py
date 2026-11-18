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
        file_columns = {row[1] for row in connection.execute("PRAGMA table_info(files)")}
        notification_columns = {row[1] for row in connection.execute("PRAGMA table_info(notifications)")}
        template_columns = {row[1] for row in connection.execute("PRAGMA table_info(notification_templates)")}
        delivery_columns = {row[1] for row in connection.execute("PRAGMA table_info(delivery_logs)")}
        level_columns = {row[1] for row in connection.execute("PRAGMA table_info(academics_grade_levels)")}
        stage_columns = {row[1] for row in connection.execute("PRAGMA table_info(academics_stages)")}
        membership_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(academics_stage_levels)")
        }
        year_columns = {row[1] for row in connection.execute("PRAGMA table_info(academics_academic_years)")}
        term_columns = {row[1] for row in connection.execute("PRAGMA table_info(academics_terms)")}
        subject_columns = {row[1] for row in connection.execute("PRAGMA table_info(academics_subjects)")}
        section_columns = {row[1] for row in connection.execute("PRAGMA table_info(academics_sections)")}
        level_subject_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(academics_level_subjects)")
        }
        group_columns = {row[1] for row in connection.execute("PRAGMA table_info(academics_subject_groups)")}
        curriculum_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(academics_curriculum_profiles)")
        }
        curriculum_subject_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(academics_curriculum_level_subjects)")
        }
        sequence_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(student_number_sequences)")
        }
        application_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(admission_applications)")
        }
        admission_guardian_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(admission_guardians)")
        }
        admission_sequence_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(admission_number_sequences)")
        }
        staff_columns = {row[1] for row in connection.execute("PRAGMA table_info(staff_profiles)")}
        staff_contract_columns = {row[1] for row in connection.execute("PRAGMA table_info(staff_contracts)")}
        staff_qualification_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(staff_qualifications)")
        }
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
        "themes",
        "files",
        "notification_templates",
        "notifications",
        "delivery_logs",
        "academics_grade_levels",
        "academics_stages",
        "academics_stage_levels",
        "academics_academic_years",
        "academics_terms",
        "academics_subjects",
        "academics_level_subjects",
        "academics_subject_groups",
        "academics_subject_group_members",
        "academics_sections",
        "academics_curriculum_profiles",
        "academics_curriculum_level_subjects",
        "student_profiles",
        "student_enrollments",
        "student_guardians",
        "student_medical_records",
        "student_number_sequences",
        "admission_applications",
        "admission_guardians",
        "admission_number_sequences",
        "staff_departments",
        "staff_positions",
        "staff_profiles",
        "staff_contracts",
        "staff_qualifications",
        "staff_number_sequences",
    } <= tables
    assert {"audit_log_no_update", "audit_log_no_delete"} <= triggers
    assert version == "0022_staff"

    assert {
        "failed_login_count",
        "locked_until",
        "totp_secret",
        "totp_enabled",
        "totp_recovery_hashes",
        "theme_key",
        "theme_mode",
    } <= user_columns
    assert {"require_totp", "is_active"} <= role_columns
    assert {"code", "start_date", "end_date", "term_system", "status"} <= year_columns
    assert "curriculum_profile_id" in year_columns
    assert {"year_id", "number", "start_date", "end_date", "status"} <= term_columns
    assert {"code", "name", "name_am", "sort_order", "is_active"} <= subject_columns
    assert {"year_id", "level_id", "code", "capacity", "homeroom_user_id"} <= section_columns
    assert {"level_id", "subject_id", "credit"} <= level_subject_columns
    assert {"code", "name", "name_am", "sort_order", "is_active"} <= group_columns
    assert {
        "code",
        "name",
        "name_am",
        "description",
        "term_system",
        "sort_order",
        "is_active",
        "is_starter",
        "is_verified",
    } <= curriculum_columns
    assert {"profile_id", "level_id", "subject_id", "credit"} <= curriculum_subject_columns
    assert {"scope", "value", "created_at", "updated_at"} <= sequence_columns
    assert {
        "person_id",
        "staff_number",
        "user_id",
        "status",
        "department_id",
        "position_id",
        "hire_date",
        "end_date",
        "notes",
        "custom",
    } <= staff_columns
    assert {"staff_id", "type", "status", "start_date", "end_date", "salary_santim"} <= (
        staff_contract_columns
    )
    assert {
        "staff_id",
        "kind",
        "title",
        "institution",
        "field_of_study",
        "start_date",
        "end_date",
        "result",
    } <= staff_qualification_columns
    assert {
        "application_number",
        "person_id",
        "year_id",
        "level_id",
        "section_id",
        "status",
        "entrance_test_score",
        "decision_notes",
        "decided_by",
        "decided_at",
        "student_id",
        "converted_at",
        "applied_on",
        "source",
        "notes",
        "custom",
        "row_version",
        "deleted_at",
    } <= application_columns
    assert {
        "application_id",
        "person_id",
        "relationship",
        "is_primary",
        "can_pickup",
        "wants_account",
        "account_user_id",
        "notes",
        "row_version",
        "deleted_at",
    } <= admission_guardian_columns
    assert {"scope", "value", "created_at", "updated_at"} <= admission_sequence_columns
    assert {"reason", "granted_by"} <= override_columns
    assert {"available_at", "last_attempt_at", "last_error"} <= outbox_columns

    assert live_index is not None
    assert "WHERE deleted_at IS NULL" in live_index[0]

    assert {
        "object_key",
        "original_name",
        "mime",
        "size_bytes",
        "checksum_sha256",
        "owner_entity_type",
        "owner_entity_id",
        "is_private",
        "thumbnail_key",
        "uploaded_by",
    } <= file_columns

    assert {
        "user_id",
        "template_key",
        "category",
        "title",
        "body",
        "params",
        "link",
        "channels",
        "read_at",
    } <= notification_columns
    assert {
        "key",
        "name",
        "namespace",
        "title_key",
        "body_key",
        "default_channels",
        "is_active",
        "is_system",
    } <= template_columns
    assert {
        "notification_id",
        "user_id",
        "template_key",
        "channel",
        "recipient",
        "status",
        "attempts",
        "error",
        "provider",
        "sent_at",
    } <= delivery_columns
    assert {
        "code",
        "name",
        "name_am",
        "scope_level",
        "sort_order",
        "is_active",
        "is_starter",
        "is_verified",
        "row_version",
        "deleted_at",
    } <= level_columns
    assert {
        "code",
        "name",
        "name_am",
        "sort_order",
        "is_active",
        "is_starter",
        "is_verified",
    } <= stage_columns
    assert {"stage_id", "level_id"} <= membership_columns
