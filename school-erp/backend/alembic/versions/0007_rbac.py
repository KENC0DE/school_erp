"""rbac: role activity, scoped overrides and delegation audit fields

Revision ID: 0007_rbac
Revises: 0006_auth_hardening
Create Date: 2026-11-17 22:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_rbac"
down_revision: str | None = "0006_auth_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column("user_permission_overrides", sa.Column("reason", sa.String(length=500), nullable=True))
    op.add_column("user_permission_overrides", sa.Column("granted_by", sa.Uuid(), nullable=True))
    op.create_index(
        "ix_user_permission_overrides_expires_at",
        "user_permission_overrides",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "uq_user_override_scope",
        "user_permission_overrides",
        ["user_id", "permission", "scope"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_user_override_scope", table_name="user_permission_overrides")
    op.drop_index(
        "ix_user_permission_overrides_expires_at",
        table_name="user_permission_overrides",
    )
    op.drop_column("user_permission_overrides", "granted_by")
    op.drop_column("user_permission_overrides", "reason")
    op.drop_column("roles", "is_active")
