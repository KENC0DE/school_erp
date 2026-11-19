"""document generation batches, issued documents and numbering

Revision ID: 0031_document_generation
Revises: 0030_documents

An issued document is a durable artifact: it copies the template version's
layout and the data snapshot beside the PDF, so a reprint never depends on
today's student record or a template that has moved on. The number and the
public verification code are unique; the batch groups one request and owns the
optional combined PDF.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031_document_generation"
down_revision: str | None = "0030_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
        "doc_number_sequences",
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
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
        sa.UniqueConstraint("scope", name="uq_doc_number_sequences_scope"),
    )

    op.create_table(
        "doc_generation_batches",
        sa.Column(
            "template_id",
            sa.Uuid(),
            sa.ForeignKey("doc_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "template_version_id",
            sa.Uuid(),
            sa.ForeignKey("doc_template_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("job_id", sa.Uuid()),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("year_id", sa.Uuid()),
        sa.Column("level_id", sa.Uuid()),
        sa.Column("section_id", sa.Uuid()),
        sa.Column("student_id", sa.Uuid()),
        sa.Column("combine", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issued_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("file_id", sa.Uuid()),
        sa.Column("failure_summary", sa.Text()),
        sa.Column("context", JSON_TYPE, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True)),
        *_business_columns(),
    )
    op.create_index("ix_doc_generation_batches_template", "doc_generation_batches", ["template_id"])
    op.create_index("ix_doc_generation_batches_status", "doc_generation_batches", ["status"])

    op.create_table(
        "issued_documents",
        sa.Column(
            "template_id",
            sa.Uuid(),
            sa.ForeignKey("doc_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "template_version_id",
            sa.Uuid(),
            sa.ForeignKey("doc_template_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("template_version_number", sa.Integer(), nullable=False),
        sa.Column("doc_type", sa.String(40), nullable=False),
        sa.Column("layout", JSON_TYPE, nullable=False),
        sa.Column("data_snapshot", JSON_TYPE, nullable=False),
        sa.Column("number", sa.String(60), nullable=False),
        sa.Column("verification_code", sa.String(64), nullable=False),
        sa.Column("issuer_id", sa.Uuid()),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("file_id", sa.Uuid()),
        sa.Column("batch_id", sa.Uuid()),
        sa.Column("recipient_type", sa.String(30), nullable=False),
        sa.Column("recipient_id", sa.Uuid()),
        sa.Column("recipient_name", sa.String(200), nullable=False),
        *_business_columns(),
    )
    op.create_index("uq_issued_documents_number", "issued_documents", ["number"], unique=True)
    op.create_index(
        "uq_issued_documents_verification",
        "issued_documents",
        ["verification_code"],
        unique=True,
    )
    op.create_index("ix_issued_documents_template", "issued_documents", ["template_id"])
    op.create_index("ix_issued_documents_batch", "issued_documents", ["batch_id"])
    op.create_index(
        "ix_issued_documents_recipient",
        "issued_documents",
        ["recipient_type", "recipient_id"],
    )
    op.create_index("ix_issued_documents_issued_at", "issued_documents", ["issued_at"])


def downgrade() -> None:
    op.drop_table("issued_documents")
    op.drop_table("doc_generation_batches")
    op.drop_table("doc_number_sequences")
