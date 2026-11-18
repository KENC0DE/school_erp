"""Response builders for staff records."""

from __future__ import annotations

from core.people.models import Person
from core.people.service import person_view

from modules.staff.models import (
    StaffContract,
    StaffDepartment,
    StaffPosition,
    StaffProfile,
    StaffQualification,
)
from modules.staff.schemas import (
    ContractOut,
    DepartmentOut,
    PersonOut,
    PositionOut,
    QualificationOut,
    StaffOut,
    StaffSummary,
)


def person_out(person: Person, locale: str = "en") -> PersonOut:
    return PersonOut(**person_view(person, locale))


def department_out(row: StaffDepartment) -> DepartmentOut:
    return DepartmentOut(
        id=str(row.id),
        code=row.code,
        name=row.name,
        name_am=row.name_am,
        parent_id=str(row.parent_id) if row.parent_id else None,
        description=row.description,
        is_active=row.is_active,
        sort_order=row.sort_order,
        row_version=row.row_version,
    )


def position_out(row: StaffPosition, department: StaffDepartment | None = None) -> PositionOut:
    return PositionOut(
        id=str(row.id),
        code=row.code,
        name=row.name,
        name_am=row.name_am,
        department_id=str(row.department_id) if row.department_id else None,
        department_code=department.code if department else None,
        department_name=department.name if department else None,
        is_teaching=row.is_teaching,
        description=row.description,
        is_active=row.is_active,
        sort_order=row.sort_order,
        row_version=row.row_version,
    )


def contract_out(row: StaffContract) -> ContractOut:
    return ContractOut(
        id=str(row.id),
        staff_id=str(row.staff_id),
        type=row.type,
        status=row.status,
        start_date=row.start_date,
        end_date=row.end_date,
        salary_santim=row.salary_santim,
        notes=row.notes,
        row_version=row.row_version,
    )


def qualification_out(row: StaffQualification) -> QualificationOut:
    return QualificationOut(
        id=str(row.id),
        staff_id=str(row.staff_id),
        kind=row.kind,
        title=row.title,
        institution=row.institution,
        field_of_study=row.field_of_study,
        start_date=row.start_date,
        end_date=row.end_date,
        result=row.result,
        notes=row.notes,
        row_version=row.row_version,
    )


def staff_summary(
    row: StaffProfile,
    person: Person,
    *,
    locale: str,
    department: StaffDepartment | None,
    position: StaffPosition | None,
) -> StaffSummary:
    return StaffSummary(
        id=str(row.id),
        staff_number=row.staff_number,
        status=row.status,
        person=person_out(person, locale),
        user_id=str(row.user_id) if row.user_id else None,
        department=department_out(department) if department else None,
        position=position_out(position, department) if position else None,
        hire_date=row.hire_date,
        end_date=row.end_date,
        row_version=row.row_version,
    )


def staff_out(
    row: StaffProfile,
    person: Person,
    *,
    locale: str,
    department: StaffDepartment | None,
    position: StaffPosition | None,
    contracts: list[StaffContract],
    qualifications: list[StaffQualification],
    contracts_restricted: bool = False,
) -> StaffOut:
    return StaffOut(
        **staff_summary(
            row,
            person,
            locale=locale,
            department=department,
            position=position,
        ).model_dump(),
        notes=row.notes,
        custom=row.custom or {},
        contracts=[contract_out(item) for item in contracts],
        contracts_restricted=contracts_restricted,
        qualifications=[qualification_out(item) for item in qualifications],
    )


__all__ = [
    "contract_out",
    "department_out",
    "person_out",
    "position_out",
    "qualification_out",
    "staff_out",
    "staff_summary",
]
