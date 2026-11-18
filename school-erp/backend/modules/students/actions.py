"""Action-registry entry points for student records.

Routers and the AI layer share these functions so permissions, validation and
audit entries are identical. Payloads are JSON objects; the router maps path
parameters into the same keys.
"""

from __future__ import annotations

import uuid

from core.actions.registry import ActionContext, action

from modules.students import (
    enrollment_service,
    guardian_service,
    medical_service,
    numbering,
    progression_service,
    service,
)
from modules.students.progression_schemas import (
    PromotionApplyOut,
    PromotionPreview,
    PromotionRequest,
    StudentStatusChange,
    StudentStatusChangeOut,
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
    StudentNumberPreview,
    StudentNumberPreviewOut,
    StudentOut,
    StudentQuery,
    StudentRegister,
    StudentRegisterOut,
    StudentUpdate,
)


def _student_id(payload: dict) -> uuid.UUID:
    return uuid.UUID(str(payload["student_id"]))


def _body(payload: dict, *path_keys: str) -> dict:
    """Drop router path parameters before validating an action payload."""
    return {key: value for key, value in payload.items() if key not in path_keys}


async def _commit(ctx: ActionContext) -> None:
    await ctx.session.commit()


@action(
    key="students.search",
    module="students",
    permission="students.view",
    risk="read",
    describe="Search and filter student records",
    input=StudentQuery,
    output=StudentList,
)
async def search_students(ctx: ActionContext, payload: dict | None = None) -> StudentList:
    query = StudentQuery.model_validate(payload or {})
    return await service.list_students(ctx.session, ctx.principal, query)


@action(
    key="students.get",
    module="students",
    permission="students.view",
    risk="read",
    describe="Read one student record with enrollments and guardians",
    output=StudentOut,
)
async def get_student(ctx: ActionContext, payload: dict) -> StudentOut:
    return await service.get_student(
        ctx.session,
        ctx.principal,
        _student_id(payload),
        include_medical=ctx.principal.can("students.medical.view"),
    )


async def preview_register(ctx: ActionContext, payload: dict) -> dict:
    data = StudentRegister.model_validate(_body(payload, "student_id"))
    return await service.preview_registration(ctx.session, data)


@action(
    key="students.register",
    module="students",
    permission="students.manage",
    risk="write",
    describe="Register a student with person names, enrollment, guardians and medical data",
    input=StudentRegister,
    output=StudentRegisterOut,
    preview=preview_register,
)
async def register_student(ctx: ActionContext, payload: dict) -> StudentRegisterOut:
    data = StudentRegister.model_validate(_body(payload, "student_id"))
    profile, warnings = await service.register_student(ctx.session, ctx.principal, data, via=ctx.via)
    detail = await service.student_detail(
        ctx.session,
        ctx.principal,
        profile,
        include_medical=ctx.principal.can("students.medical.view"),
    )
    return StudentRegisterOut(**detail.model_dump(), duplicate_warnings=warnings)


@action(
    key="students.duplicate_check",
    module="students",
    permission="students.manage",
    risk="read",
    describe="Check a person's names and date of birth for likely duplicate students",
)
async def duplicate_check(ctx: ActionContext, payload: dict) -> dict:
    data = DuplicateCheck.model_validate(_body(payload, "student_id"))
    warnings = await service.duplicate_warnings(ctx.session, data)
    return {"duplicate_warnings": warnings}


@action(
    key="students.numbers.preview",
    module="students",
    permission="students.manage",
    risk="read",
    describe="Preview the next generated student number without reserving it",
    input=StudentNumberPreview,
    output=StudentNumberPreviewOut,
)
async def preview_number(ctx: ActionContext, payload: dict | None = None) -> StudentNumberPreviewOut:
    data = StudentNumberPreview.model_validate(payload or {})
    allocation = await numbering.peek_number(ctx.session, year_id=data.year_id)
    return StudentNumberPreviewOut(
        student_number=allocation.student_number,
        scope=allocation.scope,
        year=allocation.year,
        sequence=allocation.sequence,
    )


@action(
    key="students.update",
    module="students",
    permission="students.manage",
    risk="write",
    describe="Edit a student's person details, status and custom fields",
    input=StudentUpdate,
    output=StudentOut,
)
async def update_student(ctx: ActionContext, payload: dict) -> StudentOut:
    data = StudentUpdate.model_validate(_body(payload, "student_id"))
    return await service.update_student(ctx.session, ctx.principal, _student_id(payload), data, via=ctx.via)


@action(
    key="students.delete",
    module="students",
    permission="students.manage",
    risk="destructive",
    describe="Soft-delete a student record (restorable, audited)",
)
async def delete_student(ctx: ActionContext, payload: dict) -> dict:
    return await service.delete_student(
        ctx.session,
        ctx.principal,
        _student_id(payload),
        row_version=payload.get("row_version"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="students.restore",
    module="students",
    permission="students.manage",
    risk="write",
    describe="Restore a soft-deleted student record",
    output=StudentOut,
)
async def restore_student(ctx: ActionContext, payload: dict) -> StudentOut:
    return await service.restore_student(
        ctx.session,
        ctx.principal,
        _student_id(payload),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="students.enrollments.list",
    module="students",
    permission="students.view",
    risk="read",
    describe="List a student's enrollments",
    output=list[EnrollmentOut],
)
async def list_enrollments(ctx: ActionContext, payload: dict) -> list[EnrollmentOut]:
    rows = await enrollment_service.list_enrollments(ctx.session, _student_id(payload))
    return [await enrollment_service.enrollment_view(ctx.session, row) for row in rows]


@action(
    key="students.enrollments.create",
    module="students",
    permission="students.manage",
    risk="write",
    describe="Enroll a student in an academic year, level and section",
    input=EnrollmentInput,
    output=EnrollmentOut,
)
async def create_enrollment(ctx: ActionContext, payload: dict) -> EnrollmentOut:
    data = EnrollmentInput.model_validate(_body(payload, "student_id", "enrollment_id"))
    row = await enrollment_service.create_enrollment(
        ctx.session, ctx.principal, _student_id(payload), data, via=ctx.via
    )
    await _commit(ctx)
    return await enrollment_service.enrollment_view(ctx.session, row)


@action(
    key="students.enrollments.update",
    module="students",
    permission="students.manage",
    risk="write",
    describe="Edit an enrollment using optimistic concurrency",
    input=EnrollmentUpdate,
    output=EnrollmentOut,
)
async def update_enrollment(ctx: ActionContext, payload: dict) -> EnrollmentOut:
    data = EnrollmentUpdate.model_validate(_body(payload, "student_id", "enrollment_id"))
    row = await enrollment_service.update_enrollment(
        ctx.session,
        ctx.principal,
        _student_id(payload),
        uuid.UUID(str(payload["enrollment_id"])),
        data,
        via=ctx.via,
    )
    await _commit(ctx)
    return await enrollment_service.enrollment_view(ctx.session, row)


@action(
    key="students.enrollments.delete",
    module="students",
    permission="students.manage",
    risk="destructive",
    describe="Soft-delete an enrollment (restorable, audited)",
)
async def delete_enrollment(ctx: ActionContext, payload: dict) -> dict:
    row = await enrollment_service.delete_enrollment(
        ctx.session,
        ctx.principal,
        _student_id(payload),
        uuid.UUID(str(payload["enrollment_id"])),
        row_version=payload.get("row_version"),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return {"id": str(row.id), "deleted": True}


@action(
    key="students.enrollments.restore",
    module="students",
    permission="students.manage",
    risk="write",
    describe="Restore a soft-deleted enrollment",
    output=EnrollmentOut,
)
async def restore_enrollment(ctx: ActionContext, payload: dict) -> EnrollmentOut:
    row = await enrollment_service.restore_enrollment(
        ctx.session,
        ctx.principal,
        _student_id(payload),
        uuid.UUID(str(payload["enrollment_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return await enrollment_service.enrollment_view(ctx.session, row)


@action(
    key="students.guardians.list",
    module="students",
    permission="students.view",
    risk="read",
    describe="List a student's guardians",
    output=list[GuardianOut],
)
async def list_guardians(ctx: ActionContext, payload: dict) -> list[GuardianOut]:
    rows = await guardian_service.list_guardians(ctx.session, _student_id(payload))
    return [
        await guardian_service.guardian_view(ctx.session, row, locale=ctx.principal.locale)
        for row, _person in rows
    ]


@action(
    key="students.guardians.add",
    module="students",
    permission="students.manage",
    risk="write",
    describe="Link an existing person or create a new guardian",
    input=GuardianInput,
    output=GuardianOut,
)
async def add_guardian(ctx: ActionContext, payload: dict) -> GuardianOut:
    data = GuardianInput.model_validate(_body(payload, "student_id", "guardian_id"))
    row = await guardian_service.add_guardian(
        ctx.session, ctx.principal, _student_id(payload), data, via=ctx.via
    )
    await _commit(ctx)
    return await guardian_service.guardian_view(ctx.session, row, locale=ctx.principal.locale)


@action(
    key="students.guardians.update",
    module="students",
    permission="students.manage",
    risk="write",
    describe="Edit a guardian link using optimistic concurrency",
    input=GuardianUpdate,
    output=GuardianOut,
)
async def update_guardian(ctx: ActionContext, payload: dict) -> GuardianOut:
    data = GuardianUpdate.model_validate(_body(payload, "student_id", "guardian_id"))
    row = await guardian_service.update_guardian(
        ctx.session,
        ctx.principal,
        _student_id(payload),
        uuid.UUID(str(payload["guardian_id"])),
        data,
        via=ctx.via,
    )
    await _commit(ctx)
    return await guardian_service.guardian_view(ctx.session, row, locale=ctx.principal.locale)


@action(
    key="students.guardians.remove",
    module="students",
    permission="students.manage",
    risk="destructive",
    describe="Remove a guardian link (restorable, audited)",
)
async def remove_guardian(ctx: ActionContext, payload: dict) -> dict:
    row = await guardian_service.remove_guardian(
        ctx.session,
        ctx.principal,
        _student_id(payload),
        uuid.UUID(str(payload["guardian_id"])),
        row_version=payload.get("row_version"),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return {"id": str(row.id), "deleted": True}


@action(
    key="students.guardians.restore",
    module="students",
    permission="students.manage",
    risk="write",
    describe="Restore a removed guardian link",
    output=GuardianOut,
)
async def restore_guardian(ctx: ActionContext, payload: dict) -> GuardianOut:
    row = await guardian_service.restore_guardian(
        ctx.session,
        ctx.principal,
        _student_id(payload),
        uuid.UUID(str(payload["guardian_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return await guardian_service.guardian_view(ctx.session, row, locale=ctx.principal.locale)


async def preview_promotion(ctx: ActionContext, payload: dict) -> PromotionPreview:
    data = PromotionRequest.model_validate(_body(payload, "student_id"))
    return await progression_service.preview_promotion(ctx.session, data)


@action(
    key="students.promotions.preview",
    module="students",
    permission="students.manage",
    risk="read",
    describe="Preview a bulk promotion, its target sections and warnings",
    input=PromotionRequest,
    output=PromotionPreview,
)
async def preview_promotion_action(ctx: ActionContext, payload: dict) -> PromotionPreview:
    return await preview_promotion(ctx, payload)


@action(
    key="students.promotions.apply",
    module="students",
    permission="students.manage",
    risk="bulk",
    describe="Promote, repeat or graduate a whole section or level in one audited batch",
    input=PromotionRequest,
    output=PromotionApplyOut,
    preview=preview_promotion,
)
async def apply_promotion(ctx: ActionContext, payload: dict) -> PromotionApplyOut:
    data = PromotionRequest.model_validate(_body(payload, "student_id"))
    result = await progression_service.apply_promotion(ctx.session, ctx.principal, data, via=ctx.via)
    await _commit(ctx)
    return result


@action(
    key="students.status.change",
    module="students",
    permission="students.manage",
    risk="write",
    describe="Transfer out, withdraw, graduate, convert to alumni or reinstate a student",
    input=StudentStatusChange,
    output=StudentStatusChangeOut,
)
async def change_student_status(ctx: ActionContext, payload: dict) -> StudentStatusChangeOut:
    data = StudentStatusChange.model_validate(_body(payload, "student_id"))
    result = await progression_service.change_status(
        ctx.session, ctx.principal, _student_id(payload), data, via=ctx.via
    )
    await _commit(ctx)
    return result


@action(
    key="students.medical.get",
    module="students",
    permission="students.medical.view",
    risk="read",
    describe="Read a student's sensitive medical record",
    output=MedicalOut,
)
async def get_medical(ctx: ActionContext, payload: dict) -> MedicalOut | None:
    return await medical_service.get_medical(ctx.session, _student_id(payload))


@action(
    key="students.medical.update",
    module="students",
    permission="students.medical.manage",
    risk="write",
    describe="Create or replace a student's medical record",
    input=MedicalInput,
    output=MedicalOut,
)
async def update_medical(ctx: ActionContext, payload: dict) -> MedicalOut:
    data = MedicalInput.model_validate(_body(payload, "student_id"))
    row = await medical_service.upsert_medical(
        ctx.session, ctx.principal, _student_id(payload), data, via=ctx.via
    )
    await _commit(ctx)
    return medical_service.medical_out(row)


__all__ = [
    "add_guardian",
    "apply_promotion",
    "change_student_status",
    "create_enrollment",
    "delete_enrollment",
    "delete_student",
    "duplicate_check",
    "get_medical",
    "get_student",
    "list_enrollments",
    "list_guardians",
    "preview_number",
    "preview_promotion_action",
    "preview_register",
    "register_student",
    "remove_guardian",
    "restore_enrollment",
    "restore_guardian",
    "restore_student",
    "search_students",
    "update_enrollment",
    "update_guardian",
    "update_medical",
    "update_student",
]
