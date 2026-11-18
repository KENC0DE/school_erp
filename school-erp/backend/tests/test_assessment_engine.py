"""P4-01: table-driven tests for the pure assessment engine."""

from __future__ import annotations

from decimal import Decimal

import pytest
from modules.assessment.engine import (
    AggregationMode,
    Component,
    RoundingMode,
    Score,
    ScoreStatus,
    YearMode,
    YearRule,
    aggregate,
    component_value,
    converted_score,
    round_mark,
    score_percent,
    term_total,
    year_result,
)


def quiz(raw: int | str | None, out_of: int | str = 10, **kwargs) -> Score:
    return Score(out_of=out_of, raw=raw, **kwargs)


def test_guide_examples_convert_to_a_ten_point_scale():
    assert score_percent(Score(out_of=15, raw=12)) == Decimal("0.8")
    assert converted_score(Score(out_of=15, raw=12), max_points=10, precision=1) == Decimal("8.0")

    assert score_percent(Score(out_of=13, raw=9)) == Decimal(9) / Decimal(13)
    assert converted_score(Score(out_of=13, raw=9), max_points=10, precision=1) == Decimal("6.9")


def test_component_average_of_two_quizzes_rounds_once():
    component = Component(
        key="quizzes",
        max_points=10,
        scores=(Score(out_of=15, raw=12), Score(out_of=13, raw=9)),
    )
    # (0.8 + 9/13) / 2 * 10 = 7.4615… -> 7.5 at one decimal.
    assert component_value(component, precision=1) == Decimal("7.5")


def test_absent_is_zero_or_excluded_by_component_setting():
    scores = (Score(out_of=15, raw=12), Score(out_of=10, status=ScoreStatus.ABSENT))

    counted = Component(
        key="quizzes",
        max_points=10,
        scores=scores,
        absent_counts_as_zero=True,
    )
    excluded = Component(
        key="quizzes",
        max_points=10,
        scores=scores,
        absent_counts_as_zero=False,
    )

    assert component_value(counted, precision=1) == Decimal("4.0")
    assert component_value(excluded, precision=1) == Decimal("8.0")


@pytest.mark.parametrize(
    "status",
    [ScoreStatus.EXCUSED, ScoreStatus.EXEMPT, ScoreStatus.NOT_TAKEN],
)
def test_other_non_present_statuses_are_always_excluded(status):
    component = Component(
        key="quizzes",
        max_points=10,
        scores=(Score(out_of=15, raw=12), Score(out_of=10, status=status)),
        absent_counts_as_zero=True,
    )
    assert component_value(component, precision=1) == Decimal("8.0")


def test_weighted_average_uses_each_score_weight():
    component = Component(
        key="coursework",
        max_points=10,
        aggregation=AggregationMode.WEIGHTED_AVERAGE,
        scores=(
            Score(out_of=10, raw=8, weight=1),
            Score(out_of=10, raw=6, weight=3),
        ),
    )
    # (0.8 * 1 + 0.6 * 3) / 4 = 0.65 -> 6.5
    assert component_value(component, precision=1) == Decimal("6.5")


def test_best_n_keeps_the_highest_scores():
    component = Component(
        key="quizzes",
        max_points=10,
        aggregation=AggregationMode.BEST_N,
        best_n=2,
        scores=(quiz(5), quiz(10), quiz(75, out_of=100)),
    )
    assert component_value(component, precision=2) == Decimal("8.75")


def test_sum_capped_caps_the_sum_of_percents():
    component = Component(
        key="participation",
        max_points=10,
        aggregation=AggregationMode.SUM_CAPPED,
        cap=1,
        scores=(quiz(6), quiz(5)),
    )
    assert component_value(component, precision=2) == Decimal("10.00")

    generous = Component(
        key="participation",
        max_points=10,
        aggregation=AggregationMode.SUM_CAPPED,
        cap=Decimal("1.5"),
        scores=(quiz(6), quiz(5)),
    )
    assert component_value(generous, precision=2) == Decimal("11.00")


def test_latest_uses_input_order_after_excluded_scores_are_removed():
    component = Component(
        key="reading",
        max_points=10,
        aggregation=AggregationMode.LATEST,
        scores=(
            quiz(5),
            quiz(None, status=ScoreStatus.EXCUSED),
            quiz(75, out_of=100),
        ),
    )
    assert component_value(component, precision=2) == Decimal("7.50")


def test_term_total_sums_rounded_component_values():
    quizzes = Component(key="quizzes", max_points=10, scores=(Score(out_of=15, raw=12),))
    exam = Component(key="exam", max_points=10, scores=(Score(out_of=13, raw=9),))
    assert term_total((quizzes, exam), precision=1) == Decimal("14.9")


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        (YearRule(mode=YearMode.AVERAGE), Decimal("80.00")),
        (YearRule(mode=YearMode.SUM), Decimal("240.00")),
        (
            YearRule(mode=YearMode.WEIGHTED_AVERAGE, weights=(1, 1, 2)),
            Decimal("77.50"),
        ),
    ],
)
def test_year_rules_combine_terms(rule, expected):
    terms = (Decimal("80"), Decimal("90"), Decimal("70"))
    assert year_result(terms, rule) == expected


def test_year_rules_ignore_missing_terms_and_return_none_when_empty():
    rule = YearRule(mode=YearMode.AVERAGE)
    assert year_result((Decimal("80"), None, Decimal("90")), rule) == Decimal("85.00")
    assert year_result((None, None), rule) is None


def test_bonus_marks_require_the_assessment_flag():
    with pytest.raises(ValueError, match="bonus"):
        score_percent(Score(out_of=10, raw=11))

    assert score_percent(Score(out_of=10, raw=11, allow_bonus=True)) == Decimal("1.1")
    assert converted_score(Score(out_of=10, raw=11, allow_bonus=True), max_points=10, precision=1) == Decimal(
        "11.0"
    )


def test_invalid_scores_are_rejected():
    with pytest.raises(ValueError, match="greater than zero"):
        score_percent(Score(out_of=0, raw=0))
    with pytest.raises(ValueError, match="greater than zero"):
        score_percent(Score(out_of=-5, raw=0))
    with pytest.raises(ValueError, match="raw value"):
        score_percent(Score(out_of=10))
    with pytest.raises(ValueError, match="negative"):
        score_percent(Score(out_of=10, raw=-1))


def test_empty_or_fully_excluded_components_return_none():
    no_scores = Component(key="quizzes", max_points=10)
    only_excused = Component(
        key="quizzes",
        max_points=10,
        scores=(Score(out_of=10, status=ScoreStatus.EXCUSED),),
    )
    assert component_value(no_scores) is None
    assert component_value(only_excused) is None
    assert term_total((no_scores, only_excused)) is None
    assert aggregate([], AggregationMode.AVERAGE) is None


def test_invalid_aggregation_configuration_is_clear():
    with pytest.raises(ValueError, match="one weight per"):
        aggregate([Decimal("0.5")], AggregationMode.WEIGHTED_AVERAGE)
    with pytest.raises(ValueError, match="sum to more than zero"):
        aggregate(
            [Decimal("0.5")],
            AggregationMode.WEIGHTED_AVERAGE,
            weights=[0],
        )
    with pytest.raises(ValueError, match="integer count"):
        aggregate([Decimal("0.5")], AggregationMode.BEST_N)
    with pytest.raises(ValueError, match="greater than zero"):
        aggregate([Decimal("0.5")], AggregationMode.BEST_N, best_n=0)
    with pytest.raises(ValueError, match="cap"):
        aggregate([Decimal("0.5")], AggregationMode.SUM_CAPPED, cap=-1)
    with pytest.raises(ValueError, match="one weight per term"):
        year_result(
            [Decimal("80")],
            YearRule(mode=YearMode.WEIGHTED_AVERAGE, weights=(1, 2)),
        )
    with pytest.raises(ValueError, match="sum to more than zero"):
        year_result(
            [Decimal("80")],
            YearRule(mode=YearMode.WEIGHTED_AVERAGE, weights=(0,)),
        )


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (RoundingMode.HALF_UP, Decimal("3")),
        (RoundingMode.HALF_EVEN, Decimal("2")),
        (RoundingMode.HALF_DOWN, Decimal("2")),
        (RoundingMode.UP, Decimal("3")),
        (RoundingMode.DOWN, Decimal("2")),
        (RoundingMode.CEILING, Decimal("3")),
        (RoundingMode.FLOOR, Decimal("2")),
    ],
)
def test_rounding_modes(mode, expected):
    assert round_mark(Decimal("2.5"), precision=0, rounding=mode) == expected


def test_rounding_rejects_bad_precision():
    with pytest.raises(ValueError, match="between"):
        round_mark(Decimal("1"), precision=-1)
    with pytest.raises(ValueError, match="between"):
        round_mark(Decimal("1"), precision=7)
    with pytest.raises(TypeError, match="integer"):
        round_mark(Decimal("1"), precision=1.5)


def test_extreme_decimals_keep_exact_arithmetic():
    score = Score(out_of=1, raw=Decimal("0.1234567890123456789012345678"))
    assert converted_score(score, max_points=100, precision=6) == Decimal("12.345679")


def test_floats_are_rejected_everywhere():
    with pytest.raises(TypeError, match="Decimal"):
        score_percent(Score(out_of=10.0, raw=5.0))
    with pytest.raises(TypeError, match="Decimal"):
        aggregate([0.5], AggregationMode.AVERAGE)
    with pytest.raises(TypeError, match="Decimal"):
        Component(key="quiz", max_points=10.0)
