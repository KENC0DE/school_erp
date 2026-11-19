"""files: object metadata, ownership and thumbnails

Revision ID: 0013_files
Revises: 0012_theme_manager
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_files"
down_revision: str | None = "0012_theme_manager"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("owner_entity_type", sa.String(length=80), nullable=True),
        sa.Column("owner_entity_id", sa.String(length=80), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("thumbnail_key", sa.String(length=255), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_files_owner", "files", ["owner_entity_type", "owner_entity_id"])
    op.create_index("ix_files_deleted_at", "files", ["deleted_at"])
    op.create_index(
        "uq_files_object_key_live",
        "files",
        ["object_key"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_files_object_key_live", table_name="files")
    op.drop_index("ix_files_deleted_at", table_name="files")
    op.drop_index("ix_files_owner", table_name="files")
    op.drop_table("files")
