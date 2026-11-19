"""Default soft-delete filtering for ORM selects (ARCH §5.1).

Importing this module registers a session event that hides soft-deleted rows
from every ORM select unless the caller opts in with
``execution_options(include_deleted=True)``. Restore paths use that option;
normal reads cannot accidentally resurface deleted records.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from core.db.base import SoftDeleteMixin

INCLUDE_DELETED = "include_deleted"


@event.listens_for(Session, "do_orm_execute")
def _exclude_soft_deleted(execute_state) -> None:  # type: ignore[no-untyped-def]
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get(INCLUDE_DELETED):
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.deleted_at.is_(None),
            include_aliases=True,
        )
    )


__all__ = ["INCLUDE_DELETED"]
