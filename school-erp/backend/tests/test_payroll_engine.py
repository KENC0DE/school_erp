"""P3-05: pure payroll arithmetic, brackets and payslip assembly.

Every rate here is a test fixture, not a shipped rate: the product ships no
starter tax or pension numbers because only an accountant can supply them.
"""

from __future__ import annotations

import pytest
from modules.payroll.engine import (
    Basis,
    Bracket,
    ComponentAmount,
    Payer,
    PayrollError,
    PayslipInput,
    Rounding,
    Rule,
    RuleKind,
    RuleMethod,
    bracket_amount,
    compute_payslip,
    percent_amount,
    rule_amount,
    validate_brackets,
    validate_rule,
)


def _percent_rule(
    key: str = "tax",
    *,
    rate: int = 1500,
    base: Basis = Basis.TAXABLE,
    payer: Payer = Payer.EMPLOYEE,
) -> Rule:
    return Rule(
        key=key,
        name=key.title(),
        kind=RuleKind.INCOME_TAX,
        payer=payer,
        method=RuleMethod.PERCENT,
        base=base,
        rate_basis_points=rate,
    )


# ----------------------------------------------------------------- arithmetic


def test_percent_amount_is_integer_santim_with_selectable_rounding() -> None:
    assert percent_amount(100_00, 1500) == 15_00
    assert percent_amount(1, 5000) == 1  # half up
    assert percent_amount(1, 5000, Rounding.HALF_EVEN) == 0
    assert percent_amount(1, 5000, Rounding.DOWN) == 0
    assert percent_amount(1, 5000, Rounding.UP) == 1
    assert percent_amount(1, 5000, Rounding.FLOOR) == 0
    assert percent_amount(1, 5000, Rounding.CEILING) == 1
    # Half-even only rounds an exact half towards the even quotient.
    assert percent_amount(3, 5000, Rounding.HALF_EVEN) == 2
    assert percent_amount(5, 5000, Rounding.HALF_EVEN) == 2


def test_percent_amount_rejects_negative_or_non_integer_input() -> None:
    with pytest.raises(PayrollError):
        percent_amount(-1, 1000)
    with pytest.raises(PayrollError):
        percent_amount(100, 1000.0)  # type: ignore[arg-type]
    with pytest.raises(PayrollError):
        percent_amount(100, 10_001)


# ------------------------------------------------------------------- brackets


BRACKETS = [
    Bracket(lower_santim=0, upper_santim=1000_00, rate_basis_points=1000),
    Bracket(lower_santim=1000_00, upper_santim=2000_00, rate_basis_points=2000),
    Bracket(lower_santim=2000_00, upper_santim=None, rate_basis_points=3000),
]


def test_brackets_tax_each_slice_and_round_per_slice() -> None:
    assert bracket_amount(2500_00, BRACKETS) == 100_00 + 200_00 + 150_00
    # Ending the chain early expresses a contribution cap.
    capped = [
        Bracket(lower_santim=0, upper_santim=1000_00, rate_basis_points=1000),
        Bracket(lower_santim=1000_00, upper_santim=2000_00, rate_basis_points=2000),
    ]
    assert bracket_amount(2500_00, capped) == 100_00 + 200_00
    # Per-slice rounding: 1 santim at 50% in two slices is 1 + 1, not 1.
    halves = [
        Bracket(lower_santim=0, upper_santim=1, rate_basis_points=5000),
        Bracket(lower_santim=1, upper_santim=2, rate_basis_points=5000),
    ]
    assert bracket_amount(2, halves) == 2


def test_validate_brackets_requires_a_contiguous_chain_from_zero() -> None:
    validate_brackets(BRACKETS)
    validate_brackets([Bracket(0, None, 100)])

    with pytest.raises(PayrollError):
        validate_brackets([])
    with pytest.raises(PayrollError):
        validate_brackets([Bracket(1, None, 100)])
    with pytest.raises(PayrollError):
        validate_brackets([Bracket(0, 100, 100), Bracket(200, None, 100)])
    with pytest.raises(PayrollError):
        validate_brackets([Bracket(0, 100, 100), Bracket(50, None, 100)])
    with pytest.raises(PayrollError):
        validate_brackets([Bracket(0, 0, 100)])
    with pytest.raises(PayrollError):
        validate_brackets([Bracket(0, 100, 100), Bracket(100, None, 100), Bracket(200, None, 100)])
    with pytest.raises(PayrollError):
        validate_brackets([Bracket(0, 100, 10_001)])


def test_rules_are_validated_by_method() -> None:
    validate_rule(_percent_rule())
    validate_rule(
        Rule(
            key="pension",
            name="Pension",
            kind=RuleKind.PENSION,
            payer=Payer.EMPLOYEE,
            method=RuleMethod.BRACKETS,
            base=Basis.BASIC,
            brackets=tuple(BRACKETS),
        )
    )

    with pytest.raises(PayrollError):
        validate_rule(_percent_rule(rate=None))  # type: ignore[arg-type]
    with pytest.raises(PayrollError):
        validate_rule(
            Rule(
                key="tax",
                name="Tax",
                kind=RuleKind.INCOME_TAX,
                payer=Payer.EMPLOYEE,
                method=RuleMethod.PERCENT,
                base=Basis.TAXABLE,
                rate_basis_points=1000,
                brackets=tuple(BRACKETS),
            )
        )
    with pytest.raises(PayrollError):
        validate_rule(
            Rule(
                key="tax",
                name="Tax",
                kind=RuleKind.INCOME_TAX,
                payer=Payer.EMPLOYEE,
                method=RuleMethod.BRACKETS,
                base=Basis.TAXABLE,
                rate_basis_points=1000,
                brackets=tuple(BRACKETS),
            )
        )


def test_rule_amount_dispatches_percent_and_bracket_methods() -> None:
    assert rule_amount(_percent_rule(rate=1000), 500_00) == 50_00
    bracketed = Rule(
        key="tax",
        name="Tax",
        kind=RuleKind.INCOME_TAX,
        payer=Payer.EMPLOYEE,
        method=RuleMethod.BRACKETS,
        base=Basis.TAXABLE,
        brackets=tuple(BRACKETS),
    )
    assert rule_amount(bracketed, 2500_00) == 450_00


# ------------------------------------------------------------------- payslips


def test_compute_payslip_keeps_employer_contributions_out_of_net() -> None:
    payslip = compute_payslip(
        PayslipInput(
            base_salary_santim=10_000_00,
            earnings=(
                ComponentAmount(
                    code="housing",
                    name="Housing allowance",
                    rate_basis_points=1000,  # 10% of basic
                ),
                ComponentAmount(
                    code="transport",
                    name="Transport",
                    amount_santim=500_00,
                    is_taxable=False,
                    is_pensionable=False,
                ),
            ),
            deductions=(ComponentAmount(code="loan", name="Staff loan", amount_santim=100_00),),
            rules=(
                _percent_rule(rate=1500, base=Basis.TAXABLE),
                _percent_rule("pension", rate=700, base=Basis.PENSIONABLE),
                _percent_rule(
                    "employer_pension",
                    rate=1100,
                    base=Basis.PENSIONABLE,
                    payer=Payer.EMPLOYER,
                ),
            ),
        )
    )

    assert payslip.gross_santim == 10_000_00 + 1_000_00 + 500_00
    assert payslip.taxable_santim == 10_000_00 + 1_000_00
    assert payslip.pensionable_santim == 10_000_00 + 1_000_00
    assert payslip.total_earnings_santim == payslip.gross_santim
    # 15% of 11,000 + 7% of 11,000 + a fixed 100.
    assert payslip.total_deductions_santim == 1650_00 + 770_00 + 100_00
    assert payslip.net_santim == payslip.gross_santim - payslip.total_deductions_santim
    assert payslip.employer_contributions_santim == 1210_00

    kinds = {line.code: line.kind for line in payslip.lines}
    assert kinds["basic"] == "earning"
    assert kinds["housing"] == "earning"
    assert kinds["tax"] == "deduction"
    assert kinds["pension"] == "deduction"
    assert kinds["employer_pension"] == "employer_contribution"
    assert kinds["loan"] == "deduction"
    basic = payslip.lines[0]
    assert basic.amount_santim == 10_000_00
    assert basic.source == "basic"


def test_payslip_rejects_deductions_above_gross_and_bad_components() -> None:
    with pytest.raises(PayrollError):
        compute_payslip(
            PayslipInput(
                base_salary_santim=100_00,
                deductions=(ComponentAmount(code="loan", name="Loan", amount_santim=200_00),),
                rules=(_percent_rule(rate=1000),),
            )
        )

    both = ComponentAmount(code="bad", name="Bad", amount_santim=1, rate_basis_points=1)
    with pytest.raises(PayrollError):
        compute_payslip(PayslipInput(base_salary_santim=100_00, earnings=(both,)))
    neither = ComponentAmount(code="bad", name="Bad")
    with pytest.raises(PayrollError):
        compute_payslip(PayslipInput(base_salary_santim=100_00, deductions=(neither,)))
    negative = ComponentAmount(code="bad", name="Bad", amount_santim=-1)
    with pytest.raises(PayrollError):
        compute_payslip(PayslipInput(base_salary_santim=100_00, earnings=(negative,)))


def test_zero_rules_and_zero_components_add_no_lines() -> None:
    payslip = compute_payslip(
        PayslipInput(
            base_salary_santim=100_00,
            earnings=(ComponentAmount(code="zero", name="Zero", amount_santim=0),),
            deductions=(ComponentAmount(code="nil", name="Nil", amount_santim=0),),
            rules=(_percent_rule(rate=0),),
        )
    )
    assert [line.code for line in payslip.lines] == ["basic"]
    assert payslip.net_santim == 100_00
