"""Class ranking with configurable tie handling (P4-03)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from modules.assessment.engine import Number, as_decimal


class TieMode(StrEnum):
    """How equal marks share and advance ranks."""

    COMPETITION = "competition"  # 1, 1, 3, 4
    DENSE = "dense"  # 1, 1, 2, 3
    ORDINAL = "ordinal"  # 1, 2, 3, 4 (ties keep input order)


@dataclass(frozen=True)
class RankedStudent:
    student_id: str
    value: Decimal
    rank: int
    position: int
    tied: bool


def rank_students(
    values: Mapping[str, Number],
    *,
    tie_mode: TieMode = TieMode.COMPETITION,
) -> list[RankedStudent]:
    """Rank students from highest to lowest without changing input values."""
    if not values:
        return []
    if not isinstance(tie_mode, TieMode):
        raise ValueError(f"unsupported tie mode: {tie_mode}")

    parsed = [(student_id, as_decimal(value, name="value")) for student_id, value in values.items()]
    ordered = sorted(parsed, key=lambda item: item[1], reverse=True)

    distinct_greater: dict[Decimal, int] = {}
    seen: set[Decimal] = set()
    for _, value in ordered:
        if value not in seen:
            distinct_greater[value] = len(seen)
            seen.add(value)

    occurrences: dict[Decimal, int] = {}
    for _, value in ordered:
        occurrences[value] = occurrences.get(value, 0) + 1

    ranked: list[RankedStudent] = []
    for position, (student_id, value) in enumerate(ordered, start=1):
        if tie_mode is TieMode.ORDINAL:
            rank = position
        elif tie_mode is TieMode.DENSE:
            rank = distinct_greater[value] + 1
        else:
            rank = sum(count for other, count in occurrences.items() if other > value) + 1
        ranked.append(
            RankedStudent(
                student_id=student_id,
                value=value,
                rank=rank,
                position=position,
                tied=occurrences[value] > 1,
            )
        )
    return ranked


__all__ = ["RankedStudent", "TieMode", "rank_students"]
