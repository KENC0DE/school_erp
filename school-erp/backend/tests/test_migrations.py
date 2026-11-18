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
        teaching_assignment_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(staff_teaching_assignments)")
        }
        leave_type_columns = {row[1] for row in connection.execute("PRAGMA table_info(staff_leave_types)")}
        leave_balance_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(staff_leave_balances)")
        }
        leave_request_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(staff_leave_requests)")
        }
        payroll_component_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(payroll_components)")
        }
        payroll_staff_component_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(payroll_staff_components)")
        }
        payroll_rule_set_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(payroll_rule_sets)")
        }
        payroll_rule_columns = {row[1] for row in connection.execute("PRAGMA table_info(payroll_rules)")}
        payroll_bracket_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(payroll_rule_brackets)")
        }
        payroll_run_columns = {row[1] for row in connection.execute("PRAGMA table_info(payroll_runs)")}
        payroll_payslip_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(payroll_payslips)")
        }
        payroll_line_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(payroll_payslip_lines)")
        }
        attendance_session_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(attendance_sessions)")
        }
        attendance_record_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(attendance_records)")
        }
        staff_attendance_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(staff_attendance)")
        }
        structure_columns = {row[1] for row in connection.execute("PRAGMA table_info(assessment_structures)")}
        component_columns = {row[1] for row in connection.execute("PRAGMA table_info(assessment_components)")}
        assessment_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(assessment_assessments)")
        }
        score_columns = {row[1] for row in connection.execute("PRAGMA table_info(assessment_scores)")}
        revision_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(assessment_score_revisions)")
        }
        correction_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(assessment_correction_requests)")
        }
        scale_columns = {row[1] for row in connection.execute("PRAGMA table_info(assessment_grade_scales)")}
        band_columns = {row[1] for row in connection.execute("PRAGMA table_info(assessment_grade_bands)")}
        assignment_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(assessment_scale_assignments)")
        }
        window_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(assessment_marking_windows)")
        }
        submission_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(assessment_submissions)")
        }
        term_result_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(assessment_term_results)")
        }
        snapshot_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(assessment_result_snapshots)")
        }
        mark_type = connection.execute(
            "SELECT type FROM pragma_table_info('assessment_assessments') WHERE name = 'out_of'"
        ).fetchone()
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
        "staff_teaching_assignments",
        "staff_leave_types",
        "staff_leave_balances",
        "staff_leave_requests",
        "payroll_components",
        "payroll_staff_components",
        "payroll_rule_sets",
        "payroll_rules",
        "payroll_rule_brackets",
        "payroll_runs",
        "payroll_payslips",
        "payroll_payslip_lines",
        "attendance_sessions",
        "attendance_records",
        "staff_attendance",
        "assessment_structures",
        "assessment_components",
        "assessment_assessments",
        "assessment_scores",
        "assessment_score_revisions",
        "assessment_correction_requests",
        "assessment_grade_scales",
        "assessment_grade_bands",
        "assessment_scale_assignments",
        "assessment_marking_windows",
        "assessment_submissions",
        "assessment_term_results",
        "assessment_result_snapshots",
    } <= tables
    assert {"audit_log_no_update", "audit_log_no_delete"} <= triggers
    assert version == "0028_assessment"

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
    assert {"staff_id", "year_id", "section_id", "subject_id", "notes"} <= (teaching_assignment_columns)
    assert {
        "code",
        "name",
        "name_am",
        "is_paid",
        "annual_entitlement_units",
        "counts_against_balance",
        "requires_approval",
        "is_active",
        "sort_order",
    } <= leave_type_columns
    assert {
        "staff_id",
        "year_id",
        "leave_type_id",
        "entitled_units",
        "carried_units",
        "adjustment_units",
        "notes",
    } <= leave_balance_columns
    assert {
        "staff_id",
        "year_id",
        "leave_type_id",
        "start_date",
        "end_date",
        "is_half_day",
        "days_units",
        "reason",
        "status",
        "submitted_at",
        "decided_at",
        "decided_by",
        "decision_note",
    } <= leave_request_columns
    assert {
        "code",
        "name",
        "name_am",
        "kind",
        "is_taxable",
        "is_pensionable",
        "is_active",
        "sort_order",
    } <= payroll_component_columns
    assert {
        "staff_id",
        "component_id",
        "amount_santim",
        "rate_basis_points",
        "starts_on",
        "ends_on",
    } <= payroll_staff_component_columns
    assert {
        "code",
        "name",
        "effective_from",
        "effective_to",
        "status",
        "verified_by_accountant",
    } <= payroll_rule_set_columns
    assert {
        "rule_set_id",
        "key",
        "name",
        "kind",
        "payer",
        "method",
        "base",
        "rate_basis_points",
        "is_active",
    } <= payroll_rule_columns
    assert {
        "rule_id",
        "lower_santim",
        "upper_santim",
        "rate_basis_points",
        "sort_order",
    } <= payroll_bracket_columns
    assert {
        "period_year",
        "period_month",
        "rule_set_id",
        "status",
        "payslip_count",
        "skipped_count",
        "gross_santim",
        "deductions_santim",
        "net_santim",
        "employer_santim",
    } <= payroll_run_columns
    assert {
        "run_id",
        "staff_id",
        "contract_id",
        "staff_number",
        "staff_name",
        "base_salary_santim",
        "gross_santim",
        "taxable_santim",
        "pensionable_santim",
        "total_deductions_santim",
        "net_santim",
        "employer_contributions_santim",
    } <= payroll_payslip_columns
    assert {
        "payslip_id",
        "kind",
        "code",
        "name",
        "source",
        "rule_key",
        "amount_santim",
        "base_santim",
        "rate_basis_points",
        "sort_order",
    } <= payroll_line_columns
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
    assert {
        "year_id",
        "section_id",
        "date",
        "mode",
        "period",
        "subject_id",
        "status",
        "notes",
        "status_changed_at",
        "status_changed_by",
    } <= attendance_session_columns
    assert {
        "session_id",
        "student_id",
        "status",
        "reason",
        "late_minutes",
        "note",
        "recorded_at",
        "recorded_by",
    } <= attendance_record_columns
    assert {
        "staff_id",
        "date",
        "status",
        "reason",
        "note",
        "recorded_at",
        "recorded_by",
        "row_version",
        "deleted_at",
    } <= staff_attendance_columns
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

    assert {
        "year_id",
        "scope_type",
        "scope_key",
        "level_id",
        "stage_id",
        "subject_id",
        "name",
        "name_am",
        "term_system",
        "year_mode",
        "year_weights",
        "precision",
        "rounding",
        "intended_total",
        "descriptive_mode",
        "version",
        "is_active",
        "row_version",
        "deleted_at",
    } <= structure_columns
    assert {
        "structure_id",
        "key",
        "name",
        "name_am",
        "max_points",
        "aggregation",
        "absent_counts_as_zero",
        "best_n",
        "cap",
        "sort_order",
        "is_active",
    } <= component_columns
    assert {
        "year_id",
        "term_id",
        "section_id",
        "subject_id",
        "structure_id",
        "component_id",
        "title",
        "title_am",
        "assessment_date",
        "out_of",
        "weight",
        "allow_bonus",
        "status",
    } <= assessment_columns
    assert {
        "assessment_id",
        "student_id",
        "raw_score",
        "out_of",
        "status",
        "converted",
        "note",
        "entered_at",
        "entered_by",
    } <= score_columns
    assert {
        "score_id",
        "assessment_id",
        "student_id",
        "correction_request_id",
        "old_raw",
        "new_raw",
        "old_status",
        "new_status",
        "old_converted",
        "new_converted",
        "source",
        "reason",
        "changed_at",
        "changed_by",
    } <= revision_columns
    assert {
        "score_id",
        "assessment_id",
        "student_id",
        "year_id",
        "term_id",
        "section_id",
        "subject_id",
        "old_raw",
        "new_raw",
        "old_status",
        "new_status",
        "reason",
        "status",
        "requested_at",
        "requested_by",
        "decided_at",
        "decided_by",
        "decision_note",
    } <= correction_columns
    assert {
        "name",
        "name_am",
        "type",
        "is_default",
        "lower_bound",
        "upper_bound",
        "precision",
        "rounding",
        "version",
        "effective_from",
        "effective_to",
        "is_active",
    } <= scale_columns
    assert {
        "scale_id",
        "min_value",
        "max_value",
        "label",
        "remark",
        "gpa_points",
        "is_pass",
        "color",
        "sort_order",
    } <= band_columns
    assert {
        "scale_id",
        "context",
        "scope_key",
        "assessment_id",
        "subject_id",
        "level_id",
        "stage_id",
    } <= assignment_columns
    assert {
        "year_id",
        "term_id",
        "level_id",
        "section_id",
        "scope_key",
        "opens_at",
        "closes_at",
        "is_active",
        "note",
    } <= window_columns
    assert {
        "year_id",
        "term_id",
        "section_id",
        "subject_id",
        "status",
        "submitted_at",
        "submitted_by",
        "approved_at",
        "approved_by",
        "published_at",
        "published_by",
        "locked_at",
        "locked_by",
        "note",
    } <= submission_columns
    assert {
        "year_id",
        "term_id",
        "section_id",
        "subject_id",
        "student_id",
        "structure_id",
        "structure_version",
        "scale_id",
        "scale_version",
        "total",
        "out_of",
        "percent",
        "grade_label",
        "grade_remark",
        "gpa_points",
        "is_pass",
        "rank",
        "rank_size",
        "status",
        "published_at",
    } <= term_result_columns
    assert {
        "year_id",
        "term_id",
        "section_id",
        "student_id",
        "kind",
        "structure_id",
        "structure_version",
        "scale_id",
        "scale_version",
        "payload",
        "checksum",
        "published_at",
        "published_by",
        "note",
        "supersedes_id",
    } <= snapshot_columns

    # Marks are stored as integer micro-units, never as SQL floats (ARCH §9.5).
    assert mark_type is not None
    assert mark_type[0] == "BIGINT"
