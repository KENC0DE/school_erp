"""document templates and numbered versions

Revision ID: 0030_documents
Revises: 0029_portal_links

A template owns its layout through versions: only a draft can change, a published
version is immutable, and generation records the version it used. The partial
unique index allows at most one live draft per template.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_documents"
down_revision: str | None = "0029_portal_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIVE_WHERE = sa.text("deleted_at IS NULL")
DRAFT_WHERE = sa.text("status = 'draft' AND deleted_at IS NULL")
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
    op.create_table(
        "doc_templates",
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("doc_type", sa.String(40), nullable=False),
        *_business_columns(),
    )
    op.create_index(
        "uq_doc_templates_key_live",
        "doc_templates",
        ["key"],
        unique=True,
        sqlite_where=LIVE_WHERE,
        postgresql_where=LIVE_WHERE,
    )
    op.create_index("ix_doc_templates_type", "doc_templates", ["doc_type"])

    op.create_table(
        "doc_template_versions",
        sa.Column(
            "template_id",
            sa.Uuid(),
            sa.ForeignKey("doc_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("layout", JSON_TYPE, nullable=False),
        sa.Column("change_note", sa.String(500)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("published_by", sa.Uuid()),
        *_business_columns(),
    )
    op.create_index(
        "uq_doc_template_versions_number",
        "doc_template_versions",
        ["template_id", "version_number"],
        unique=True,
    )
    op.create_index(
        "uq_doc_template_versions_draft",
        "doc_template_versions",
        ["template_id"],
        unique=True,
        sqlite_where=DRAFT_WHERE,
        postgresql_where=DRAFT_WHERE,
    )
    op.create_index(
        "ix_doc_template_versions_template",
        "doc_template_versions",
        ["template_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("doc_template_versions")
    op.drop_table("doc_templates")
