"""assessment structures, marks, grade rules and results

Revision ID: 0028_assessment
Revises: 0027_staff_attendance
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028_assessment"
down_revision: str | None = "0027_staff_attendance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIVE_WHERE = sa.text("deleted_at IS NULL")
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _business_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.Uuid()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    # Grade rules first: a structure and a term result both refer to them.
    op.create_table(
        "assessment_grade_scales",
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_am", sa.String(120)),
        sa.Column("type", sa.String(20), nullable=False, server_default="numeric_bands"),
        sa.Column("description", sa.Text()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("lower_bound", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("upper_bound", sa.BigInteger(), nullable=False, server_default="100000000"),
        sa.Column("precision", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("rounding", sa.String(20), nullable=False, server_default="half_up"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("effective_from", sa.Date()),
        sa.Column("effective_to", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    op.create_index(
        "uq_assessment_grade_scales_name_version_live",
        "assessment_grade_scales",
        ["name", "version"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index(
        "uq_assessment_grade_scales_default_live",
        "assessment_grade_scales",
        ["is_default"],
        unique=True,
        sqlite_where=sa.text("is_default = 1 AND deleted_at IS NULL"),
        postgresql_where=sa.text("is_default = TRUE AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_assessment_grade_scales_effective",
        "assessment_grade_scales",
        ["effective_from", "effective_to"],
    )

    op.create_table(
        "assessment_grade_bands",
        sa.Column(
            "scale_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_grade_scales.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("min_value", sa.BigInteger(), nullable=False),
        sa.Column("max_value", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(40), nullable=False),
        sa.Column("remark", sa.String(255)),
        sa.Column("gpa_points", sa.BigInteger()),
        sa.Column("is_pass", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("color", sa.String(30)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_business_columns(),
    )
    op.create_index(
        "uq_assessment_grade_bands_scale_min_live",
        "assessment_grade_bands",
        ["scale_id", "min_value"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index(
        "ix_assessment_grade_bands_scale_sort",
        "assessment_grade_bands",
        ["scale_id", "sort_order"],
    )

    op.create_table(
        "assessment_structures",
        sa.Column(
            "year_id",
            sa.Uuid(),
            sa.ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_type", sa.String(20), nullable=False, server_default="school"),
        sa.Column("scope_key", sa.String(80), nullable=False),
        sa.Column(
            "level_id",
            sa.Uuid(),
            sa.ForeignKey("academics_grade_levels.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "stage_id",
            sa.Uuid(),
            sa.ForeignKey("academics_stages.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("academics_subjects.id", ondelete="SET NULL"),
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_am", sa.String(120)),
        sa.Column("term_system", sa.String(20), nullable=False),
        sa.Column("year_mode", sa.String(20), nullable=False, server_default="average"),
        sa.Column("year_weights", JSON_TYPE),
        sa.Column("precision", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("rounding", sa.String(20), nullable=False, server_default="half_up"),
        sa.Column("intended_total", sa.BigInteger()),
        sa.Column("descriptive_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    op.create_index(
        "uq_assessment_structures_year_scope_live",
        "assessment_structures",
        ["year_id", "scope_key"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index(
        "ix_assessment_structures_year_type",
        "assessment_structures",
        ["year_id", "scope_type"],
    )
    op.create_index("ix_assessment_structures_level", "assessment_structures", ["level_id"])
    op.create_index("ix_assessment_structures_stage", "assessment_structures", ["stage_id"])
    op.create_index("ix_assessment_structures_subject", "assessment_structures", ["subject_id"])

    op.create_table(
        "assessment_components",
        sa.Column(
            "structure_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_structures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_am", sa.String(120)),
        sa.Column("max_points", sa.BigInteger(), nullable=False),
        sa.Column("aggregation", sa.String(20), nullable=False, server_default="average"),
        sa.Column("absent_counts_as_zero", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("best_n", sa.Integer()),
        sa.Column("cap", sa.BigInteger()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    op.create_index(
        "uq_assessment_components_structure_key_live",
        "assessment_components",
        ["structure_id", "key"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index(
        "ix_assessment_components_structure_sort",
        "assessment_components",
        ["structure_id", "sort_order"],
    )

    op.create_table(
        "assessment_assessments",
        sa.Column(
            "year_id",
            sa.Uuid(),
            sa.ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "term_id",
            sa.Uuid(),
            sa.ForeignKey("academics_terms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            sa.Uuid(),
            sa.ForeignKey("academics_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("academics_subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "structure_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_structures.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "component_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_components.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("title_am", sa.String(160)),
        sa.Column("assessment_date", sa.Date(), nullable=False),
        sa.Column("out_of", sa.BigInteger(), nullable=False),
        sa.Column("weight", sa.BigInteger()),
        sa.Column("allow_bonus", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    op.create_index(
        "ix_assessment_assessments_scope_date",
        "assessment_assessments",
        ["year_id", "term_id", "section_id", "subject_id", "assessment_date"],
    )
    op.create_index(
        "ix_assessment_assessments_component",
        "assessment_assessments",
        ["component_id"],
    )
    op.create_index(
        "ix_assessment_assessments_subject",
        "assessment_assessments",
        ["subject_id"],
    )

    op.create_table(
        "assessment_scores",
        sa.Column(
            "assessment_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_score", sa.BigInteger()),
        sa.Column("out_of", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="present"),
        sa.Column("converted", sa.BigInteger()),
        sa.Column("note", sa.String(500)),
        sa.Column(
            "entered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "entered_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        *_business_columns(),
    )
    op.create_index(
        "uq_assessment_scores_assessment_student_live",
        "assessment_scores",
        ["assessment_id", "student_id"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index("ix_assessment_scores_student", "assessment_scores", ["student_id"])
    op.create_index(
        "ix_assessment_scores_assessment_status",
        "assessment_scores",
        ["assessment_id", "status"],
    )

    op.create_table(
        "assessment_correction_requests",
        sa.Column(
            "score_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_scores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "year_id",
            sa.Uuid(),
            sa.ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "term_id",
            sa.Uuid(),
            sa.ForeignKey("academics_terms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            sa.Uuid(),
            sa.ForeignKey("academics_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("academics_subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_raw", sa.BigInteger()),
        sa.Column("new_raw", sa.BigInteger()),
        sa.Column("old_status", sa.String(20)),
        sa.Column("new_status", sa.String(20)),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "requested_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column(
            "decided_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("decision_note", sa.String(500)),
        *_business_columns(),
    )
    op.create_index(
        "ix_assessment_correction_requests_status",
        "assessment_correction_requests",
        ["status"],
    )
    op.create_index(
        "ix_assessment_correction_requests_score",
        "assessment_correction_requests",
        ["score_id"],
    )
    op.create_index(
        "ix_assessment_correction_requests_scope",
        "assessment_correction_requests",
        ["year_id", "term_id", "section_id"],
    )

    op.create_table(
        "assessment_score_revisions",
        sa.Column(
            "score_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_scores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "correction_request_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_correction_requests.id", ondelete="SET NULL"),
        ),
        sa.Column("old_raw", sa.BigInteger()),
        sa.Column("new_raw", sa.BigInteger()),
        sa.Column("old_status", sa.String(20)),
        sa.Column("new_status", sa.String(20)),
        sa.Column("old_converted", sa.BigInteger()),
        sa.Column("new_converted", sa.BigInteger()),
        sa.Column("source", sa.String(20), nullable=False, server_default="entry"),
        sa.Column("reason", sa.String(500)),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "changed_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        *_business_columns(),
    )
    op.create_index(
        "ix_assessment_score_revisions_score",
        "assessment_score_revisions",
        ["score_id", "changed_at"],
    )
    op.create_index(
        "ix_assessment_score_revisions_student",
        "assessment_score_revisions",
        ["student_id", "changed_at"],
    )
    op.create_index(
        "ix_assessment_score_revisions_request",
        "assessment_score_revisions",
        ["correction_request_id"],
    )

    op.create_table(
        "assessment_scale_assignments",
        sa.Column(
            "scale_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_grade_scales.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("context", sa.String(20), nullable=False),
        sa.Column("scope_key", sa.String(80), nullable=False),
        sa.Column(
            "assessment_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_assessments.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("academics_subjects.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "level_id",
            sa.Uuid(),
            sa.ForeignKey("academics_grade_levels.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "stage_id",
            sa.Uuid(),
            sa.ForeignKey("academics_stages.id", ondelete="CASCADE"),
        ),
        sa.Column("notes", sa.Text()),
        *_business_columns(),
    )
    op.create_index(
        "uq_assessment_scale_assignments_scope_live",
        "assessment_scale_assignments",
        ["scope_key", "scale_id"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index(
        "ix_assessment_scale_assignments_context",
        "assessment_scale_assignments",
        ["context", "scope_key"],
    )

    op.create_table(
        "assessment_term_results",
        sa.Column(
            "year_id",
            sa.Uuid(),
            sa.ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "term_id",
            sa.Uuid(),
            sa.ForeignKey("academics_terms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            sa.Uuid(),
            sa.ForeignKey("academics_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("academics_subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "structure_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_structures.id", ondelete="SET NULL"),
        ),
        sa.Column("structure_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "scale_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_grade_scales.id", ondelete="SET NULL"),
        ),
        sa.Column("scale_version", sa.Integer()),
        sa.Column("total", sa.BigInteger(), nullable=False),
        sa.Column("out_of", sa.BigInteger(), nullable=False),
        sa.Column("percent", sa.BigInteger(), nullable=False),
        sa.Column("grade_label", sa.String(40)),
        sa.Column("grade_remark", sa.String(255)),
        sa.Column("gpa_points", sa.BigInteger()),
        sa.Column("is_pass", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rank", sa.Integer()),
        sa.Column("rank_size", sa.Integer()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        *_business_columns(),
    )
    op.create_index(
        "uq_assessment_term_results_scope_live",
        "assessment_term_results",
        ["year_id", "term_id", "section_id", "subject_id", "student_id"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index(
        "ix_assessment_term_results_student",
        "assessment_term_results",
        ["student_id", "year_id"],
    )
    op.create_index(
        "ix_assessment_term_results_section_term",
        "assessment_term_results",
        ["section_id", "term_id"],
    )
    op.create_index(
        "ix_assessment_term_results_status",
        "assessment_term_results",
        ["status"],
    )

    op.create_table(
        "assessment_result_snapshots",
        sa.Column(
            "year_id",
            sa.Uuid(),
            sa.ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "term_id",
            sa.Uuid(),
            sa.ForeignKey("academics_terms.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "section_id",
            sa.Uuid(),
            sa.ForeignKey("academics_sections.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
        ),
        sa.Column("kind", sa.String(20), nullable=False, server_default="term"),
        sa.Column(
            "structure_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_structures.id", ondelete="SET NULL"),
        ),
        sa.Column("structure_version", sa.Integer()),
        sa.Column(
            "scale_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_grade_scales.id", ondelete="SET NULL"),
        ),
        sa.Column("scale_version", sa.Integer()),
        sa.Column("payload", JSON_TYPE, nullable=False),
        sa.Column("checksum", sa.String(64)),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "published_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("note", sa.String(500)),
        sa.Column(
            "supersedes_id",
            sa.Uuid(),
            sa.ForeignKey("assessment_result_snapshots.id", ondelete="SET NULL"),
        ),
        *_business_columns(),
    )
    op.create_index(
        "ix_assessment_result_snapshots_scope",
        "assessment_result_snapshots",
        ["year_id", "term_id"],
    )
    op.create_index(
        "ix_assessment_result_snapshots_section",
        "assessment_result_snapshots",
        ["section_id"],
    )
    op.create_index(
        "ix_assessment_result_snapshots_student",
        "assessment_result_snapshots",
        ["student_id"],
    )
    op.create_index(
        "ix_assessment_result_snapshots_published",
        "assessment_result_snapshots",
        ["published_at"],
    )

    op.create_table(
        "assessment_marking_windows",
        sa.Column(
            "year_id",
            sa.Uuid(),
            sa.ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "term_id",
            sa.Uuid(),
            sa.ForeignKey("academics_terms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "level_id",
            sa.Uuid(),
            sa.ForeignKey("academics_grade_levels.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "section_id",
            sa.Uuid(),
            sa.ForeignKey("academics_sections.id", ondelete="CASCADE"),
        ),
        sa.Column("scope_key", sa.String(80), nullable=False, server_default="all"),
        sa.Column("opens_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("note", sa.String(500)),
        *_business_columns(),
    )
    op.create_index(
        "ix_assessment_marking_windows_term",
        "assessment_marking_windows",
        ["year_id", "term_id", "closes_at"],
    )
    op.create_index(
        "ix_assessment_marking_windows_scope",
        "assessment_marking_windows",
        ["scope_key"],
    )

    op.create_table(
        "assessment_submissions",
        sa.Column(
            "year_id",
            sa.Uuid(),
            sa.ForeignKey("academics_academic_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "term_id",
            sa.Uuid(),
            sa.ForeignKey("academics_terms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            sa.Uuid(),
            sa.ForeignKey("academics_sections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("academics_subjects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "submitted_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "approved_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "published_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "locked_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("note", sa.String(500)),
        *_business_columns(),
    )
    op.create_index(
        "uq_assessment_submissions_scope_live",
        "assessment_submissions",
        ["year_id", "term_id", "section_id", "subject_id"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index(
        "ix_assessment_submissions_status",
        "assessment_submissions",
        ["status"],
    )
    op.create_index(
        "ix_assessment_submissions_section_term",
        "assessment_submissions",
        ["section_id", "term_id"],
    )


def downgrade() -> None:
    op.drop_table("assessment_submissions")
    op.drop_table("assessment_marking_windows")
    op.drop_table("assessment_result_snapshots")
    op.drop_table("assessment_term_results")
    op.drop_table("assessment_scale_assignments")
    op.drop_table("assessment_score_revisions")
    op.drop_table("assessment_correction_requests")
    op.drop_table("assessment_scores")
    op.drop_table("assessment_assessments")
    op.drop_table("assessment_components")
    op.drop_table("assessment_structures")
    op.drop_table("assessment_grade_bands")
    op.drop_table("assessment_grade_scales")
