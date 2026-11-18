"""admissions: applications, guardians and application numbering

Revision ID: 0021_admissions
Revises: 0020_student_numbering
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_admissions"
down_revision: str | None = "0020_student_numbering"
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
        "admission_applications",
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("persons.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("application_number", sa.String(length=40), nullable=False),
        sa.Column("year_id", sa.Uuid(), nullable=False),
        sa.Column("level_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="applied"),
        sa.Column("entrance_test_score", sa.Integer()),
        sa.Column("decision_notes", sa.Text()),
        sa.Column("decided_by", sa.Uuid()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="SET NULL"),
        ),
        sa.Column("converted_at", sa.DateTime(timezone=True)),
        sa.Column("applied_on", sa.Date()),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="office"),
        sa.Column("notes", sa.Text()),
        sa.Column("custom", sa.JSON()),
        *_common_columns(),
    )
    op.create_index(
        "uq_admission_applications_number_live",
        "admission_applications",
        ["application_number"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_admission_applications_person_year_live",
        "admission_applications",
        ["person_id", "year_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_admission_applications_status", "admission_applications", ["status"])
    op.create_index(
        "ix_admission_applications_year_level",
        "admission_applications",
        ["year_id", "level_id"],
    )

    op.create_table(
        "admission_guardians",
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("admission_applications.id", ondelete="CASCADE"),
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
        sa.Column("wants_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("account_user_id", sa.Uuid()),
        sa.Column("notes", sa.Text()),
        *_common_columns(),
    )
    op.create_index(
        "uq_admission_guardians_application_person_live",
        "admission_guardians",
        ["application_id", "person_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_admission_guardians_person", "admission_guardians", ["person_id"])

    op.create_table(
        "admission_number_sequences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("scope", name="uq_admission_number_sequences_scope"),
    )


def downgrade() -> None:
    op.drop_table("admission_number_sequences")
    op.drop_table("admission_guardians")
    op.drop_table("admission_applications")
