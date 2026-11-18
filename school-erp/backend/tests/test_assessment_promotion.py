"""P4-03: ranking tie modes, promotion rules and the promotion-flow adapter."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from modules.assessment.promotion import (
    PromotionPolicy,
    SubjectResult,
    decide_promotion,
    decide_promotions,
    subject_minimum,
)
from modules.assessment.ranking import RankedStudent, TieMode, rank_students
from modules.students.progression_rules import promotion_rule_resolver


def test_competition_ranking_skips_after_a_tie():
    ranked = rank_students({"a": 90, "b": 90, "c": 80, "d": 70}, tie_mode=TieMode.COMPETITION)
    assert [(row.student_id, row.rank, row.position, row.tied) for row in ranked] == [
        ("a", 1, 1, True),
        ("b", 1, 2, True),
        ("c", 3, 3, False),
        ("d", 4, 4, False),
    ]


def test_dense_ranking_uses_the_next_number_after_a_tie():
    ranked = rank_students({"a": 90, "b": 90, "c": 80, "d": 70}, tie_mode=TieMode.DENSE)
    assert [row.rank for row in ranked] == [1, 1, 2, 3]


def test_ordinal_ranking_breaks_ties_by_input_order():
    ranked = rank_students({"a": 90, "b": 90, "c": 80}, tie_mode=TieMode.ORDINAL)
    assert [row.rank for row in ranked] == [1, 2, 3]
    assert [row.student_id for row in ranked] == ["a", "b", "c"]
    assert all(isinstance(row, RankedStudent) for row in ranked)


def test_ranking_accepts_decimal_strings_and_handles_empty_input():
    ranked = rank_students({"a": "89.99", "b": Decimal("90")})
    assert ranked[0].student_id == "b"
    assert ranked[1].value == Decimal("89.99")
    assert rank_students({}) == []
    with pytest.raises(ValueError, match="tie mode"):
        rank_students({"a": 1}, tie_mode="competition")  # type: ignore[arg-type]


def policy(**overrides) -> PromotionPolicy:
    values = {
        "min_average": 75,
        "max_failed_subjects": 0,
        "pass_mark": 50,
    }
    values.update(overrides)
    return PromotionPolicy(**values)


def test_minimum_average_and_per_subject_minimums_decide_promotion():
    pass_decision = decide_promotion(
        "s1",
        [
            SubjectResult("math", 80),
            SubjectResult("english", 75),
            SubjectResult("science", 70),
        ],
        policy(),
    )
    assert pass_decision.promote is True
    assert pass_decision.action == "promote"
    assert pass_decision.average == Decimal("75.00")
    assert pass_decision.failed_subjects == ()
    assert pass_decision.reasons == ()

    fail_average = decide_promotion(
        "s2",
        [SubjectResult("math", 74), SubjectResult("english", 74)],
        policy(),
    )
    assert fail_average.promote is False
    assert fail_average.action == "repeat"
    assert "average_below_minimum" in fail_average.reasons

    math_minimum = policy(subject_minimums={"math": 85})
    fail_subject = decide_promotion(
        "s3",
        [SubjectResult("math", 84), SubjectResult("english", 90), SubjectResult("science", 90)],
        math_minimum,
    )
    assert fail_subject.promote is False
    assert fail_subject.failed_subjects == ("math",)
    assert "too_many_failed_subjects" in fail_subject.reasons
    assert subject_minimum(math_minimum, "math") == Decimal("85")
    assert subject_minimum(math_minimum, "english") == Decimal("50")


def test_failed_subject_budget_and_exact_boundaries():
    one_failure = decide_promotion(
        "s1",
        [SubjectResult("math", Decimal("49.99")), SubjectResult("english", 90)],
        policy(min_average=65, max_failed_subjects=1),
    )
    assert one_failure.promote is True
    assert one_failure.failed_subjects == ("math",)

    too_many = decide_promotion(
        "s2",
        [
            SubjectResult("math", Decimal("49.99")),
            SubjectResult("english", Decimal("49.99")),
            SubjectResult("science", 90),
        ],
        policy(min_average=60, max_failed_subjects=1),
    )
    assert too_many.promote is False
    assert "too_many_failed_subjects" in too_many.reasons

    at_minimum = decide_promotion(
        "s3",
        [SubjectResult("math", 50), SubjectResult("english", 100)],
        policy(min_average=75),
    )
    assert at_minimum.failed_subjects == ()
    assert at_minimum.promote is True

    exact_average = decide_promotion(
        "s4",
        [SubjectResult("math", 75), SubjectResult("english", 75)],
        policy(),
    )
    assert exact_average.promote is True
    just_below = decide_promotion(
        "s5",
        [SubjectResult("math", Decimal("74.99")), SubjectResult("english", Decimal("75.00"))],
        policy(),
    )
    assert just_below.average == Decimal("75.00")
    assert just_below.promote is False


def test_promotion_policy_and_results_are_validated():
    with pytest.raises(ValueError, match="at least one"):
        decide_promotion("s1", [], policy())
    with pytest.raises(ValueError, match="student_id"):
        decide_promotion(" ", [SubjectResult("math", 80)], policy())
    with pytest.raises(ValueError, match="duplicate"):
        decide_promotion(
            "s1",
            [SubjectResult("math", 80), SubjectResult("math", 90)],
            policy(),
        )
    with pytest.raises(ValueError, match="min_average"):
        PromotionPolicy(min_average=-1)
    with pytest.raises(ValueError, match="max_failed_subjects"):
        PromotionPolicy(min_average=75, max_failed_subjects=-1)
    with pytest.raises(TypeError, match="max_failed_subjects"):
        PromotionPolicy(min_average=75, max_failed_subjects=1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="subject"):
        PromotionPolicy(min_average=75, subject_minimums={"": 80})


def test_decide_promotions_returns_one_decision_per_student():
    decisions = decide_promotions(
        {
            "a": [SubjectResult("math", 90)],
            "b": [SubjectResult("math", 10)],
        },
        policy(),
    )
    assert decisions["a"].action == "promote"
    assert decisions["b"].action == "repeat"


def candidate(student_id: str, *, final: bool = False, action: str = "promote"):
    return SimpleNamespace(
        profile=SimpleNamespace(id=student_id),
        next_level=None if final else SimpleNamespace(id="next"),
        action=action,
    )


def test_promotion_rule_resolver_plugs_into_the_existing_hook():
    results = {
        "pass": [SubjectResult("math", 80), SubjectResult("english", 80)],
        "fail": [SubjectResult("math", 40), SubjectResult("english", 80)],
    }
    resolver = promotion_rule_resolver(policy(), results)

    assert resolver(candidate("pass")) == "promote"
    assert resolver(candidate("pass", final=True)) == "graduate"
    assert resolver(candidate("fail")) == "repeat"
    assert resolver(candidate("missing", action="skip")) == "skip"
