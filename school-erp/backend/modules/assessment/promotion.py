"""Promotion rules: minimum average, failed subjects and per-subject minima (P4-03)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from modules.assessment.engine import Number, RoundingMode, as_decimal, round_mark


@dataclass(frozen=True)
class SubjectResult:
    subject: str
    total: Number


@dataclass(frozen=True)
class PromotionPolicy:
    min_average: Number
    max_failed_subjects: int = 0
    pass_mark: Number = 50
    subject_minimums: Mapping[str, Number] = field(default_factory=dict)
    precision: int = 2
    rounding: RoundingMode = RoundingMode.HALF_UP

    def __post_init__(self) -> None:
        if as_decimal(self.min_average, name="min_average") < 0:
            raise ValueError("min_average cannot be negative")
        if isinstance(self.max_failed_subjects, bool) or not isinstance(self.max_failed_subjects, int):
            raise TypeError("max_failed_subjects must be an integer")
        if self.max_failed_subjects < 0:
            raise ValueError("max_failed_subjects cannot be negative")
        if as_decimal(self.pass_mark, name="pass_mark") < 0:
            raise ValueError("pass_mark cannot be negative")
        for subject, minimum in self.subject_minimums.items():
            if not subject or not subject.strip():
                raise ValueError("subject_minimums needs non-empty subject keys")
            if as_decimal(minimum, name=f"subject minimum for {subject}") < 0:
                raise ValueError("subject minimums cannot be negative")
        if isinstance(self.precision, bool) or not isinstance(self.precision, int):
            raise TypeError("precision must be an integer")
        if self.precision < 0 or self.precision > 6:
            raise ValueError("precision must be between 0 and 6")


@dataclass(frozen=True)
class PromotionDecision:
    student_id: str
    promote: bool
    action: str
    average: Decimal
    failed_subjects: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


def subject_minimum(policy: PromotionPolicy, subject: str) -> Decimal:
    override = policy.subject_minimums.get(subject)
    return as_decimal(
        override if override is not None else policy.pass_mark,
        name=f"minimum for {subject}",
    )


def decide_promotion(
    student_id: str,
    subjects: Sequence[SubjectResult],
    policy: PromotionPolicy,
) -> PromotionDecision:
    """Decide one student's action from subject totals.

    The comparison uses exact totals; ``average`` is rounded only for display.
    A mark exactly at the minimum passes. ``subject_minimums`` overrides the
    policy ``pass_mark`` for the named subject.
    """
    if not student_id or not student_id.strip():
        raise ValueError("student_id is required")
    if not subjects:
        raise ValueError("at least one subject result is required")

    seen: set[str] = set()
    totals: list[tuple[str, Decimal]] = []
    for result in subjects:
        if not result.subject or not result.subject.strip():
            raise ValueError("subject result needs a subject key")
        if result.subject in seen:
            raise ValueError(f"duplicate subject result: {result.subject}")
        seen.add(result.subject)
        totals.append((result.subject, as_decimal(result.total, name=f"total for {result.subject}")))

    average = sum((total for _, total in totals), Decimal(0)) / len(totals)
    failed = tuple(subject for subject, total in totals if total < subject_minimum(policy, subject))

    reasons: list[str] = []
    if average < as_decimal(policy.min_average, name="min_average"):
        reasons.append("average_below_minimum")
    if len(failed) > policy.max_failed_subjects:
        reasons.append("too_many_failed_subjects")

    promote = not reasons
    return PromotionDecision(
        student_id=student_id,
        promote=promote,
        action="promote" if promote else "repeat",
        average=round_mark(average, precision=policy.precision, rounding=policy.rounding),
        failed_subjects=failed,
        reasons=tuple(reasons),
    )


def decide_promotions(
    results_by_student: Mapping[str, Sequence[SubjectResult]],
    policy: PromotionPolicy,
) -> dict[str, PromotionDecision]:
    return {
        student_id: decide_promotion(student_id, subjects, policy)
        for student_id, subjects in results_by_student.items()
    }


__all__ = [
    "PromotionDecision",
    "PromotionPolicy",
    "SubjectResult",
    "decide_promotion",
    "decide_promotions",
    "subject_minimum",
]
