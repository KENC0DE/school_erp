"""Staff-number generation with an atomic global sequence.

Staff numbers are not part of the school's configurable student numbering: a
single ``STF-{year}-{seq:04d}`` format keeps the demo and the API predictable.
An explicit number may always be supplied, which is how imported records keep
their historical identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.db.base import uuid7
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from modules.staff.models import StaffNumberSequence

SCOPE = "staff"


@dataclass(frozen=True)
class Allocation:
    staff_number: str
    scope: str
    year: int
    sequence: int


def _render(year: int, sequence: int) -> Allocation:
    return Allocation(
        staff_number=f"STF-{year}-{sequence:04d}",
        scope=SCOPE,
        year=year,
        sequence=sequence,
    )


async def _next_value(session: AsyncSession, start: int = 1) -> int:
    table = StaffNumberSequence.__table__
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        statement = pg_insert(table)
    elif dialect == "sqlite":
        statement = sqlite_insert(table)
    else:  # pragma: no cover - only the two supported databases reach here
        raise RuntimeError(f"Staff numbering is not implemented for {dialect}")
    statement = (
        statement.values(id=uuid7(), scope=SCOPE, value=start)
        .on_conflict_do_update(
            index_elements=[table.c.scope],
            set_={"value": table.c.value + 1, "updated_at": func.now()},
        )
        .returning(table.c.value)
    )
    return int((await session.execute(statement)).scalar_one())


async def allocate_number(session: AsyncSession) -> Allocation:
    """Reserve the next staff number and commit the counter immediately."""
    await session.commit()  # end any read transaction before writing the counter
    sequence = await _next_value(session)
    await session.commit()
    return _render(date.today().year, sequence)


async def peek_number(session: AsyncSession) -> Allocation:
    """Return the candidate number without reserving it."""
    current = (
        await session.execute(select(StaffNumberSequence.value).where(StaffNumberSequence.scope == SCOPE))
    ).scalar_one_or_none()
    return _render(date.today().year, 1 if current is None else current + 1)


__all__ = ["Allocation", "allocate_number", "peek_number"]
