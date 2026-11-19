"""Response builders for payroll records."""

from __future__ import annotations

from modules.payroll.models import (
    PayrollComponent,
    PayrollPayslip,
    PayrollPayslipLine,
    PayrollRule,
    PayrollRuleBracket,
    PayrollRuleSet,
    PayrollRun,
    PayrollStaffComponent,
)
from modules.payroll.schemas import (
    BracketOut,
    ComponentOut,
    PayslipLineOut,
    PayslipOut,
    RuleOut,
    RuleSetOut,
    RunOut,
    StaffComponentOut,
)

ACCOUNTANT_NOTICE_KEY = "payroll.rules.accountant_notice"


def component_out(row: PayrollComponent) -> ComponentOut:
    return ComponentOut(
        id=str(row.id),
        code=row.code,
        name=row.name,
        name_am=row.name_am,
        kind=row.kind,
        is_taxable=row.is_taxable,
        is_pensionable=row.is_pensionable,
        is_active=row.is_active,
        sort_order=row.sort_order,
        notes=row.notes,
        row_version=row.row_version,
    )


def staff_component_out(
    row: PayrollStaffComponent,
    component: PayrollComponent,
) -> StaffComponentOut:
    return StaffComponentOut(
        id=str(row.id),
        staff_id=str(row.staff_id),
        component_id=str(row.component_id),
        component_code=component.code,
        component_name=component.name,
        kind=component.kind,
        amount_santim=row.amount_santim,
        rate_basis_points=row.rate_basis_points,
        starts_on=row.starts_on,
        ends_on=row.ends_on,
        notes=row.notes,
        row_version=row.row_version,
    )


def rule_out(row: PayrollRule, brackets: list[PayrollRuleBracket]) -> RuleOut:
    return RuleOut(
        id=str(row.id),
        rule_set_id=str(row.rule_set_id),
        key=row.key,
        name=row.name,
        kind=row.kind,
        payer=row.payer,
        method=row.method,
        base=row.base,
        rate_basis_points=row.rate_basis_points,
        brackets=[
            BracketOut(
                lower_santim=bracket.lower_santim,
                upper_santim=bracket.upper_santim,
                rate_basis_points=bracket.rate_basis_points,
            )
            for bracket in brackets
        ],
        is_active=row.is_active,
        sort_order=row.sort_order,
        notes=row.notes,
        row_version=row.row_version,
    )


def rule_set_out(
    row: PayrollRuleSet,
    rules: list[tuple[PayrollRule, list[PayrollRuleBracket]]],
) -> RuleSetOut:
    return RuleSetOut(
        id=str(row.id),
        code=row.code,
        name=row.name,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        status=row.status,
        verified_by_accountant=row.verified_by_accountant,
        accountant_notice=ACCOUNTANT_NOTICE_KEY,
        notes=row.notes,
        rules=[rule_out(rule, brackets) for rule, brackets in rules],
        row_version=row.row_version,
    )


def run_out(row: PayrollRun, rule_set_code: str) -> RunOut:
    return RunOut(
        id=str(row.id),
        period_year=row.period_year,
        period_month=row.period_month,
        rule_set_id=str(row.rule_set_id),
        rule_set_code=rule_set_code,
        status=row.status,
        payslip_count=row.payslip_count,
        skipped_count=row.skipped_count,
        gross_santim=row.gross_santim,
        deductions_santim=row.deductions_santim,
        net_santim=row.net_santim,
        employer_santim=row.employer_santim,
        calculated_at=row.calculated_at,
        finalized_at=row.finalized_at,
        notes=row.notes,
        row_version=row.row_version,
    )


def payslip_line_out(row: PayrollPayslipLine) -> PayslipLineOut:
    return PayslipLineOut(
        id=str(row.id),
        kind=row.kind,
        code=row.code,
        name=row.name,
        source=row.source,
        rule_key=row.rule_key,
        amount_santim=row.amount_santim,
        base_santim=row.base_santim,
        rate_basis_points=row.rate_basis_points,
        sort_order=row.sort_order,
    )


def payslip_out(row: PayrollPayslip, lines: list[PayrollPayslipLine]) -> PayslipOut:
    return PayslipOut(
        id=str(row.id),
        run_id=str(row.run_id),
        staff_id=str(row.staff_id),
        staff_number=row.staff_number,
        staff_name=row.staff_name,
        contract_id=str(row.contract_id) if row.contract_id else None,
        base_salary_santim=row.base_salary_santim,
        gross_santim=row.gross_santim,
        taxable_santim=row.taxable_santim,
        pensionable_santim=row.pensionable_santim,
        total_deductions_santim=row.total_deductions_santim,
        net_santim=row.net_santim,
        employer_contributions_santim=row.employer_contributions_santim,
        notes=row.notes,
        lines=[payslip_line_out(line) for line in lines],
        row_version=row.row_version,
    )


__all__ = [
    "ACCOUNTANT_NOTICE_KEY",
    "component_out",
    "payslip_out",
    "rule_out",
    "rule_set_out",
    "run_out",
    "staff_component_out",
]
