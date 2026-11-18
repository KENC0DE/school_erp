"""Rollback handlers for enrollments and progression (P1-11, P2-11).

An enrollment can be reverted (including undoing its creation). A progression
entry restores the student's status and exit fields and removes the enrollment
that the promotion created, so a mistaken bulk promotion can be undone from the
activity history without editing the audit trail.
"""

from __future__ import annotations

import uuid

from app.errors import NotFound
from core.audit.revert import RevertContext, Reverter, register_reverter
from core.db.soft_delete import get_including_deleted, mark_deleted, mark_restored

from modules.students.models import StudentEnrollment, StudentProfile
from modules.students.progression_service import revert_progression


async def _enrollment(ctx: RevertContext) -> StudentEnrollment:
    try:
        row = await get_including_deleted(ctx.session, StudentEnrollment, uuid.UUID(ctx.entity_id))
    except ValueError as exc:
        raise NotFound("The enrollment does not exist") from exc
    if row is None:
        raise NotFound("The enrollment does not exist")
    return row


def _enrollment_state(row: StudentEnrollment) -> dict:
    return {
        "student_id": str(row.student_id),
        "year_id": str(row.year_id),
        "level_id": str(row.level_id),
        "section_id": str(row.section_id) if row.section_id else None,
        "roll_number": row.roll_number,
        "status": row.status,
        "notes": row.notes,
        "row_version": row.row_version,
        "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
    }


async def apply_enrollment_revert(ctx: RevertContext) -> dict:
    row = await _enrollment(ctx)
    if ctx.before is None:
        # The entry created the enrollment: reverting it removes the row.
        mark_deleted(row, actor=ctx.principal)
    else:
        if ctx.before.get("deleted_at"):
            mark_restored(row, actor=ctx.principal)
        else:
            row.year_id = uuid.UUID(ctx.before["year_id"])
            row.level_id = uuid.UUID(ctx.before["level_id"])
            section = ctx.before.get("section_id")
            row.section_id = uuid.UUID(section) if section else None
            row.roll_number = ctx.before.get("roll_number")
            row.status = ctx.before.get("status", row.status)
            row.notes = ctx.before.get("notes")
            row.row_version = (row.row_version or 0) + 1
    await ctx.session.flush()
    return _enrollment_state(row)


async def restore_enrollment_revert(ctx: RevertContext) -> dict:
    row = await _enrollment(ctx)
    mark_restored(row, actor=ctx.principal)
    await ctx.session.flush()
    return _enrollment_state(row)


async def _profile(ctx: RevertContext) -> StudentProfile:
    try:
        profile = await get_including_deleted(ctx.session, StudentProfile, uuid.UUID(ctx.entity_id))
    except ValueError as exc:
        raise NotFound("The student does not exist") from exc
    if profile is None:
        raise NotFound("The student does not exist")
    return profile


async def apply_progression_revert(ctx: RevertContext) -> dict:
    profile = await _profile(ctx)
    before = ctx.before or {}
    created_enrollment = None
    if ctx.after and ctx.after.get("enrollment_id"):
        created_enrollment = ctx.after.get("enrollment_id")
    if before.get("enrollment_id") == created_enrollment:
        created_enrollment = None
    return await revert_progression(
        ctx.session,
        profile,
        status=before.get("status"),
        exit_date=before.get("exit_date"),
        exit_reason=before.get("exit_reason"),
        enrollment_id=created_enrollment,
    )


register_reverter(
    Reverter(
        entity_type="student_enrollment",
        module="students",
        permission="students.manage",
        apply=apply_enrollment_revert,
        restore=restore_enrollment_revert,
    )
)

register_reverter(
    Reverter(
        entity_type="student_progression",
        module="students",
        permission="students.manage",
        apply=apply_progression_revert,
    )
)

__all__ = [
    "apply_enrollment_revert",
    "apply_progression_revert",
    "restore_enrollment_revert",
]
