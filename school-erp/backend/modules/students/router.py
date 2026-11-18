"""HTTP routes for student records, enrollment, guardians and medical data."""

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

from modules.students import documents_service
from modules.students.actions import (
    add_guardian,
    create_enrollment,
    delete_enrollment,
    delete_student,
    duplicate_check,
    get_medical,
    get_student,
    list_enrollments,
    list_guardians,
    preview_number,
    preview_register,
    register_student,
    remove_guardian,
    restore_enrollment,
    restore_guardian,
    restore_student,
    search_students,
    update_enrollment,
    update_guardian,
    update_medical,
    update_student,
)
from modules.students.schemas import (
    DuplicateCheck,
    EnrollmentInput,
    EnrollmentOut,
    EnrollmentUpdate,
    GuardianInput,
    GuardianOut,
    GuardianUpdate,
    MedicalInput,
    MedicalOut,
    StudentList,
    StudentNumberPreviewOut,
    StudentOut,
    StudentQuery,
    StudentRegister,
    StudentRegisterOut,
    StudentStatus,
    StudentUpdate,
)

router = APIRouter(tags=["students"])


def _context(principal: Principal, session: AsyncSession) -> ActionContext:
    return ActionContext(
        principal=principal, session=session, via=principal.via, request_id=request_id_var.get()
    )


def _with_student(payload: dict, student_id: uuid.UUID) -> dict:
    return {**payload, "student_id": str(student_id)}


@router.get("", response_model=StudentList)
async def list_students_route(
    q: str | None = Query(None, max_length=120),
    status: StudentStatus | None = Query(None),
    year_id: uuid.UUID | None = Query(None),
    level_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    cursor: str | None = Query(None, max_length=1000),
    sort: str | None = Query(None, max_length=60),
    order: Literal["asc", "desc"] = Query("desc"),
    principal: Principal = Depends(require("students.view")),
    session: AsyncSession = Depends(get_session),
) -> StudentList:
    query = StudentQuery(
        q=q,
        status=status,
        year_id=year_id,
        level_id=level_id,
        section_id=section_id,
        limit=limit,
        cursor=cursor,
        sort=sort,
        order=order,
    )
    return await search_students(_context(principal, session), query.model_dump())


@router.post("/duplicate-check", dependencies=[Depends(require("students.manage"))])
async def duplicate_check_route(
    payload: DuplicateCheck,
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await duplicate_check(_context(principal, session), payload.model_dump())


@router.post(
    "/register/preview",
    dependencies=[Depends(require("students.manage"))],
)
async def register_preview_route(
    payload: StudentRegister,
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await preview_register(_context(principal, session), payload.model_dump())


@router.post("", response_model=StudentRegisterOut, status_code=201)
async def register_student_route(
    payload: StudentRegister,
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> StudentRegisterOut:
    return await register_student(_context(principal, session), payload.model_dump())


@router.get("/number-preview", response_model=StudentNumberPreviewOut)
async def number_preview_route(
    year_id: uuid.UUID | None = Query(None),
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> StudentNumberPreviewOut:
    payload = {"year_id": str(year_id)} if year_id is not None else {}
    return await preview_number(_context(principal, session), payload)


@router.get("/{student_id}", response_model=StudentOut)
async def get_student_route(
    student_id: uuid.UUID,
    principal: Principal = Depends(require("students.view")),
    session: AsyncSession = Depends(get_session),
) -> StudentOut:
    return await get_student(_context(principal, session), {"student_id": str(student_id)})


@router.patch("/{student_id}", response_model=StudentOut)
async def update_student_route(
    student_id: uuid.UUID,
    payload: StudentUpdate,
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> StudentOut:
    body = _with_student(payload.model_dump(exclude_unset=True), student_id)
    return await update_student(_context(principal, session), body)


@router.delete("/{student_id}", dependencies=[Depends(require("students.manage"))])
async def delete_student_route(
    student_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    body = _with_student({"row_version": expected, "reason": reason}, student_id)
    return await delete_student(_context(principal, session), body)


@router.post("/{student_id}/restore", response_model=StudentOut)
async def restore_student_route(
    student_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> StudentOut:
    return await restore_student(_context(principal, session), _with_student({"reason": reason}, student_id))


# ------------------------------------------------------------------ enrollment


@router.get("/{student_id}/enrollments", response_model=list[EnrollmentOut])
async def list_enrollments_route(
    student_id: uuid.UUID,
    principal: Principal = Depends(require("students.view")),
    session: AsyncSession = Depends(get_session),
) -> list[EnrollmentOut]:
    return await list_enrollments(_context(principal, session), {"student_id": str(student_id)})


@router.post("/{student_id}/enrollments", response_model=EnrollmentOut, status_code=201)
async def create_enrollment_route(
    student_id: uuid.UUID,
    payload: EnrollmentInput,
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> EnrollmentOut:
    return await create_enrollment(
        _context(principal, session), _with_student(payload.model_dump(), student_id)
    )


@router.patch(
    "/{student_id}/enrollments/{enrollment_id}",
    response_model=EnrollmentOut,
)
async def update_enrollment_route(
    student_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    payload: EnrollmentUpdate,
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> EnrollmentOut:
    body = _with_student(payload.model_dump(exclude_unset=True), student_id) | {
        "enrollment_id": str(enrollment_id)
    }
    return await update_enrollment(_context(principal, session), body)


@router.delete(
    "/{student_id}/enrollments/{enrollment_id}",
    dependencies=[Depends(require("students.manage"))],
)
async def delete_enrollment_route(
    student_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    body = _with_student({"row_version": expected, "reason": reason}, student_id) | {
        "enrollment_id": str(enrollment_id)
    }
    return await delete_enrollment(_context(principal, session), body)


@router.post(
    "/{student_id}/enrollments/{enrollment_id}/restore",
    response_model=EnrollmentOut,
)
async def restore_enrollment_route(
    student_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> EnrollmentOut:
    body = _with_student({"reason": reason}, student_id) | {"enrollment_id": str(enrollment_id)}
    return await restore_enrollment(_context(principal, session), body)


# -------------------------------------------------------------------- guardians


@router.get("/{student_id}/guardians", response_model=list[GuardianOut])
async def list_guardians_route(
    student_id: uuid.UUID,
    principal: Principal = Depends(require("students.view")),
    session: AsyncSession = Depends(get_session),
) -> list[GuardianOut]:
    return await list_guardians(_context(principal, session), {"student_id": str(student_id)})


@router.post("/{student_id}/guardians", response_model=GuardianOut, status_code=201)
async def add_guardian_route(
    student_id: uuid.UUID,
    payload: GuardianInput,
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> GuardianOut:
    return await add_guardian(_context(principal, session), _with_student(payload.model_dump(), student_id))


@router.patch(
    "/{student_id}/guardians/{guardian_id}",
    response_model=GuardianOut,
)
async def update_guardian_route(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    payload: GuardianUpdate,
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> GuardianOut:
    body = _with_student(payload.model_dump(exclude_unset=True), student_id) | {
        "guardian_id": str(guardian_id)
    }
    return await update_guardian(_context(principal, session), body)


@router.delete(
    "/{student_id}/guardians/{guardian_id}",
    dependencies=[Depends(require("students.manage"))],
)
async def remove_guardian_route(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    if_match: str | None = Header(None),
    row_version: int | None = Query(None, ge=1),
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    expected = parse_if_match(if_match) if if_match is not None else row_version
    body = _with_student({"row_version": expected, "reason": reason}, student_id) | {
        "guardian_id": str(guardian_id)
    }
    return await remove_guardian(_context(principal, session), body)


@router.post(
    "/{student_id}/guardians/{guardian_id}/restore",
    response_model=GuardianOut,
)
async def restore_guardian_route(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> GuardianOut:
    body = _with_student({"reason": reason}, student_id) | {"guardian_id": str(guardian_id)}
    return await restore_guardian(_context(principal, session), body)


# ---------------------------------------------------------------------- medical


@router.get("/{student_id}/medical", response_model=MedicalOut | None)
async def get_medical_route(
    student_id: uuid.UUID,
    principal: Principal = Depends(require("students.medical.view")),
    session: AsyncSession = Depends(get_session),
) -> MedicalOut | None:
    return await get_medical(_context(principal, session), {"student_id": str(student_id)})


@router.put("/{student_id}/medical", response_model=MedicalOut)
async def update_medical_route(
    student_id: uuid.UUID,
    payload: MedicalInput,
    principal: Principal = Depends(require("students.medical.manage")),
    session: AsyncSession = Depends(get_session),
) -> MedicalOut:
    return await update_medical(_context(principal, session), _with_student(payload.model_dump(), student_id))


# -------------------------------------------------------------------- documents


@router.get("/{student_id}/documents")
async def list_documents_route(
    student_id: uuid.UUID,
    principal: Principal = Depends(require("students.view")),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    items = await documents_service.list_documents(session, storage, settings, student_id)
    return {"items": items}


@router.post("/{student_id}/documents", status_code=201)
async def upload_document_route(
    student_id: uuid.UUID,
    file: UploadFile = File(...),
    principal: Principal = Depends(require("students.manage")),
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
        student_id,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
    )


@router.delete("/{student_id}/documents/{file_id}")
async def delete_document_route(
    student_id: uuid.UUID,
    file_id: str,
    reason: str | None = Query(None, max_length=500),
    principal: Principal = Depends(require("students.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await documents_service.delete_document(session, principal, student_id, file_id, reason=reason)


__all__ = ["router"]
