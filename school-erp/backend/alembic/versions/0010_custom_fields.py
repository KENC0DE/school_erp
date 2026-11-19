"""core: custom field definitions

Revision ID: 0010_custom_fields
Revises: 0009_people
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_custom_fields"
down_revision: str | None = "0009_people"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custom_field_defs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("label_key", sa.String(160), nullable=False),
        sa.Column("help_key", sa.String(160)),
        sa.Column("field_type", sa.String(20), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("options", sa.JSON()),
        sa.Column("min_value", sa.Text()),
        sa.Column("max_value", sa.Text()),
        sa.Column("max_length", sa.Integer()),
        sa.Column("pattern", sa.String(200)),
        sa.Column("visible_roles", sa.JSON()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("group_key", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.Uuid()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("entity_type", "key", name="uq_custom_field_defs_entity_key"),
    )
    op.create_index("ix_custom_field_defs_entity_type", "custom_field_defs", ["entity_type"])


def downgrade() -> None:
    op.drop_table("custom_field_defs")
