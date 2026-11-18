"""Bulk promotion and status changes (ARCH §9.2).

The planner is pure with respect to the database: it reads the source
enrollments, resolves the next in-scope level and the matching section, and
returns every decision with its warnings. ``apply_promotion`` runs the same
planner and then writes through the students services, so a preview can never
diverge from the applied result.

Phase 4 plugs result rules into this module through the ``rule_resolver`` hook:
the default resolver promotes every student to the next level and graduates the
last level; a rule resolver can return ``repeat`` for a student instead.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.errors import Conflict, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import mark_deleted
from core.people.models import Person, full_name
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics import section_service
from modules.academics import service as catalog
from modules.academics import years as year_service
from modules.academics.schemas import LevelOut
from modules.academics.section_schemas import SectionOut
from modules.students import enrollment_service
from modules.students.common import live_student, student_state
from modules.students.models import StudentEnrollment, StudentProfile
from modules.students.progression_schemas import (
    PromotionApplyOut,
    PromotionPreview,
    PromotionRequest,
    PromotionRow,
    StudentStatusChange,
    StudentStatusChangeOut,
)
from modules.students.schemas import EnrollmentInput

MODULE = "students"

RuleResolver = Callable[["_Candidate"], Awaitable[str] | str]

STATUS_FOR_ACTION = {
    "transfer_out": "transferred_out",
    "withdraw": "withdrawn",
    "graduate": "graduated",
    "alumni": "alumni",
    "reinstate": "active",
}
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "transfer_out": {"active", "promoted", "repeating"},
    "withdraw": {"active", "promoted", "repeating"},
    "graduate": {"active", "promoted", "repeating"},
    "alumni": {"graduated"},
    "reinstate": {"transferred_out", "withdrawn"},
}
REASON_REQUIRED = {"transfer_out", "withdraw"}
PROMOTABLE_STATUSES = {"active", "promoted", "repeating"}


def progression_state(
    profile: StudentProfile,
    *,
    enrollment_id: str | None = None,
    year_id: str | None = None,
    level_id: str | None = None,
    section_id: str | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "status": profile.status,
        "exit_date": profile.exit_date.isoformat() if profile.exit_date else None,
        "exit_reason": profile.exit_reason,
        "row_version": profile.row_version,
    }
    if enrollment_id is not None:
        state["enrollment_id"] = enrollment_id
    if year_id is not None:
        state["year_id"] = year_id
    if level_id is not None:
        state["level_id"] = level_id
    if section_id is not None:
        state["section_id"] = section_id
    return state


@dataclass
class _Candidate:
    profile: StudentProfile
    person: Person
    enrollment: StudentEnrollment
    level: LevelOut
    next_level: LevelOut | None
    action: str
    target_level: LevelOut | None = None
    target_section: SectionOut | None = None
    source_section: SectionOut | None = None
    target_year_id: uuid.UUID | None = None
    warnings: list[str] = field(default_factory=list)
    blocking: bool = False


def _warning(code: str) -> str:
    return f"students.progress.warning.{code}"


def _block(candidate: _Candidate, code: str) -> None:
    candidate.blocking = True
    if _warning(code) not in candidate.warnings:
        candidate.warnings.append(_warning(code))


def _resolve_section(
    candidate: _Candidate,
    exception: Any,
    sections_by_level: dict[uuid.UUID, list[SectionOut]],
    all_sections: dict[uuid.UUID, SectionOut],
) -> None:
    if candidate.action in {"skip", "graduate"}:
        candidate.target_section = None
        return
    if candidate.target_level is None:
        return
    if exception is not None and getattr(exception, "target_section_id", None) is not None:
        section = all_sections.get(exception.target_section_id)
        if (
            section is None
            or uuid.UUID(section.level_id) != uuid.UUID(candidate.target_level.id)
            or uuid.UUID(section.year_id) != candidate.target_year_id
        ):
            _block(candidate, "target_section_invalid")
            return
        candidate.target_section = section
        return
    if candidate.source_section is None:
        _block(candidate, "section_missing")
        return
    labels = sections_by_level.get(uuid.UUID(candidate.target_level.id), [])
    # The source section code is the only stable hint; sections have no id
    # continuity across years.
    match = next((section for section in labels if section.code == candidate.source_section.code), None)
    if match is None:
        candidate.warnings.append(_warning("section_unmapped"))
        return
    candidate.target_section = match


async def _plan(
    session: AsyncSession,
    data: PromotionRequest,
    *,
    rule_resolver: RuleResolver | None = None,
) -> list[_Candidate]:
    source_year = await year_service.get_year(session, data.source_year_id)
    target_year = await year_service.get_year(session, data.target_year_id)
    if source_year.id == target_year.id:
        raise ValidationFailed(
            "The target year must differ from the source year",
            message_key="students.progress.error.same_year",
        )
    if target_year.start_date <= source_year.start_date:
        raise ValidationFailed(
            "The target year must start after the source year",
            message_key="students.progress.error.target_year_order",
        )
    if target_year.status == "closed":
        raise Conflict(
            "A closed academic year cannot receive promoted students",
            message_key="students.progress.error.target_year_closed",
            details={"target_year_id": target_year.id},
        )

    level_list = await catalog.list_levels(session)
    ordered = sorted(level_list.items, key=lambda item: (item.sort_order, item.name))
    level_by_id = {item.id: item for item in ordered}
    level_index = {item.id: index for index, item in enumerate(ordered)}

    stmt = (
        select(StudentProfile, Person, StudentEnrollment)
        .join(Person, Person.id == StudentProfile.person_id)
        .join(StudentEnrollment, StudentEnrollment.student_id == StudentProfile.id)
        .where(
            StudentEnrollment.year_id == data.source_year_id,
            StudentEnrollment.deleted_at.is_(None),
            StudentProfile.deleted_at.is_(None),
            Person.deleted_at.is_(None),
            StudentProfile.status.in_(PROMOTABLE_STATUSES),
        )
        .order_by(StudentProfile.student_number)
    )
    if data.source_level_id is not None:
        stmt = stmt.where(StudentEnrollment.level_id == data.source_level_id)
    if data.source_section_id is not None:
        stmt = stmt.where(StudentEnrollment.section_id == data.source_section_id)
    if data.student_ids:
        stmt = stmt.where(StudentProfile.id.in_(data.student_ids))
    rows = (await session.execute(stmt)).all()

    if data.student_ids:
        found = {row[0].id for row in rows}
        missing = [str(item) for item in data.student_ids if item not in found]
        if missing:
            raise ValidationFailed(
                "Some selected students are not enrolled in that year and scope",
                message_key="students.progress.error.students_not_found",
                details={"student_ids": missing},
            )

    exceptions: dict[uuid.UUID, Any] = {}
    for exception in data.exceptions:
        if exception.student_id in exceptions:
            raise ValidationFailed(
                "A student can only have one manual exception",
                message_key="students.progress.error.duplicate_exception",
                details={"student_id": str(exception.student_id)},
            )
        exceptions[exception.student_id] = exception
    known = {row[0].id for row in rows}
    unknown = [str(item) for item in exceptions if item not in known]
    if unknown:
        raise ValidationFailed(
            "A manual exception points at a student outside the selected scope",
            message_key="students.progress.error.exception_not_found",
            details={"student_ids": unknown},
        )

    target_sections = await section_service.list_sections(session, year_id=data.target_year_id)
    sections_by_level: dict[uuid.UUID, list[SectionOut]] = defaultdict(list)
    all_sections: dict[uuid.UUID, SectionOut] = {}
    for section in target_sections.items:
        sections_by_level[uuid.UUID(section.level_id)].append(section)
        all_sections[uuid.UUID(section.id)] = section

    target_enrollments = {
        row.student_id
        for row in (
            await session.execute(
                select(StudentEnrollment).where(
                    StudentEnrollment.year_id == data.target_year_id,
                    StudentEnrollment.deleted_at.is_(None),
                    StudentEnrollment.student_id.in_([row[0].id for row in rows] or [uuid.uuid4()]),
                )
            )
        ).scalars()
    }

    source_sections = await section_service.list_sections(session, year_id=data.source_year_id)
    source_section_map = {uuid.UUID(section.id): section for section in source_sections.items}

    candidates: list[_Candidate] = []
    for profile, person, enrollment in rows:
        level = level_by_id.get(str(enrollment.level_id))
        if level is None:
            # A level moved out of scope after the student enrolled. Skipping
            # is safer than guessing a target; the office can move the student
            # manually or widen the scope.
            candidate = _Candidate(
                profile=profile,
                person=person,
                enrollment=enrollment,
                level=LevelOut(
                    id=str(enrollment.level_id),
                    code="",
                    name="",
                    scope_level=0,
                    sort_order=0,
                    is_active=False,
                    is_starter=False,
                    is_verified=False,
                    in_scope=False,
                    row_version=0,
                ),
                next_level=None,
                action="skip",
            )
            _block(candidate, "level_out_of_scope")
            candidates.append(candidate)
            continue

        index = level_index.get(level.id, -1)
        next_level = ordered[index + 1] if 0 <= index < len(ordered) - 1 else None
        candidate = _Candidate(
            profile=profile,
            person=person,
            enrollment=enrollment,
            level=level,
            next_level=next_level,
            action="promote" if next_level is not None else "graduate",
            source_section=(source_section_map.get(enrollment.section_id) if enrollment.section_id else None),
            target_year_id=data.target_year_id,
        )
        exception = exceptions.get(profile.id)
        if rule_resolver is not None and exception is None:
            resolved = rule_resolver(candidate)
            if hasattr(resolved, "__await__"):
                resolved = await resolved  # type: ignore[assignment]
            candidate.action = str(resolved)
        elif exception is not None:
            candidate.action = exception.action

        if profile.id in target_enrollments:
            candidate.action = "skip"
            candidate.target_level = None
            candidate.target_section = None
            candidate.warnings.append(_warning("already_enrolled"))
            candidates.append(candidate)
            continue

        # Manual target level, when supplied, must be in scope and ahead of the
        # current level. The default target is the next level in the catalog.
        explicit_level = getattr(exception, "target_level_id", None) if exception else None
        if candidate.action == "promote":
            if explicit_level is None:
                candidate.target_level = next_level
            else:
                candidate.target_level = level_by_id.get(str(explicit_level))
                if candidate.target_level is None:
                    _block(candidate, "target_level_invalid")
                elif candidate.target_level.id == level.id:
                    _block(candidate, "target_level_not_after")
            if candidate.target_level is None and not candidate.blocking:
                _block(candidate, "no_next_level")
        elif candidate.action == "repeat":
            candidate.target_level = level
        elif candidate.action == "graduate":
            if next_level is not None:
                _block(candidate, "graduate_not_final")
        elif candidate.action == "skip":
            candidate.target_level = None
        else:
            raise ValidationFailed(
                "Unknown promotion action",
                message_key="students.progress.error.action_invalid",
                details={"action": candidate.action},
            )

        _resolve_section(candidate, exception, sections_by_level, all_sections)
        candidates.append(candidate)

    await _mark_capacity_warnings(session, candidates, data.target_year_id)
    return candidates


async def _mark_capacity_warnings(
    session: AsyncSession,
    candidates: list[_Candidate],
    target_year_id: uuid.UUID,
) -> None:
    counts: dict[uuid.UUID, int] = defaultdict(int)
    for level_id in {candidate.target_level.id for candidate in candidates if candidate.target_level}:
        occupancy = await enrollment_service.section_occupancy(
            session, year_id=target_year_id, level_id=uuid.UUID(level_id)
        )
        counts.update({section_id: count for section_id, count in occupancy.items()})
    for candidate in candidates:
        if candidate.target_section is None or candidate.action not in {"promote", "repeat"}:
            continue
        section_id = uuid.UUID(candidate.target_section.id)
        counts[section_id] += 1
        if counts[section_id] > candidate.target_section.capacity:
            warning = _warning("section_full")
            if warning not in candidate.warnings:
                candidate.warnings.append(warning)


async def preview_promotion(
    session: AsyncSession,
    data: PromotionRequest,
    *,
    rule_resolver: RuleResolver | None = None,
) -> PromotionPreview:
    candidates = await _plan(session, data, rule_resolver=rule_resolver)
    rows = [_row(candidate) for candidate in candidates]
    counts = {
        action: sum(1 for row in rows if row.action == action)
        for action in ("promote", "repeat", "graduate", "skip")
    }
    return PromotionPreview(
        source_year_id=str(data.source_year_id),
        target_year_id=str(data.target_year_id),
        total=len(rows),
        promote=counts["promote"],
        repeat=counts["repeat"],
        graduate=counts["graduate"],
        skip=counts["skip"],
        blocking=sum(1 for row in rows if row.blocking),
        items=rows,
    )


def _row(candidate: _Candidate) -> PromotionRow:
    source_section = getattr(candidate, "source_section", None)
    return PromotionRow(
        student_id=str(candidate.profile.id),
        student_number=candidate.profile.student_number,
        full_name=full_name(candidate.person, locale="en"),
        status=candidate.profile.status,
        current_level_id=candidate.level.id,
        current_level_name=candidate.level.name,
        current_level_sort_order=candidate.level.sort_order,
        current_section_id=str(candidate.enrollment.section_id) if candidate.enrollment.section_id else None,
        current_section_code=source_section.code if source_section is not None else None,
        action=candidate.action,  # type: ignore[arg-type]
        next_level_id=candidate.next_level.id if candidate.next_level is not None else None,
        next_level_name=candidate.next_level.name if candidate.next_level is not None else None,
        target_level_id=candidate.target_level.id if candidate.target_level is not None else None,
        target_level_name=candidate.target_level.name if candidate.target_level is not None else None,
        target_section_id=candidate.target_section.id if candidate.target_section is not None else None,
        target_section_code=candidate.target_section.code if candidate.target_section is not None else None,
        warnings=candidate.warnings,
        blocking=candidate.blocking,
    )


async def apply_promotion(
    session: AsyncSession,
    principal: Principal,
    data: PromotionRequest,
    *,
    via: str = "api",
    rule_resolver: RuleResolver | None = None,
) -> PromotionApplyOut:
    candidates = await _plan(session, data, rule_resolver=rule_resolver)
    blocking = [candidate for candidate in candidates if candidate.blocking]
    if blocking:
        raise ValidationFailed(
            "Some students cannot be promoted until the warnings are resolved",
            message_key="students.progress.error.blocking",
            details={
                "student_ids": [str(candidate.profile.id) for candidate in blocking],
            },
        )

    effective = data.effective_date or date.today()
    counts = {"promote": 0, "repeat": 0, "graduate": 0, "skip": 0}
    applied: list[PromotionRow] = []
    for candidate in candidates:
        if candidate.action == "skip":
            counts["skip"] += 1
            applied.append(_row(candidate))
            continue
        before = progression_state(candidate.profile)
        if candidate.action in {"promote", "repeat"}:
            assert candidate.target_level is not None
            enrollment = await enrollment_service.create_enrollment(
                session,
                principal,
                candidate.profile.id,
                EnrollmentInput(
                    year_id=data.target_year_id,
                    level_id=uuid.UUID(candidate.target_level.id),
                    section_id=(
                        uuid.UUID(candidate.target_section.id)
                        if candidate.target_section is not None
                        else None
                    ),
                    roll_number=candidate.enrollment.roll_number,
                    status="active",
                ),
                via=via,
            )
            candidate.profile.status = "promoted" if candidate.action == "promote" else "repeating"
            candidate.profile.exit_date = None
            candidate.profile.exit_reason = None
            action = f"students.progress.{candidate.action}"
            after = progression_state(
                candidate.profile,
                enrollment_id=str(enrollment.id),
                year_id=str(enrollment.year_id),
                level_id=str(enrollment.level_id),
                section_id=str(enrollment.section_id) if enrollment.section_id else None,
            )
        else:
            candidate.profile.status = "graduated"
            candidate.profile.exit_date = effective
            candidate.profile.exit_reason = data.reason
            action = "students.progress.graduate"
            after = progression_state(candidate.profile)
        candidate.profile.row_version = (candidate.profile.row_version or 0) + 1
        await session.flush()
        await record(
            session,
            action=action,
            module=MODULE,
            entity_type="student_progression",
            entity_id=str(candidate.profile.id),
            before=before,
            after=after,
            actor=principal,
            reason=data.reason,
            via=via,
        )
        counts[candidate.action] += 1
        applied.append(_row(candidate))

    batch_id = str(uuid.uuid4())
    await record(
        session,
        action="students.progress.apply",
        module=MODULE,
        entity_type="promotion_batch",
        entity_id=batch_id,
        after={
            "source_year_id": str(data.source_year_id),
            "target_year_id": str(data.target_year_id),
            "promote": counts["promote"],
            "repeat": counts["repeat"],
            "graduate": counts["graduate"],
            "skip": counts["skip"],
        },
        actor=principal,
        reason=data.reason,
        via=via,
    )
    await session.flush()
    return PromotionApplyOut(
        source_year_id=str(data.source_year_id),
        target_year_id=str(data.target_year_id),
        enrolled=counts["promote"] + counts["repeat"],
        promoted=counts["promote"],
        repeated=counts["repeat"],
        graduated=counts["graduate"],
        skipped=counts["skip"],
        items=applied,
    )


async def change_status(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    data: StudentStatusChange,
    *,
    via: str = "api",
) -> StudentStatusChangeOut:
    profile = await live_student(session, student_id)
    if data.row_version is not None:
        ensure_row_version(profile, data.row_version, current_state=student_state(profile))
    allowed = ALLOWED_TRANSITIONS[data.action]
    if profile.status not in allowed:
        raise Conflict(
            "That status change is not allowed from the student's current status",
            message_key="students.progress.error.transition",
            details={
                "action": data.action,
                "status": profile.status,
                "allowed_from": sorted(allowed),
            },
        )
    reason = (data.exit_reason or "").strip() or None
    if data.action in REASON_REQUIRED and reason is None:
        raise ValidationFailed(
            "A reason is required for this status change",
            message_key="students.progress.error.reason_required",
            details={"action": data.action},
        )
    if data.action == "graduate":
        await _assert_final_level(session, profile)

    before = progression_state(profile)
    profile.status = STATUS_FOR_ACTION[data.action]
    if data.action == "reinstate":
        profile.exit_date = None
        profile.exit_reason = None
    else:
        profile.exit_date = data.exit_date or date.today()
        profile.exit_reason = reason
    profile.row_version = (profile.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action=f"students.progress.{data.action}",
        module=MODULE,
        entity_type="student_progression",
        entity_id=str(profile.id),
        before=before,
        after=progression_state(profile),
        actor=principal,
        reason=reason,
        via=via,
    )
    from modules.students import service

    detail = await service.get_student(
        session,
        principal,
        profile.id,
        include_medical=principal.can("students.medical.view"),
    )
    return StudentStatusChangeOut(
        action=data.action,
        changed=True,
        student=detail.model_dump(mode="json"),
    )


async def _assert_final_level(session: AsyncSession, profile: StudentProfile) -> None:
    rows = await enrollment_service.list_enrollments(session, profile.id)
    if not rows:
        raise ValidationFailed(
            "The student has no enrollment to graduate from",
            message_key="students.progress.error.no_enrollment",
        )
    years = await year_service.list_years(session)
    starts = {item.id: item.start_date for item in years.items}
    latest = max(rows, key=lambda row: starts.get(str(row.year_id), date.min))
    levels = await catalog.list_levels(session)
    ordered = sorted(levels.items, key=lambda item: (item.sort_order, item.name))
    if not ordered:
        raise ValidationFailed(
            "The school has no grade levels",
            message_key="students.progress.error.no_levels",
        )
    current = next((level for level in ordered if level.id == str(latest.level_id)), None)
    if current is None or current.id != ordered[-1].id:
        raise ValidationFailed(
            "Only a student in the final grade level can graduate",
            message_key="students.progress.error.not_final_level",
            details={"level_id": str(latest.level_id)},
        )


async def revert_progression(
    session: AsyncSession,
    profile: StudentProfile,
    *,
    status: str | None,
    exit_date: str | None,
    exit_reason: str | None,
    enrollment_id: str | None,
) -> dict[str, Any]:
    """Apply an earlier progression state; used by the audit rollback handler."""
    profile.status = status or profile.status
    profile.exit_date = date.fromisoformat(exit_date) if exit_date else None
    profile.exit_reason = exit_reason
    profile.row_version = (profile.row_version or 0) + 1
    if enrollment_id:
        enrollment = await session.get(StudentEnrollment, uuid.UUID(enrollment_id))
        if enrollment is not None and enrollment.deleted_at is None:
            mark_deleted(enrollment)
    await session.flush()
    return progression_state(profile)


async def load_progression_profile(session: AsyncSession, entity_id: str) -> StudentProfile | None:
    try:
        return (
            await session.execute(select(StudentProfile).where(StudentProfile.id == uuid.UUID(entity_id)))
        ).scalar_one_or_none()
    except ValueError:
        return None


__all__ = [
    "ALLOWED_TRANSITIONS",
    "PromotionRequest",
    "apply_promotion",
    "change_status",
    "load_progression_profile",
    "preview_promotion",
    "progression_state",
    "revert_progression",
]
