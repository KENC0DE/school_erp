"""staff-targeted document generation

Revision ID: 0033_document_staff
Revises: 0032_document_approval

Experience letters and staff certificates are generated for one staff member.
The batch keeps that staff id beside the existing student id; the columns are
plain UUIDs because documents already refer to recipients across modules
without foreign keys that would block a module being disabled.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_document_staff"
down_revision: str | None = "0032_document_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("doc_generation_batches", sa.Column("staff_id", sa.Uuid()))


def downgrade() -> None:
    op.drop_column("doc_generation_batches", "staff_id")
