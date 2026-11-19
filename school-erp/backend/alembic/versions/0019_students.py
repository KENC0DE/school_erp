"""students: profiles, enrollments, guardians and medical records

Revision ID: 0019_students
Revises: 0018_curriculum_profiles
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_students"
down_revision: str | None = "0018_curriculum_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.Uuid()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    op.create_table(
        "student_profiles",
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("persons.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("student_number", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="applicant"),
        sa.Column("admission_date", sa.Date()),
        sa.Column("exit_date", sa.Date()),
        sa.Column("exit_reason", sa.String(length=500)),
        sa.Column("notes", sa.Text()),
        sa.Column("custom", sa.JSON()),
        *_common_columns(),
    )
    op.create_index(
        "uq_student_profiles_number_live",
        "student_profiles",
        ["student_number"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_student_profiles_person_live",
        "student_profiles",
        ["person_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_student_profiles_status", "student_profiles", ["status"])

    op.create_table(
        "student_enrollments",
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year_id", sa.Uuid(), nullable=False),
        sa.Column("level_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid()),
        sa.Column("roll_number", sa.String(length=30)),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text()),
        *_common_columns(),
    )
    op.create_index(
        "uq_student_enrollments_student_year_live",
        "student_enrollments",
        ["student_id", "year_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_student_enrollments_year_level_section",
        "student_enrollments",
        ["year_id", "level_id", "section_id"],
    )

    op.create_table(
        "student_guardians",
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("persons.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("relationship", sa.String(length=40), nullable=False, server_default="guardian"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_pickup", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text()),
        *_common_columns(),
    )
    op.create_index(
        "uq_student_guardians_student_person_live",
        "student_guardians",
        ["student_id", "person_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_student_guardians_person", "student_guardians", ["person_id"])

    op.create_table(
        "student_medical_records",
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("blood_type", sa.String(length=10)),
        sa.Column("allergies", sa.Text()),
        sa.Column("chronic_conditions", sa.Text()),
        sa.Column("medications", sa.Text()),
        sa.Column("emergency_contact_name", sa.String(length=160)),
        sa.Column("emergency_contact_phone", sa.String(length=32)),
        sa.Column("notes", sa.Text()),
        sa.Column("consent_to_treat", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_common_columns(),
    )
    op.create_index(
        "uq_student_medical_records_student_live",
        "student_medical_records",
        ["student_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_student_medical_records_student_live",
        table_name="student_medical_records",
    )
    op.drop_table("student_medical_records")
    op.drop_index("ix_student_guardians_person", table_name="student_guardians")
    op.drop_index(
        "uq_student_guardians_student_person_live",
        table_name="student_guardians",
    )
    op.drop_table("student_guardians")
    op.drop_index(
        "ix_student_enrollments_year_level_section",
        table_name="student_enrollments",
    )
    op.drop_index(
        "uq_student_enrollments_student_year_live",
        table_name="student_enrollments",
    )
    op.drop_table("student_enrollments")
    op.drop_index("ix_student_profiles_status", table_name="student_profiles")
    op.drop_index("uq_student_profiles_person_live", table_name="student_profiles")
    op.drop_index("uq_student_profiles_number_live", table_name="student_profiles")
    op.drop_table("student_profiles")
