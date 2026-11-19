"""Pure mark conversion and aggregation rules (P4-01).

No database or framework imports live here: later assessment APIs call these
functions and store the results. Every value is a :class:`~decimal.Decimal`;
floats are rejected so a binary rounding error can never enter a mark.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Decimal,
    InvalidOperation,
)
from enum import StrEnum


class ScoreStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    EXCUSED = "excused"
    EXEMPT = "exempt"
    NOT_TAKEN = "not_taken"


class AggregationMode(StrEnum):
    AVERAGE = "average"
    WEIGHTED_AVERAGE = "weighted_average"
    BEST_N = "best_n"
    SUM_CAPPED = "sum_capped"
    LATEST = "latest"


class YearMode(StrEnum):
    AVERAGE = "average"
    SUM = "sum"
    WEIGHTED_AVERAGE = "weighted_average"


class RoundingMode(StrEnum):
    HALF_UP = "half_up"
    HALF_EVEN = "half_even"
    HALF_DOWN = "half_down"
    UP = "up"
    DOWN = "down"
    CEILING = "ceiling"
    FLOOR = "floor"


_ROUNDING = {
    RoundingMode.HALF_UP: ROUND_HALF_UP,
    RoundingMode.HALF_EVEN: ROUND_HALF_EVEN,
    RoundingMode.HALF_DOWN: ROUND_HALF_DOWN,
    RoundingMode.UP: ROUND_UP,
    RoundingMode.DOWN: ROUND_DOWN,
    RoundingMode.CEILING: ROUND_CEILING,
    RoundingMode.FLOOR: ROUND_FLOOR,
}

Number = Decimal | int | str
MAX_PRECISION = 6


def as_decimal(value: Number, *, name: str = "value") -> Decimal:
    """Convert an exact input to Decimal; floats are deliberately rejected."""
    if isinstance(value, bool):
        raise TypeError(f"{name} must be Decimal, int or str, not bool")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, str):
        try:
            result = Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValueError(f"{name} is not a decimal number: {value!r}") from exc
    else:
        raise TypeError(f"{name} must be Decimal, int or str, not {type(value).__name__}")
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def round_mark(
    value: Number,
    *,
    precision: int = 2,
    rounding: RoundingMode = RoundingMode.HALF_UP,
) -> Decimal:
    """Round a mark to a fixed number of decimal places."""
    if isinstance(precision, bool) or not isinstance(precision, int):
        raise TypeError("precision must be an integer")
    if precision < 0 or precision > MAX_PRECISION:
        raise ValueError(f"precision must be between 0 and {MAX_PRECISION}")
    number = as_decimal(value)
    quantum = Decimal(1).scaleb(-precision)
    try:
        return number.quantize(quantum, rounding=_ROUNDING[rounding])
    except InvalidOperation as exc:
        raise ValueError("value is too large to round at this precision") from exc


@dataclass(frozen=True)
class Score:
    """One assessment score for one student.

    ``out_of`` is copied from the assessment. ``raw`` is required only for a
    present score; the other statuses are handled by the component setting.
    ``weight`` is used by ``weighted_average``.
    """

    out_of: Number
    raw: Number | None = None
    status: ScoreStatus = ScoreStatus.PRESENT
    weight: Number | None = None
    allow_bonus: bool = False


@dataclass(frozen=True)
class Component:
    """A mark-structure component (quizzes, mid-exam, final, …)."""

    key: str
    max_points: Number
    scores: Sequence[Score] = ()
    aggregation: AggregationMode = AggregationMode.AVERAGE
    absent_counts_as_zero: bool = False
    best_n: int | None = None
    cap: Number | None = None

    def __post_init__(self) -> None:
        if not self.key or not self.key.strip():
            raise ValueError("component key is required")
        if as_decimal(self.max_points, name="max_points") <= 0:
            raise ValueError("max_points must be greater than zero")


@dataclass(frozen=True)
class YearRule:
    """How term totals combine into a year result."""

    mode: YearMode = YearMode.AVERAGE
    weights: Sequence[Number] | None = None


def score_percent(
    score: Score,
    *,
    absent_counts_as_zero: bool = False,
) -> Decimal | None:
    """Return the score as a fraction of its ``out_of``, or None if excluded.

    ``excused``, ``exempt`` and ``not_taken`` are always excluded. ``absent``
    is excluded by default and becomes zero only when the component says so.
    """
    out_of = as_decimal(score.out_of, name="out_of")
    if out_of <= 0:
        raise ValueError("out_of must be greater than zero")

    if score.status is ScoreStatus.PRESENT:
        if score.raw is None:
            raise ValueError("a present score needs a raw value")
        raw = as_decimal(score.raw, name="raw")
        if raw < 0:
            raise ValueError("raw score cannot be negative")
        if raw > out_of and not score.allow_bonus:
            raise ValueError("raw score cannot exceed out_of unless bonus marks are enabled")
        return raw / out_of

    if score.status is ScoreStatus.ABSENT:
        return Decimal(0) if absent_counts_as_zero else None
    return None


def converted_score(
    score: Score,
    *,
    max_points: Number,
    absent_counts_as_zero: bool = False,
    precision: int = 2,
    rounding: RoundingMode = RoundingMode.HALF_UP,
) -> Decimal | None:
    """Convert one score onto a component's point scale (for storage)."""
    target = as_decimal(max_points, name="max_points")
    if target <= 0:
        raise ValueError("max_points must be greater than zero")
    percent = score_percent(score, absent_counts_as_zero=absent_counts_as_zero)
    if percent is None:
        return None
    return round_mark(percent * target, precision=precision, rounding=rounding)


def aggregate(
    percents: Sequence[Decimal],
    mode: AggregationMode,
    *,
    weights: Sequence[Number] | None = None,
    best_n: int | None = None,
    cap: Number | None = None,
) -> Decimal | None:
    """Aggregate included percents. Excluded scores must already be removed."""
    if not percents:
        return None
    values = [as_decimal(percent, name="percent") for percent in percents]
    if any(percent < 0 for percent in values):
        raise ValueError("percents cannot be negative")

    if mode is AggregationMode.AVERAGE:
        return sum(values, Decimal(0)) / len(values)

    if mode is AggregationMode.WEIGHTED_AVERAGE:
        if weights is None or len(weights) != len(values):
            raise ValueError("weighted_average needs one weight per included score")
        parsed = [as_decimal(weight, name="weight") for weight in weights]
        if any(weight < 0 for weight in parsed):
            raise ValueError("weights cannot be negative")
        total_weight = sum(parsed, Decimal(0))
        if total_weight <= 0:
            raise ValueError("the weights of included scores must sum to more than zero")
        return (
            sum((value * weight for value, weight in zip(values, parsed, strict=True)), Decimal(0))
            / total_weight
        )

    if mode is AggregationMode.BEST_N:
        if isinstance(best_n, bool) or not isinstance(best_n, int):
            raise ValueError("best_n needs an integer count")
        if best_n <= 0:
            raise ValueError("best_n must be greater than zero")
        chosen = sorted(values, reverse=True)[:best_n]
        return sum(chosen, Decimal(0)) / len(chosen)

    if mode is AggregationMode.SUM_CAPPED:
        cap_value = Decimal(1) if cap is None else as_decimal(cap, name="cap")
        if cap_value < 0:
            raise ValueError("cap cannot be negative")
        return min(sum(values, Decimal(0)), cap_value)

    if mode is AggregationMode.LATEST:
        return values[-1]

    raise ValueError(f"unsupported aggregation mode: {mode}")


def component_value(
    component: Component,
    *,
    precision: int = 2,
    rounding: RoundingMode = RoundingMode.HALF_UP,
) -> Decimal | None:
    """Aggregate a component's percents, scale to its max, then round once."""
    max_points = as_decimal(component.max_points, name="max_points")
    included: list[Score] = []
    percents: list[Decimal] = []
    for score in component.scores:
        percent = score_percent(score, absent_counts_as_zero=component.absent_counts_as_zero)
        if percent is not None:
            included.append(score)
            percents.append(percent)
    if not percents:
        return None

    weights = None
    if component.aggregation is AggregationMode.WEIGHTED_AVERAGE:
        weights = []
        for score in included:
            if score.weight is None:
                raise ValueError("weighted_average needs a weight on every included score")
            weights.append(score.weight)

    aggregated = aggregate(
        percents,
        component.aggregation,
        weights=weights,
        best_n=component.best_n,
        cap=component.cap,
    )
    if aggregated is None:
        return None
    return round_mark(aggregated * max_points, precision=precision, rounding=rounding)


def term_total(
    components: Sequence[Component],
    *,
    precision: int = 2,
    rounding: RoundingMode = RoundingMode.HALF_UP,
) -> Decimal | None:
    """Sum rounded component values for one term; None when nothing counts."""
    values = [
        value
        for component in components
        if (value := component_value(component, precision=precision, rounding=rounding)) is not None
    ]
    if not values:
        return None
    return round_mark(sum(values, Decimal(0)), precision=precision, rounding=rounding)


def year_result(
    terms: Sequence[Number | None],
    rule: YearRule | None = None,
    *,
    precision: int = 2,
    rounding: RoundingMode = RoundingMode.HALF_UP,
) -> Decimal | None:
    """Combine term totals into a year result according to ``rule``."""
    rule = rule or YearRule()
    present = [
        (index, as_decimal(term, name="term total")) for index, term in enumerate(terms) if term is not None
    ]
    if not present:
        return None

    if rule.mode is YearMode.SUM:
        result = sum((value for _, value in present), Decimal(0))
    elif rule.mode is YearMode.AVERAGE:
        result = sum((value for _, value in present), Decimal(0)) / len(present)
    elif rule.mode is YearMode.WEIGHTED_AVERAGE:
        if rule.weights is None or len(rule.weights) != len(terms):
            raise ValueError("weighted_average needs one weight per term")
        parsed = [as_decimal(weight, name="weight") for weight in rule.weights]
        if any(weight < 0 for weight in parsed):
            raise ValueError("weights cannot be negative")
        total_weight = sum((parsed[index] for index, _ in present), Decimal(0))
        if total_weight <= 0:
            raise ValueError("the weights of present terms must sum to more than zero")
        result = sum((value * parsed[index] for index, value in present), Decimal(0)) / total_weight
    else:
        raise ValueError(f"unsupported year mode: {rule.mode}")

    return round_mark(result, precision=precision, rounding=rounding)


__all__ = [
    "AggregationMode",
    "Component",
    "MAX_PRECISION",
    "RoundingMode",
    "Score",
    "ScoreStatus",
    "YearMode",
    "YearRule",
    "aggregate",
    "as_decimal",
    "component_value",
    "converted_score",
    "round_mark",
    "score_percent",
    "term_total",
    "year_result",
]
