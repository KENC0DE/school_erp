"""Pure payroll calculation rules (P3-05).

Nothing here touches the database or a framework: the payroll service loads
configurable components and rule sets, then hands plain values to these
functions. Every amount is an integer number of santim and every rate is an
integer number of basis points (1% = 100 bp), so no float can introduce a
rounding error into pay.

Tax and pension rates are **never** hard-coded here. A rule set stores the
rates a school's accountant configured, and the shipped starter rules are
marked "to be validated by an accountant".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

RATE_SCALE = 10_000
MAX_RATE_BASIS_POINTS = RATE_SCALE


class PayrollError(ValueError):
    """A payroll input or rule set would produce an invalid payslip."""


class RuleKind(StrEnum):
    INCOME_TAX = "income_tax"
    PENSION = "pension"
    OTHER = "other"


class Payer(StrEnum):
    EMPLOYEE = "employee"
    EMPLOYER = "employer"


class RuleMethod(StrEnum):
    PERCENT = "percent"
    BRACKETS = "brackets"


class Basis(StrEnum):
    BASIC = "basic"
    GROSS = "gross"
    TAXABLE = "taxable"
    PENSIONABLE = "pensionable"


class Rounding(StrEnum):
    HALF_UP = "half_up"
    HALF_EVEN = "half_even"
    DOWN = "down"
    UP = "up"
    FLOOR = "floor"
    CEILING = "ceiling"


@dataclass(frozen=True)
class Bracket:
    """One slice of a progressive rule.

    ``upper_santim`` is exclusive. A missing upper bound means the rule keeps
    applying upwards; ending the chain at a finite bound is how a contribution
    cap is expressed.
    """

    lower_santim: int
    upper_santim: int | None
    rate_basis_points: int


@dataclass(frozen=True)
class Rule:
    key: str
    name: str
    kind: RuleKind
    payer: Payer
    method: RuleMethod
    base: Basis
    rate_basis_points: int | None = None
    brackets: tuple[Bracket, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ComponentAmount:
    """A configured earning or deduction assigned to one staff member.

    Exactly one of ``amount_santim`` (fixed ETB amount) and
    ``rate_basis_points`` (a percentage of basic salary) must be set.
    """

    code: str
    name: str
    amount_santim: int | None = None
    rate_basis_points: int | None = None
    is_taxable: bool = True
    is_pensionable: bool = True


@dataclass(frozen=True)
class PayslipInput:
    """Everything the engine needs for one staff member in one period."""

    base_salary_santim: int
    earnings: tuple[ComponentAmount, ...] = ()
    deductions: tuple[ComponentAmount, ...] = ()
    rules: tuple[Rule, ...] = ()
    rounding: Rounding = Rounding.HALF_UP


@dataclass(frozen=True)
class PayslipLine:
    code: str
    name: str
    kind: str  # earning | deduction | employer_contribution
    amount_santim: int
    source: str  # component | rule | basic
    rule_key: str | None = None
    base_santim: int | None = None
    rate_basis_points: int | None = None


@dataclass(frozen=True)
class Payslip:
    gross_santim: int
    taxable_santim: int
    pensionable_santim: int
    total_earnings_santim: int
    total_deductions_santim: int
    net_santim: int
    employer_contributions_santim: int
    lines: tuple[PayslipLine, ...]


# --------------------------------------------------------------- arithmetic


def _check_santim(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PayrollError(f"{label} must be integer santim")
    if value < 0:
        raise PayrollError(f"{label} cannot be negative")
    return value


def _check_rate(rate_basis_points: int) -> int:
    if isinstance(rate_basis_points, bool) or not isinstance(rate_basis_points, int):
        raise PayrollError("A rate must be integer basis points")
    if not 0 <= rate_basis_points <= MAX_RATE_BASIS_POINTS:
        raise PayrollError("A rate must be between 0 and 10000 basis points")
    return rate_basis_points


def _divide(numerator: int, denominator: int, rounding: Rounding) -> int:
    """Round a non-negative integer fraction without ever using a float."""
    if numerator < 0 or denominator <= 0:
        raise PayrollError("Only non-negative amounts can be rounded")
    quotient, remainder = divmod(numerator, denominator)
    if remainder == 0:
        return quotient
    twice = remainder * 2
    if rounding is Rounding.DOWN:
        return quotient
    if rounding is Rounding.UP:
        return quotient + 1
    if rounding is Rounding.FLOOR:
        return quotient
    if rounding is Rounding.CEILING:
        return quotient + 1
    if rounding is Rounding.HALF_UP:
        return quotient + 1 if twice >= denominator else quotient
    if rounding is Rounding.HALF_EVEN:
        if twice > denominator:
            return quotient + 1
        if twice < denominator:
            return quotient
        return quotient + 1 if quotient % 2 else quotient
    raise PayrollError(f"Unknown rounding mode {rounding!r}")


def percent_amount(
    base_santim: int,
    rate_basis_points: int,
    rounding: Rounding = Rounding.HALF_UP,
) -> int:
    """Apply a basis-point rate to an amount of santim."""
    base = _check_santim(base_santim, "Base")
    rate = _check_rate(rate_basis_points)
    return _divide(base * rate, RATE_SCALE, rounding)


# ---------------------------------------------------------------- validation


def validate_brackets(brackets: tuple[Bracket, ...] | list[Bracket]) -> None:
    """A progressive rule must start at zero and have no gaps or overlaps.

    The last bracket may be open-ended, or may stop early to express a cap.
    """
    if not brackets:
        raise PayrollError("A progressive rule needs at least one bracket")
    ordered = sorted(brackets, key=lambda bracket: bracket.lower_santim)
    expected_lower = 0
    for bracket in ordered:
        _check_santim(bracket.lower_santim, "Bracket lower bound")
        _check_rate(bracket.rate_basis_points)
        if bracket.lower_santim != expected_lower:
            raise PayrollError(
                "Brackets must be contiguous and start at zero "
                f"(expected {expected_lower}, got {bracket.lower_santim})"
            )
        if bracket.upper_santim is not None:
            _check_santim(bracket.upper_santim, "Bracket upper bound")
            if bracket.upper_santim <= bracket.lower_santim:
                raise PayrollError("A bracket's upper bound must exceed its lower bound")
            expected_lower = bracket.upper_santim
            continue
        # An open-ended bracket must be last.
        if bracket is not ordered[-1]:
            raise PayrollError("An open-ended bracket must be the last bracket")
        expected_lower = -1
    if expected_lower == -1:
        return


def validate_rule(rule: Rule) -> None:
    if not rule.key.strip():
        raise PayrollError("A rule needs a key")
    if not rule.name.strip():
        raise PayrollError("A rule needs a name")
    if rule.method is RuleMethod.PERCENT:
        if rule.rate_basis_points is None:
            raise PayrollError("A percent rule needs a rate")
        _check_rate(rule.rate_basis_points)
        if rule.brackets:
            raise PayrollError("A percent rule cannot also carry brackets")
        return
    if rule.method is RuleMethod.BRACKETS:
        if rule.rate_basis_points is not None:
            raise PayrollError("A bracket rule carries its rates on the brackets")
        validate_brackets(rule.brackets)
        return
    raise PayrollError(f"Unknown rule method {rule.method!r}")


def bracket_amount(
    base_santim: int,
    brackets: tuple[Bracket, ...] | list[Bracket],
    rounding: Rounding = Rounding.HALF_UP,
) -> int:
    """Sum each bracket slice, rounding every slice before adding it.

    Rounding per slice keeps the stored payslip recomputable line by line.
    """
    base = _check_santim(base_santim, "Base")
    validate_brackets(brackets)
    total = 0
    for bracket in sorted(brackets, key=lambda item: item.lower_santim):
        upper = base if bracket.upper_santim is None else min(base, bracket.upper_santim)
        slice_santim = upper - bracket.lower_santim
        if slice_santim <= 0:
            continue
        total += percent_amount(slice_santim, bracket.rate_basis_points, rounding)
    return total


def rule_amount(rule: Rule, base_santim: int, rounding: Rounding = Rounding.HALF_UP) -> int:
    validate_rule(rule)
    if rule.method is RuleMethod.PERCENT:
        assert rule.rate_basis_points is not None  # validated above
        return percent_amount(base_santim, rule.rate_basis_points, rounding)
    return bracket_amount(base_santim, rule.brackets, rounding)


# ------------------------------------------------------------------ payslip


def _component_amount(
    component: ComponentAmount,
    basic_santim: int,
    rounding: Rounding,
) -> int:
    fixed = component.amount_santim is not None
    rate = component.rate_basis_points is not None
    if fixed == rate:
        raise PayrollError(f"Component {component.code!r} needs exactly one of a fixed amount or a rate")
    if fixed:
        return _check_santim(component.amount_santim, f"Component {component.code} amount")
    return percent_amount(basic_santim, component.rate_basis_points, rounding)


def compute_payslip(data: PayslipInput) -> Payslip:
    """Build a payslip from basic salary, components and configurable rules.

    The basic salary is taxable and pensionable. Earning components add to
    gross pay and to the taxable/pensionable bases when their flags say so.
    Employee rules and deduction components reduce net pay; employer rules are
    recorded but never added to gross or subtracted from net.
    """
    basic = _check_santim(data.base_salary_santim, "Basic salary")
    lines: list[PayslipLine] = [
        PayslipLine(
            code="basic",
            name="Basic salary",
            kind="earning",
            amount_santim=basic,
            source="basic",
            base_santim=basic,
        )
    ]
    gross = basic
    taxable = basic
    pensionable = basic

    for earning in data.earnings:
        amount = _component_amount(earning, basic, data.rounding)
        if amount == 0:
            continue
        gross += amount
        if earning.is_taxable:
            taxable += amount
        if earning.is_pensionable:
            pensionable += amount
        lines.append(
            PayslipLine(
                code=earning.code,
                name=earning.name,
                kind="earning",
                amount_santim=amount,
                source="component",
                base_santim=basic,
                rate_basis_points=earning.rate_basis_points,
            )
        )

    bases = {
        Basis.BASIC: basic,
        Basis.GROSS: gross,
        Basis.TAXABLE: taxable,
        Basis.PENSIONABLE: pensionable,
    }

    employee_rules = 0
    employer_rules = 0
    for rule in data.rules:
        validate_rule(rule)
        base_santim = bases[rule.base]
        amount = rule_amount(rule, base_santim, data.rounding)
        if amount == 0:
            continue
        if rule.payer is Payer.EMPLOYEE:
            employee_rules += amount
            kind = "deduction"
        else:
            employer_rules += amount
            kind = "employer_contribution"
        lines.append(
            PayslipLine(
                code=rule.key,
                name=rule.name,
                kind=kind,
                amount_santim=amount,
                source="rule",
                rule_key=rule.key,
                base_santim=base_santim,
                rate_basis_points=rule.rate_basis_points,
            )
        )

    component_deductions = 0
    for deduction in data.deductions:
        amount = _component_amount(deduction, basic, data.rounding)
        if amount == 0:
            continue
        component_deductions += amount
        lines.append(
            PayslipLine(
                code=deduction.code,
                name=deduction.name,
                kind="deduction",
                amount_santim=amount,
                source="component",
                base_santim=basic,
                rate_basis_points=deduction.rate_basis_points,
            )
        )

    total_deductions = employee_rules + component_deductions
    net = gross - total_deductions
    if net < 0:
        raise PayrollError("Deductions exceed gross pay for this staff member; check the rule set")
    return Payslip(
        gross_santim=gross,
        taxable_santim=taxable,
        pensionable_santim=pensionable,
        total_earnings_santim=gross,
        total_deductions_santim=total_deductions,
        net_santim=net,
        employer_contributions_santim=employer_rules,
        lines=tuple(lines),
    )


__all__ = [
    "Basis",
    "Bracket",
    "ComponentAmount",
    "MAX_RATE_BASIS_POINTS",
    "Payer",
    "PayrollError",
    "Payslip",
    "PayslipInput",
    "PayslipLine",
    "RATE_SCALE",
    "Rounding",
    "Rule",
    "RuleKind",
    "RuleMethod",
    "bracket_amount",
    "compute_payslip",
    "percent_amount",
    "rule_amount",
    "validate_brackets",
    "validate_rule",
]
