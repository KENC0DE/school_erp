"""portal account links for students and guardians

Revision ID: 0029_portal_links
Revises: 0028_assessment

A portal account is a normal user account. The student profile carries its own
link; a guardian link carries the parent account, so one parent account can see
every child linked across its rows.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029_portal_links"
down_revision: str | None = "0028_assessment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIVE_WHERE = sa.text("deleted_at IS NULL")


def upgrade() -> None:
    # SQLite cannot ALTER a table to add a foreign key, so both columns are
    # added through batch mode, which recreates the table on that dialect.
    with op.batch_alter_table("student_profiles") as batch:
        batch.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_student_profiles_user",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "uq_student_profiles_user_live",
        "student_profiles",
        ["user_id"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )

    with op.batch_alter_table("student_guardians") as batch:
        batch.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_student_guardians_user",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_student_guardians_user",
        "student_guardians",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_student_guardians_user", table_name="student_guardians")
    with op.batch_alter_table("student_guardians") as batch:
        batch.drop_constraint("fk_student_guardians_user", type_="foreignkey")
        batch.drop_column("user_id")

    op.drop_index("uq_student_profiles_user_live", table_name="student_profiles")
    with op.batch_alter_table("student_profiles") as batch:
        batch.drop_constraint("fk_student_profiles_user", type_="foreignkey")
        batch.drop_column("user_id")
