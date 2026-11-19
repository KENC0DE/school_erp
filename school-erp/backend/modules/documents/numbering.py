"""Document numbers and public verification codes (P5-08).

A number is allocated with one atomic dialect upsert, exactly like the student
and admission sequences. The scope is the Gregorian calendar year, so the
printed number reads ``DOC-2026-00001`` and starts again each January. The
public verification code is independent of the number: it is random and
unguessable, because knowing a serial must not let anyone enumerate the
verification pages.
"""

from __future__ import annotations

import secrets

from core.db.base import uuid7
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from modules.documents.models import DocumentNumberSequence, IssuedDocument

NUMBER_FORMAT = "DOC-{year}-{seq:05d}"
VERIFICATION_BYTES = 12


async def _next_value(session: AsyncSession, scope: str, start: int) -> int:
    table = DocumentNumberSequence.__table__
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        statement = pg_insert(table)
    elif dialect == "sqlite":
        statement = sqlite_insert(table)
    else:  # pragma: no cover - only the two supported databases reach here
        raise RuntimeError(f"Document numbering is not implemented for {dialect}")
    statement = (
        statement.values(id=uuid7(), scope=scope, value=start)
        .on_conflict_do_update(
            index_elements=[table.c.scope],
            set_={"value": table.c.value + 1, "updated_at": func.now()},
        )
        .returning(table.c.value)
    )
    return int((await session.execute(statement)).scalar_one())


async def allocate_number(session: AsyncSession, *, year: int) -> str:
    """Reserve the next number for ``year`` without committing.

    The caller commits the document it belongs to. A failed transaction leaves
    a gap, which is the safe failure: a number that reached paper is never
    reissued.
    """
    sequence = await _next_value(session, str(year), 1)
    return NUMBER_FORMAT.format(year=year, seq=sequence)


async def _taken(session: AsyncSession, code: str) -> bool:
    row = await session.execute(select(IssuedDocument.id).where(IssuedDocument.verification_code == code))
    return row.scalar_one_or_none() is not None


async def new_verification_code(session: AsyncSession) -> str:
    """A fresh URL-safe code, checked against the unique index."""
    for _ in range(8):  # pragma: no branch - a collision is astronomically unlikely
        code = secrets.token_urlsafe(VERIFICATION_BYTES)
        if not await _taken(session, code):
            return code
    raise RuntimeError("Could not allocate a unique document verification code")


__all__ = [
    "NUMBER_FORMAT",
    "VERIFICATION_BYTES",
    "allocate_number",
    "new_verification_code",
]
