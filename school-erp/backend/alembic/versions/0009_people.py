"""core: persons with three-part names and normalized search

Revision ID: 0009_people
Revises: 0008_audit_retries
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_people"
down_revision: str | None = "0008_audit_retries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "persons",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("given_name_en", sa.String(120)),
        sa.Column("father_name_en", sa.String(120)),
        sa.Column("grandfather_name_en", sa.String(120)),
        sa.Column("given_name_am", sa.String(120)),
        sa.Column("father_name_am", sa.String(120)),
        sa.Column("grandfather_name_am", sa.String(120)),
        sa.Column("mother_name_en", sa.String(120)),
        sa.Column("mother_name_am", sa.String(120)),
        sa.Column("baptismal_name", sa.String(120)),
        sa.Column("nickname", sa.String(120)),
        sa.Column("search_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("sex", sa.String(20)),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column("place_of_birth", sa.String(200)),
        sa.Column("nationality", sa.String(80)),
        sa.Column("phone", sa.String(32)),
        sa.Column("email", sa.String(255)),
        sa.Column("address", sa.Text()),
        sa.Column("photo_file_id", sa.Uuid()),
        sa.Column("custom", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.Uuid()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_persons_phone", "persons", ["phone"])
    op.create_index("ix_persons_email", "persons", ["email"])
    op.create_index("ix_persons_dob", "persons", ["date_of_birth"])
    op.create_index("ix_persons_search_name", "persons", ["search_name"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute("CREATE INDEX ix_persons_search_trgm ON persons USING gin (search_name gin_trgm_ops)")


def downgrade() -> None:
    op.drop_table("persons")
