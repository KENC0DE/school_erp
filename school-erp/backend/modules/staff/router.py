"""HTTP routes for staff profiles, departments, positions, contracts and documents."""

from __future__ import annotations

import uuid
from typing import Literal

from app.logging import request_id_var
from app.settings import Settings
from core.actions.registry import ActionContext
from core.api.concurrency import parse_if_match
from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from core.files.deps import get_app_settings, get_storage
from core.files.storage import Storage
from fastapi import APIRouter, Depends, File, Header, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from modules.staff import documents_service
from modules.staff.actions import (
    create_contract,
    create_department,
    create_position,
    create_qualification,
    create_staff,
    create_teaching_assignment,
    delete_contract,
    delete_qualification,
    delete_staff,
    delete_teaching_assignment,
    get_department,
    get_position,
    get_staff,
    link_account,
    restore_contract,
    restore_qualification,
    restore_staff,
    restore_teaching_assignment,
    search_contracts,
    search_departments,
    search_positions,
    search_qualifications,
    search_staff,
    search_teaching_assignments,
    unlink_account,
    update_contract,
    update_department,
    update_position,
    update_qualification,
    update_staff,
    update_teaching_assignment,
)
from modules.staff.attendance_router import attendance_router
from modules.staff.leave_router import leave_router
from modules.staff.schemas import (
    AccountLink,
    ContractInput,
    ContractList,
    ContractOut,
    ContractUpdate,
    DepartmentInput,
    DepartmentList,
    DepartmentOut,
    DepartmentUpdate,
    PositionInput,
    PositionList,
    PositionOut,
    PositionUpdate,
    QualificationInput,
    QualificationList,
    QualificationOut,
    QualificationUpdate,
    StaffCreate,
    StaffList,
    StaffOut,
    StaffQuery,
    StaffStatus,
    StaffUpdate,
    TeachingAssignmentInput,
    TeachingAssignmentList,
    TeachingAssignmentOut,
    TeachingAssignmentUpdate,
)

router = APIRouter(tags=["staff"])
# Static staff-attendance and leave routes must come before the dynamic
# ``/{staff_id}`` routes.
router.include_router(attendance_router)
router.include_router(leave_router)


def _context(principal: Principal, session: AsyncSession) -> ActionContext:
    return ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )


def _with(payload: dict, **values) -> dict:
    return {**payload, **values}


# ------------------------------------------------------------------ departments


@router.get("/departments", response_model=DepartmentList)
async def list_departments_route(
    include_inactive: bool = Query(False),
    principal: Principal = Depends(require("staff.view")),
    session: AsyncSession = Depends(get_session),
) -> DepartmentList:
    return await search_departments(_context(principal, session), {"include_inactive": include_inactive})


@router.post("/departments", response_model=DepartmentOut, status_code=201)
async def create_department_route(
    payload: DepartmentInput,
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> DepartmentOut:
    return await create_department(_context(principal, session), payload.model_dump())


@router.get("/departments/{department_id}", response_model=DepartmentOut)
async def get_department_route(
    department_id: uuid.UUID,
    principal: Principal = Depends(require("staff.view")),
    session: AsyncSession = Depends(get_session),
) -> DepartmentOut:
    return await get_department(_context(principal, session), {"department_id": str(department_id)})


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
async def update_department_route(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> DepartmentOut:
    return await update_department(
        _context(principal, session),
        _with(payload.model_dump(exclude_unset=True), department_id=department_id),
    )


# -------------------------------------------------------------------- positions


@router.get("/positions", response_model=PositionList)
async def list_positions_route(
    department_id: uuid.UUID | None = Query(None),
    include_inactive: bool = Query(False),
    principal: Principal = Depends(require("staff.view")),
    session: AsyncSession = Depends(get_session),
) -> PositionList:
    return await search_positions(
        _context(principal, session),
        {
            "department_id": str(department_id) if department_id else None,
            "include_inactive": include_inactive,
        },
    )


@router.post("/positions", response_model=PositionOut, status_code=201)
async def create_position_route(
    payload: PositionInput,
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> PositionOut:
    return await create_position(_context(principal, session), payload.model_dump())


@router.get("/positions/{position_id}", response_model=PositionOut)
async def get_position_route(
    position_id: uuid.UUID,
    principal: Principal = Depends(require("staff.view")),
    session: AsyncSession = Depends(get_session),
) -> PositionOut:
    return await get_position(_context(principal, session), {"position_id": str(position_id)})


@router.patch("/positions/{position_id}", response_model=PositionOut)
async def update_position_route(
    position_id: uuid.UUID,
    payload: PositionUpdate,
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> PositionOut:
    return await update_position(
        _context(principal, session),
        _with(payload.model_dump(exclude_unset=True), position_id=position_id),
    )


# -------------------------------------------------------------------- teaching


@router.get("/teaching-assignments", response_model=TeachingAssignmentList)
async def list_teaching_assignments_route(
    staff_id: uuid.UUID | None = Query(None),
    year_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    principal: Principal = Depends(require("staff.view")),
    session: AsyncSession = Depends(get_session),
) -> TeachingAssignmentList:
    payload = {
        "staff_id": str(staff_id) if staff_id else None,
        "year_id": str(year_id) if year_id else None,
        "section_id": str(section_id) if section_id else None,
        "subject_id": str(subject_id) if subject_id else None,
    }
    return await search_teaching_assignments(_context(principal, session), payload)


# ------------------------------------------------------------------------ staff


@router.get("", response_model=StaffList)
async def list_staff_route(
    q: str | None = Query(None, max_length=120),
    status: StaffStatus | None = Query(None),
    department_id: uuid.UUID | None = Query(None),
    position_id: uuid.UUID | None = Query(None),
    linked: bool | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    cursor: str | None = Query(None, max_length=1000),
    sort: str | None = Query(None, max_length=60),
    order: Literal["asc", "desc"] = Query("desc"),
    principal: Principal = Depends(require("staff.view")),
    session: AsyncSession = Depends(get_session),
) -> StaffList:
    query = StaffQuery(
        q=q,
        status=status,
        department_id=department_id,
        position_id=position_id,
        linked=linked,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
    )
    return await search_staff(_context(principal, session), query.model_dump())


@router.post("", response_model=StaffOut, status_code=201)
async def create_staff_route(
    payload: StaffCreate,
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> StaffOut:
    return await create_staff(_context(principal, session), payload.model_dump())


@router.get("/{staff_id}", response_model=StaffOut)
async def get_staff_route(
    staff_id: uuid.UUID,
    principal: Principal = Depends(require("staff.view")),
    session: AsyncSession = Depends(get_session),
) -> StaffOut:
    return await get_staff(_context(principal, session), {"staff_id": str(staff_id)})


@router.patch("/{staff_id}", response_model=StaffOut)
async def update_staff_route(
    staff_id: uuid.UUID,
    payload: StaffUpdate,
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> StaffOut:
    return await update_staff(
        _context(principal, session),
        _with(payload.model_dump(exclude_unset=True), staff_id=staff_id),
    )


@router.delete("/{staff_id}")
async def delete_staff_route(
    staff_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    return await delete_staff(
        _context(principal, session),
        _with({"row_version": expected, "reason": reason}, staff_id=staff_id),
    )


@router.post("/{staff_id}/restore", response_model=StaffOut)
async def restore_staff_route(
    staff_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> StaffOut:
    return await restore_staff(_context(principal, session), _with({"reason": reason}, staff_id=staff_id))


@router.post("/{staff_id}/account", response_model=StaffOut)
async def link_account_route(
    staff_id: uuid.UUID,
    payload: AccountLink,
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> StaffOut:
    return await link_account(_context(principal, session), _with(payload.model_dump(), staff_id=staff_id))


@router.delete("/{staff_id}/account", response_model=StaffOut)
async def unlink_account_route(
    staff_id: uuid.UUID,
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> StaffOut:
    return await unlink_account(_context(principal, session), {"staff_id": str(staff_id)})


# -------------------------------------------------------------------- teaching


@router.get(
    "/{staff_id}/teaching-assignments",
    response_model=TeachingAssignmentList,
)
async def list_staff_teaching_assignments_route(
    staff_id: uuid.UUID,
    year_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    principal: Principal = Depends(require("staff.view")),
    session: AsyncSession = Depends(get_session),
) -> TeachingAssignmentList:
    payload = {
        "staff_id": str(staff_id),
        "year_id": str(year_id) if year_id else None,
        "section_id": str(section_id) if section_id else None,
        "subject_id": str(subject_id) if subject_id else None,
    }
    return await search_teaching_assignments(_context(principal, session), payload)


@router.post(
    "/{staff_id}/teaching-assignments",
    response_model=TeachingAssignmentOut,
    status_code=201,
)
async def create_teaching_assignment_route(
    staff_id: uuid.UUID,
    payload: TeachingAssignmentInput,
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> TeachingAssignmentOut:
    return await create_teaching_assignment(
        _context(principal, session), _with(payload.model_dump(), staff_id=staff_id)
    )


@router.patch(
    "/{staff_id}/teaching-assignments/{assignment_id}",
    response_model=TeachingAssignmentOut,
)
async def update_teaching_assignment_route(
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: TeachingAssignmentUpdate,
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> TeachingAssignmentOut:
    return await update_teaching_assignment(
        _context(principal, session),
        _with(
            payload.model_dump(exclude_unset=True),
            staff_id=staff_id,
            assignment_id=assignment_id,
        ),
    )


@router.delete("/{staff_id}/teaching-assignments/{assignment_id}")
async def delete_teaching_assignment_route(
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await delete_teaching_assignment(
        _context(principal, session),
        _with(
            {"reason": reason},
            staff_id=staff_id,
            assignment_id=assignment_id,
        ),
    )


@router.post(
    "/{staff_id}/teaching-assignments/{assignment_id}/restore",
    response_model=TeachingAssignmentOut,
)
async def restore_teaching_assignment_route(
    staff_id: uuid.UUID,
    assignment_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> TeachingAssignmentOut:
    return await restore_teaching_assignment(
        _context(principal, session),
        _with(
            {"reason": reason},
            staff_id=staff_id,
            assignment_id=assignment_id,
        ),
    )


# -------------------------------------------------------------------- contracts


@router.get("/{staff_id}/contracts", response_model=ContractList)
async def list_contracts_route(
    staff_id: uuid.UUID,
    principal: Principal = Depends(require("staff.contracts.view")),
    session: AsyncSession = Depends(get_session),
) -> ContractList:
    return await search_contracts(_context(principal, session), {"staff_id": str(staff_id)})


@router.post("/{staff_id}/contracts", response_model=ContractOut, status_code=201)
async def create_contract_route(
    staff_id: uuid.UUID,
    payload: ContractInput,
    principal: Principal = Depends(require("staff.contracts.manage")),
    session: AsyncSession = Depends(get_session),
) -> ContractOut:
    return await create_contract(_context(principal, session), _with(payload.model_dump(), staff_id=staff_id))


@router.patch("/{staff_id}/contracts/{contract_id}", response_model=ContractOut)
async def update_contract_route(
    staff_id: uuid.UUID,
    contract_id: uuid.UUID,
    payload: ContractUpdate,
    principal: Principal = Depends(require("staff.contracts.manage")),
    session: AsyncSession = Depends(get_session),
) -> ContractOut:
    return await update_contract(
        _context(principal, session),
        _with(
            payload.model_dump(exclude_unset=True),
            staff_id=staff_id,
            contract_id=contract_id,
        ),
    )


@router.delete("/{staff_id}/contracts/{contract_id}")
async def delete_contract_route(
    staff_id: uuid.UUID,
    contract_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("staff.contracts.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await delete_contract(
        _context(principal, session),
        _with(
            {"reason": reason},
            staff_id=staff_id,
            contract_id=contract_id,
        ),
    )


@router.post("/{staff_id}/contracts/{contract_id}/restore", response_model=ContractOut)
async def restore_contract_route(
    staff_id: uuid.UUID,
    contract_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("staff.contracts.manage")),
    session: AsyncSession = Depends(get_session),
) -> ContractOut:
    return await restore_contract(
        _context(principal, session),
        _with(
            {"reason": reason},
            staff_id=staff_id,
            contract_id=contract_id,
        ),
    )


# ---------------------------------------------------------------- qualifications


@router.get("/{staff_id}/qualifications", response_model=QualificationList)
async def list_qualifications_route(
    staff_id: uuid.UUID,
    principal: Principal = Depends(require("staff.view")),
    session: AsyncSession = Depends(get_session),
) -> QualificationList:
    return await search_qualifications(_context(principal, session), {"staff_id": str(staff_id)})


@router.post("/{staff_id}/qualifications", response_model=QualificationOut, status_code=201)
async def create_qualification_route(
    staff_id: uuid.UUID,
    payload: QualificationInput,
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> QualificationOut:
    return await create_qualification(
        _context(principal, session), _with(payload.model_dump(), staff_id=staff_id)
    )


@router.patch("/{staff_id}/qualifications/{qualification_id}", response_model=QualificationOut)
async def update_qualification_route(
    staff_id: uuid.UUID,
    qualification_id: uuid.UUID,
    payload: QualificationUpdate,
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> QualificationOut:
    return await update_qualification(
        _context(principal, session),
        _with(
            payload.model_dump(exclude_unset=True),
            staff_id=staff_id,
            qualification_id=qualification_id,
        ),
    )


@router.delete("/{staff_id}/qualifications/{qualification_id}")
async def delete_qualification_route(
    staff_id: uuid.UUID,
    qualification_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await delete_qualification(
        _context(principal, session),
        _with(
            {"reason": reason},
            staff_id=staff_id,
            qualification_id=qualification_id,
        ),
    )


@router.post(
    "/{staff_id}/qualifications/{qualification_id}/restore",
    response_model=QualificationOut,
)
async def restore_qualification_route(
    staff_id: uuid.UUID,
    qualification_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> QualificationOut:
    return await restore_qualification(
        _context(principal, session),
        _with(
            {"reason": reason},
            staff_id=staff_id,
            qualification_id=qualification_id,
        ),
    )


# -------------------------------------------------------------------- documents


@router.get("/{staff_id}/documents")
async def list_documents_route(
    staff_id: uuid.UUID,
    principal: Principal = Depends(require("staff.view")),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    items = await documents_service.list_documents(session, storage, settings, staff_id)
    return {"items": items}


@router.post("/{staff_id}/documents", status_code=201)
async def upload_document_route(
    staff_id: uuid.UUID,
    file: UploadFile = File(...),
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    data = await file.read(settings.storage_max_upload_bytes + 1)
    return await documents_service.upload_document(
        session,
        principal,
        storage,
        settings,
        staff_id,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
    )


@router.delete("/{staff_id}/documents/{file_id}")
async def delete_document_route(
    staff_id: uuid.UUID,
    file_id: str,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("staff.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await documents_service.delete_document(session, principal, staff_id, file_id, reason=reason)
