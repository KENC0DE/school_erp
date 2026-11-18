"""Bridge the pure P4-03 promotion policy into the P2-11 promotion hook.

P4-08 will build ``results_by_student`` from published term results and pass
``promotion_rule_resolver(...)`` to ``preview_promotion``/``apply_promotion``.
Keeping the adapter here means the assessment module stays free of student
models while the promotion flow stays free of assessment tables.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from modules.assessment.promotion import (
    PromotionPolicy,
    SubjectResult,
    decide_promotion,
)


class PromotionCandidate(Protocol):
    profile: Any
    next_level: Any
    action: str


def promotion_rule_resolver(
    policy: PromotionPolicy,
    results_by_student: Mapping[str, Sequence[SubjectResult]],
):
    """Return a resolver compatible with ``RuleResolver`` in progression_service.

    A student without results keeps the flow's level-based default. A student
    with results repeats when the policy fails and promotes otherwise; at the
    final level a pass graduates instead.
    """

    def resolve(candidate: PromotionCandidate) -> str:
        student_id = str(candidate.profile.id)
        subjects = results_by_student.get(student_id)
        if not subjects:
            return candidate.action
        decision = decide_promotion(student_id, subjects, policy)
        if not decision.promote:
            return "repeat"
        return "graduate" if candidate.next_level is None else "promote"

    return resolve


__all__ = ["PromotionCandidate", "promotion_rule_resolver"]
