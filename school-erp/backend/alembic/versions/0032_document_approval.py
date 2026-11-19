"""certificate approval before issuance

Revision ID: 0032_document_approval
Revises: 0031_document_generation

A certificate batch may wait for a user with ``documents.approve``. The flag is
copied onto the batch when it is requested, so a later settings change cannot
release or strand an already queued job. Existing batches are already issued or
queued, so the new column defaults to false.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_document_approval"
down_revision: str | None = "0031_document_generation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "doc_generation_batches",
        sa.Column(
            "approval_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("doc_generation_batches", sa.Column("approved_by", sa.Uuid()))
    op.add_column(
        "doc_generation_batches",
        sa.Column("approved_at", sa.DateTime(timezone=True)),
    )
    op.add_column("doc_generation_batches", sa.Column("rejection_reason", sa.Text()))


def downgrade() -> None:
    op.drop_column("doc_generation_batches", "rejection_reason")
    op.drop_column("doc_generation_batches", "approved_at")
    op.drop_column("doc_generation_batches", "approved_by")
    op.drop_column("doc_generation_batches", "approval_required")
