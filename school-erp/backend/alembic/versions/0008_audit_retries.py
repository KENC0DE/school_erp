"""audit: shipping retries with backoff

Revision ID: 0008_audit_retries
Revises: 0007_rbac
Create Date: 2026-11-17 23:30:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_audit_retries"
down_revision: str | None = "0007_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_outbox", sa.Column("available_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("audit_outbox", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("audit_outbox", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_outbox", "last_error")
    op.drop_column("audit_outbox", "last_attempt_at")
    op.drop_column("audit_outbox", "available_at")
