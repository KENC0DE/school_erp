"""Mark workflow: windows, submission states and correction requests (P4-07).

The state machine is ``draft → submitted → approved → published → locked``;
rejecting a submission returns it to ``draft``. Every transition is explicit,
so an illegal change returns ``409 assessment.error.submission_state`` rather
than quietly jumping states. After ``locked`` the only way to change a mark is a
correction request, which an approver accepts or rejects.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from app.errors import Conflict, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.api.pagination import Page, PageParams, paginate
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import soft_delete
from core.people.models import Person
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear, Section, Subject
from modules.assessment import common, scoping
from modules.assessment.common import MODULE, decimal_out
from modules.assessment.models import (
    Assessment,
    CorrectionRequest,
    MarkingWindow,
    Score,
    ScoreRevision,
    Submission,
)
from modules.assessment.schemas import (
    CorrectionCreate,
    CorrectionDecision,
    CorrectionOut,
    CorrectionQuery,
    SubmissionAction,
    SubmissionCreate,
    SubmissionOut,
    SubmissionQuery,
    SubmissionResult,
    WindowCreate,
    WindowOut,
    WindowQuery,
    WindowUpdate,
)
from modules.students.models import StudentProfile

WINDOW_SORT = {
    "created_at": MarkingWindow.created_at,
    "opens_at": MarkingWindow.opens_at,
}
SUBMISSION_SORT = {
    "created_at": Submission.created_at,
    "status": Submission.status,
}
CORRECTION_SORT = {
    "created_at": CorrectionRequest.created_at,
    "requested_at": CorrectionRequest.requested_at,
}


def _window_state(row: MarkingWindow, now: Any) -> str:
    if not row.is_active:
        return "closed"
    opens = common.as_utc(row.opens_at)
    closes = common.as_utc(row.closes_at)
    if now < opens:
        return "scheduled"
    if now > closes:
        return "closed"
    return "open"


def _window_out(row: MarkingWindow) -> WindowOut:
    return WindowOut(
        id=str(row.id),
        year_id=str(row.year_id),
        term_id=str(row.term_id),
        level_id=str(row.level_id) if row.level_id else None,
        section_id=str(row.section_id) if row.section_id else None,
        scope_key=row.scope_key,
        opens_at=row.opens_at,
        closes_at=row.closes_at,
        is_active=row.is_active,
        state=_window_state(row, common.utcnow()),
        note=row.note,
        row_version=row.row_version,
    )


async def create_window(
    session: AsyncSession,
    principal: Principal,
    data: WindowCreate,
    *,
    via: str = "api",
) -> WindowOut:
    year = await common.live_year(session, data.year_id)
    term = await common.live_term(session, data.term_id)
    if term.year_id != year.id:
        raise ValidationFailed(
            "The term does not belong to that academic year",
            message_key="assessment.error.term_year",
            details={"term_id": str(term.id), "year_id": str(year.id)},
        )
    if data.section_id is not None:
        section = await common.live_section(session, data.section_id)
        if section.year_id != year.id:
            raise ValidationFailed(
                "The section does not belong to that academic year",
                message_key="assessment.error.section_year",
                details={"section_id": str(section.id), "year_id": str(year.id)},
            )
    if data.level_id is not None:
        await common.live_level(session, data.level_id)
    actor_id = uuid.UUID(principal.user_id) if principal.actor_type == "user" else None
    row = MarkingWindow(
        year_id=year.id,
        term_id=term.id,
        level_id=data.level_id,
        section_id=data.section_id,
        scope_key=common.window_scope_key(level_id=data.level_id, section_id=data.section_id),
        opens_at=data.opens_at,
        closes_at=data.closes_at,
        is_active=data.is_active,
        note=data.note,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await record(
        session,
        action="assessment.window.create",
        module=MODULE,
        entity_type="marking_window",
        entity_id=str(row.id),
        after=common.window_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return _window_out(row)


async def update_window(
    session: AsyncSession,
    principal: Principal,
    window_id: uuid.UUID,
    data: WindowUpdate,
    *,
    via: str = "api",
) -> WindowOut:
    row = await common.live_window(session, window_id)
    before = common.window_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    opens = data.opens_at if data.opens_at is not None else row.opens_at
    closes = data.closes_at if data.closes_at is not None else row.closes_at
    if common.as_utc(closes) <= common.as_utc(opens):
        raise ValidationFailed(
            "The closing time must be after the opening time",
            message_key="assessment.error.window_dates",
        )
    changes: dict[str, Any] = {}
    if data.opens_at is not None and data.opens_at != row.opens_at:
        changes["opens_at"] = data.opens_at
    if data.closes_at is not None and data.closes_at != row.closes_at:
        changes["closes_at"] = data.closes_at
    if data.is_active is not None and data.is_active != row.is_active:
        changes["is_active"] = data.is_active
    if data.note is not None and data.note != row.note:
        changes["note"] = data.note
    if not changes:
        return _window_out(row)
    for field, value in changes.items():
        setattr(row, field, value)
    row.row_version = (row.row_version or 0) + 1
    row.updated_by = uuid.UUID(principal.user_id) if principal.actor_type == "user" else None
    await record(
        session,
        action="assessment.window.update",
        module=MODULE,
        entity_type="marking_window",
        entity_id=str(row.id),
        before=before,
        after=common.window_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return _window_out(row)


async def delete_window(
    session: AsyncSession,
    principal: Principal,
    window_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await common.live_window(session, window_id)
    await soft_delete(
        session,
        row,
        action="assessment.window.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="marking_window",
    )
    await session.commit()
    return {"id": str(row.id), "deleted": True}


async def get_window(session: AsyncSession, window_id: uuid.UUID) -> WindowOut:
    return _window_out(await common.live_window(session, window_id))


async def list_windows(session: AsyncSession, query: WindowQuery) -> Page[WindowOut]:
    stmt = select(MarkingWindow).where(MarkingWindow.deleted_at.is_(None))
    if query.year_id is not None:
        stmt = stmt.where(MarkingWindow.year_id == query.year_id)
    if query.term_id is not None:
        stmt = stmt.where(MarkingWindow.term_id == query.term_id)
    if query.level_id is not None:
        stmt = stmt.where(MarkingWindow.level_id == query.level_id)
    if query.section_id is not None:
        stmt = stmt.where(MarkingWindow.section_id == query.section_id)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows, next_cursor = await paginate(
        session,
        stmt,
        PageParams(limit=query.limit, cursor=query.cursor, sort=query.sort, order=query.order),
        sort_columns=WINDOW_SORT,
        default_sort="opens_at",
        id_column=MarkingWindow.id,
    )
    return Page[WindowOut](
        items=[_window_out(row) for row in rows],
        next_cursor=next_cursor,
        total=total,
    )


async def _submission_counts(session: AsyncSession, row: Submission) -> tuple[int, int, int]:
    assessments = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Assessment)
                .where(
                    Assessment.year_id == row.year_id,
                    Assessment.term_id == row.term_id,
                    Assessment.section_id == row.section_id,
                    Assessment.subject_id == row.subject_id,
                    Assessment.deleted_at.is_(None),
                )
            )
        ).scalar_one()
    )
    raw_values = (
        (
            await session.execute(
                select(Score.raw_score)
                .join(Assessment, Assessment.id == Score.assessment_id)
                .where(
                    Assessment.year_id == row.year_id,
                    Assessment.term_id == row.term_id,
                    Assessment.section_id == row.section_id,
                    Assessment.subject_id == row.subject_id,
                    Assessment.deleted_at.is_(None),
                    Score.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    return assessments, len(raw_values), sum(1 for value in raw_values if value is not None)


async def _submission_out(
    session: AsyncSession,
    row: Submission,
    cache: dict[tuple[type, uuid.UUID], Any],
    *,
    counts: tuple[int, int, int] | None = None,
) -> SubmissionOut:
    async def get(model: type, ident: uuid.UUID | None) -> Any:
        if ident is None:
            return None
        key = (model, ident)
        if key not in cache:
            cache[key] = await session.get(model, ident)
        return cache[key]

    year = await get(AcademicYear, row.year_id)
    section = await get(Section, row.section_id)
    subject = await get(Subject, row.subject_id)
    assessments, scores, entered = counts if counts is not None else await _submission_counts(session, row)
    return SubmissionOut(
        id=str(row.id),
        year_id=str(row.year_id),
        year_code=year.code if year is not None else "",
        term_id=str(row.term_id),
        section_id=str(row.section_id),
        section_code=section.code if section is not None else "",
        subject_id=str(row.subject_id),
        subject_name=subject.name if subject is not None else "",
        status=row.status,
        submitted_at=row.submitted_at,
        submitted_by=str(row.submitted_by) if row.submitted_by else None,
        approved_at=row.approved_at,
        approved_by=str(row.approved_by) if row.approved_by else None,
        published_at=row.published_at,
        published_by=str(row.published_by) if row.published_by else None,
        locked_at=row.locked_at,
        locked_by=str(row.locked_by) if row.locked_by else None,
        note=row.note,
        assessments=assessments,
        scores=scores,
        entered=entered,
        row_version=row.row_version,
    )


async def _detail(session: AsyncSession, row: Submission) -> SubmissionOut:
    return await _submission_out(session, row, {})


async def ensure_submission(
    session: AsyncSession,
    principal: Principal,
    data: SubmissionCreate,
    *,
    via: str = "api",
) -> SubmissionResult:
    """Return the draft for one section/subject, creating it if needed."""
    year = await common.live_year(session, data.year_id)
    term = await common.live_term(session, data.term_id)
    if term.year_id != year.id:
        raise ValidationFailed(
            "The term does not belong to that academic year",
            message_key="assessment.error.term_year",
        )
    section = await common.live_section(session, data.section_id)
    if section.year_id != year.id:
        raise ValidationFailed(
            "The section does not belong to that academic year",
            message_key="assessment.error.section_year",
        )
    subject = await common.live_subject(session, data.subject_id)
    await scoping.assert_visible(
        session,
        principal,
        "assessment.submit",
        section_id=section.id,
        subject_id=subject.id,
    )
    existing = await common.submission_for(
        session,
        year_id=year.id,
        term_id=term.id,
        section_id=section.id,
        subject_id=subject.id,
    )
    if existing is not None:
        return SubmissionResult(submission=await _detail(session, existing))
    actor_id = uuid.UUID(principal.user_id) if principal.actor_type == "user" else None
    row = Submission(
        year_id=year.id,
        term_id=term.id,
        section_id=section.id,
        subject_id=subject.id,
        status="draft",
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await record(
        session,
        action="assessment.submission.create",
        module=MODULE,
        entity_type="submission",
        entity_id=str(row.id),
        after=common.submission_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return SubmissionResult(submission=await _detail(session, row))


async def get_submission(
    session: AsyncSession,
    principal: Principal,
    submission_id: uuid.UUID,
) -> SubmissionOut:
    row = await common.live_submission(session, submission_id)
    await scoping.assert_visible(
        session,
        principal,
        "assessment.view",
        section_id=row.section_id,
        subject_id=row.subject_id,
    )
    return await _detail(session, row)


async def list_submissions(
    session: AsyncSession,
    principal: Principal,
    query: SubmissionQuery,
) -> Page[SubmissionOut]:
    stmt = select(Submission).where(Submission.deleted_at.is_(None))
    narrowed = scoping.condition(
        await scoping.visible_access(session, principal, "assessment.view"),
        Submission,
    )
    if narrowed is not None:
        stmt = stmt.where(narrowed)
    if query.year_id is not None:
        stmt = stmt.where(Submission.year_id == query.year_id)
    if query.term_id is not None:
        stmt = stmt.where(Submission.term_id == query.term_id)
    if query.section_id is not None:
        stmt = stmt.where(Submission.section_id == query.section_id)
    if query.subject_id is not None:
        stmt = stmt.where(Submission.subject_id == query.subject_id)
    if query.status is not None:
        stmt = stmt.where(Submission.status == query.status)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows, next_cursor = await paginate(
        session,
        stmt,
        PageParams(limit=query.limit, cursor=query.cursor, sort=query.sort, order=query.order),
        sort_columns=SUBMISSION_SORT,
        default_sort="created_at",
        id_column=Submission.id,
    )
    cache: dict[tuple[type, uuid.UUID], Any] = {}
    items = [await _submission_out(session, row, cache) for row in rows]
    return Page[SubmissionOut](items=items, next_cursor=next_cursor, total=total)


async def assert_entry_open(session: AsyncSession, assessment: Assessment) -> None:
    """Block score entry when the submission moved on or a window is closed."""
    submission = await common.submission_for(
        session,
        year_id=assessment.year_id,
        term_id=assessment.term_id,
        section_id=assessment.section_id,
        subject_id=assessment.subject_id,
    )
    if submission is not None and submission.status != "draft":
        raise Conflict(
            "Marks can only change while the submission is a draft",
            message_key="assessment.error.marks_not_draft",
            details={"submission_id": str(submission.id), "status": submission.status},
        )
    section = await common.live_section(session, assessment.section_id)
    await common.assert_marking_open(
        session,
        year_id=assessment.year_id,
        term_id=assessment.term_id,
        section_id=section.id,
        level_id=section.level_id,
    )


async def _has_marks(session: AsyncSession, row: Submission) -> bool:
    count = (
        await session.execute(
            select(func.count())
            .select_from(Score)
            .join(Assessment, Assessment.id == Score.assessment_id)
            .where(
                Assessment.year_id == row.year_id,
                Assessment.term_id == row.term_id,
                Assessment.section_id == row.section_id,
                Assessment.subject_id == row.subject_id,
                Assessment.deleted_at.is_(None),
                Score.deleted_at.is_(None),
                Score.raw_score.is_not(None),
            )
        )
    ).scalar_one()
    return int(count) > 0


async def _transition(
    session: AsyncSession,
    principal: Principal,
    submission_id: uuid.UUID,
    data: SubmissionAction,
    *,
    permission: str,
    allowed: set[str],
    target: str,
    action: str,
    stamp: str,
    clear: tuple[str, ...] = (),
    via: str = "api",
) -> SubmissionOut:
    row = await common.live_submission(session, submission_id)
    before = common.submission_state(row)
    if data.row_version is not None:
        ensure_row_version(row, data.row_version, current_state=before)
    await scoping.assert_visible(
        session,
        principal,
        permission,
        section_id=row.section_id,
        subject_id=row.subject_id,
    )
    if row.status not in allowed:
        raise Conflict(
            "That mark workflow change is not allowed",
            message_key="assessment.error.submission_state",
            details={"status": row.status, "allowed": sorted(allowed), "target": target},
        )
    actor_id = uuid.UUID(principal.user_id) if principal.actor_type == "user" else None
    row.status = target
    setattr(row, f"{stamp}_at", common.utcnow())
    setattr(row, f"{stamp}_by", actor_id)
    for field in clear:
        setattr(row, field, None)
    if data.note is not None:
        row.note = data.note
    row.row_version = (row.row_version or 0) + 1
    row.updated_by = actor_id
    await record(
        session,
        action=action,
        module=MODULE,
        entity_type="submission",
        entity_id=str(row.id),
        before=before,
        after=common.submission_state(row),
        actor=principal,
        reason=data.note,
        via=via,
    )
    await session.commit()
    return await _detail(session, row)


async def submit_marks(
    session: AsyncSession,
    principal: Principal,
    submission_id: uuid.UUID,
    data: SubmissionAction,
    *,
    via: str = "api",
) -> SubmissionOut:
    row = await common.live_submission(session, submission_id)
    if row.status != "draft":
        raise Conflict(
            "That mark workflow change is not allowed",
            message_key="assessment.error.submission_state",
            details={"status": row.status, "allowed": ["draft"], "target": "submitted"},
        )
    if not await _has_marks(session, row):
        raise ValidationFailed(
            "Enter at least one mark before submitting",
            message_key="assessment.error.no_marks",
            details={"submission_id": str(row.id)},
        )
    section = await common.live_section(session, row.section_id)
    await common.assert_marking_open(
        session,
        year_id=row.year_id,
        term_id=row.term_id,
        section_id=section.id,
        level_id=section.level_id,
    )
    return await _transition(
        session,
        principal,
        submission_id,
        data,
        permission="assessment.submit",
        allowed={"draft"},
        target="submitted",
        action="assessment.submission.submit",
        stamp="submitted",
        via=via,
    )


async def approve_marks(
    session: AsyncSession,
    principal: Principal,
    submission_id: uuid.UUID,
    data: SubmissionAction,
    *,
    via: str = "api",
) -> SubmissionOut:
    return await _transition(
        session,
        principal,
        submission_id,
        data,
        permission="assessment.approve",
        allowed={"submitted"},
        target="approved",
        action="assessment.submission.approve",
        stamp="approved",
        via=via,
    )


async def reject_marks(
    session: AsyncSession,
    principal: Principal,
    submission_id: uuid.UUID,
    data: SubmissionAction,
    *,
    via: str = "api",
) -> SubmissionOut:
    return await _transition(
        session,
        principal,
        submission_id,
        data,
        permission="assessment.approve",
        allowed={"submitted"},
        target="draft",
        action="assessment.submission.reject",
        stamp="submitted",
        clear=("submitted_at", "submitted_by"),
        via=via,
    )


async def publish_marks(
    session: AsyncSession,
    principal: Principal,
    submission_id: uuid.UUID,
    data: SubmissionAction,
    *,
    via: str = "api",
) -> SubmissionOut:
    return await _transition(
        session,
        principal,
        submission_id,
        data,
        permission="assessment.publish",
        allowed={"approved"},
        target="published",
        action="assessment.submission.publish",
        stamp="published",
        via=via,
    )


async def lock_marks(
    session: AsyncSession,
    principal: Principal,
    submission_id: uuid.UUID,
    data: SubmissionAction,
    *,
    via: str = "api",
) -> SubmissionOut:
    return await _transition(
        session,
        principal,
        submission_id,
        data,
        permission="assessment.publish",
        allowed={"published"},
        target="locked",
        action="assessment.submission.lock",
        stamp="locked",
        via=via,
    )


async def _correction_out(
    session: AsyncSession,
    row: CorrectionRequest,
    cache: dict[tuple[type, uuid.UUID], Any],
) -> CorrectionOut:
    key = (StudentProfile, row.student_id)
    if key not in cache:
        cache[key] = await session.get(StudentProfile, row.student_id)
    profile = cache[key]
    person = None
    if profile is not None:
        person_key = (Person, profile.person_id)
        if person_key not in cache:
            cache[person_key] = await session.get(Person, profile.person_id)
        person = cache[person_key]
    return CorrectionOut(
        id=str(row.id),
        score_id=str(row.score_id),
        assessment_id=str(row.assessment_id),
        student_id=str(row.student_id),
        student_number=profile.student_number if profile is not None else "",
        student_name=common.person_name(person) if person is not None else "",
        year_id=str(row.year_id),
        term_id=str(row.term_id),
        section_id=str(row.section_id),
        subject_id=str(row.subject_id),
        old_raw=decimal_out(row.old_raw),
        new_raw=decimal_out(row.new_raw),
        old_status=row.old_status,
        new_status=row.new_status,
        reason=row.reason,
        status=row.status,
        requested_at=row.requested_at,
        requested_by=str(row.requested_by) if row.requested_by else None,
        decided_at=row.decided_at,
        decided_by=str(row.decided_by) if row.decided_by else None,
        decision_note=row.decision_note,
        row_version=row.row_version,
    )


async def _correction_detail(session: AsyncSession, row: CorrectionRequest) -> CorrectionOut:
    return await _correction_out(session, row, {})


async def create_correction(
    session: AsyncSession,
    principal: Principal,
    data: CorrectionCreate,
    *,
    via: str = "api",
) -> CorrectionOut:
    score = await common.live_score(session, data.score_id)
    assessment = await common.live_assessment(session, score.assessment_id)
    submission = await common.submission_for(
        session,
        year_id=assessment.year_id,
        term_id=assessment.term_id,
        section_id=assessment.section_id,
        subject_id=assessment.subject_id,
    )
    if submission is None or submission.status != "locked":
        raise Conflict(
            "A correction can only be requested after marks are locked",
            message_key="assessment.error.not_locked",
            details={"score_id": str(score.id)},
        )
    await scoping.assert_visible(
        session,
        principal,
        "assessment.correct",
        section_id=assessment.section_id,
        subject_id=assessment.subject_id,
    )
    pending = (
        await session.execute(
            select(CorrectionRequest.id).where(
                CorrectionRequest.score_id == score.id,
                CorrectionRequest.status == "pending",
                CorrectionRequest.deleted_at.is_(None),
            )
        )
    ).first()
    if pending is not None:
        raise Conflict(
            "This score already has a pending correction request",
            message_key="assessment.error.correction_pending",
            details={"score_id": str(score.id)},
        )
    component = await common.live_component(session, assessment.component_id)
    common.validate_mark(
        assessment=assessment,
        component=component,
        raw=data.new_raw,
        status=data.new_status,
        student_id=score.student_id,
    )
    if score.raw_score == data.new_raw and score.status == data.new_status:
        raise ValidationFailed(
            "The proposed value matches the current mark",
            message_key="assessment.error.correction_unchanged",
            details={"score_id": str(score.id)},
        )
    actor_id = uuid.UUID(principal.user_id) if principal.actor_type == "user" else None
    row = CorrectionRequest(
        score_id=score.id,
        assessment_id=assessment.id,
        student_id=score.student_id,
        year_id=assessment.year_id,
        term_id=assessment.term_id,
        section_id=assessment.section_id,
        subject_id=assessment.subject_id,
        old_raw=score.raw_score,
        new_raw=data.new_raw,
        old_status=score.status,
        new_status=data.new_status,
        reason=data.reason,
        status="pending",
        requested_at=common.utcnow(),
        requested_by=actor_id,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await record(
        session,
        action="assessment.correction.create",
        module=MODULE,
        entity_type="correction_request",
        entity_id=str(row.id),
        after=common.correction_state(row),
        actor=principal,
        reason=data.reason,
        via=via,
    )
    await session.commit()
    return await _correction_detail(session, row)


async def _decide(
    session: AsyncSession,
    principal: Principal,
    correction_id: uuid.UUID,
    data: CorrectionDecision,
    *,
    approve: bool,
    via: str = "api",
) -> CorrectionOut:
    row = await common.live_correction(session, correction_id)
    before = common.correction_state(row)
    if data.row_version is not None:
        ensure_row_version(row, data.row_version, current_state=before)
    await scoping.assert_visible(
        session,
        principal,
        "assessment.correct_approve",
        section_id=row.section_id,
        subject_id=row.subject_id,
    )
    if row.status != "pending":
        raise Conflict(
            "That correction request has already been decided",
            message_key="assessment.error.correction_state",
            details={"status": row.status},
        )
    actor_id = uuid.UUID(principal.user_id) if principal.actor_type == "user" else None
    score_before: dict[str, Any] | None = None
    if approve:
        assessment = await common.live_assessment(session, row.assessment_id)
        if assessment.structure_id is None:
            raise ValidationFailed(
                "No mark structure applies to this year, level and subject",
                message_key="assessment.error.no_structure",
                details={"assessment_id": str(assessment.id)},
            )
        component = await common.live_component(session, assessment.component_id)
        structure = await common.live_structure(session, assessment.structure_id)
        common.validate_mark(
            assessment=assessment,
            component=component,
            raw=row.new_raw,
            status=row.new_status or "present",
            student_id=row.student_id,
        )
        score = await common.live_score(session, row.score_id)
        score_before = common.score_state(score)
        converted = common.converted_for(
            raw=row.new_raw,
            out_of=score.out_of,
            status=row.new_status or "present",
            component=component,
            structure=structure,
        )
        score.raw_score = row.new_raw
        score.status = row.new_status or "present"
        score.converted = converted
        score.entered_at = common.utcnow()
        score.entered_by = actor_id
        score.updated_by = actor_id
        score.row_version = (score.row_version or 0) + 1
        session.add(
            ScoreRevision(
                score_id=score.id,
                assessment_id=score.assessment_id,
                student_id=score.student_id,
                correction_request_id=row.id,
                old_raw=row.old_raw,
                new_raw=row.new_raw,
                old_status=row.old_status,
                new_status=row.new_status,
                old_converted=Decimal(score_before["converted"])
                if score_before["converted"] is not None
                else None,
                new_converted=converted,
                source="correction",
                reason=row.reason,
                changed_by=actor_id,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        row.status = "approved"
    else:
        row.status = "rejected"
    row.decided_at = common.utcnow()
    row.decided_by = actor_id
    if data.note is not None:
        row.decision_note = data.note
    row.row_version = (row.row_version or 0) + 1
    row.updated_by = actor_id
    after = common.correction_state(row)
    if score_before is not None:
        after = {**after, "score": common.score_state(score)}
    await record(
        session,
        action="assessment.correction.approve" if approve else "assessment.correction.reject",
        module=MODULE,
        entity_type="correction_request",
        entity_id=str(row.id),
        before={**before, **({"score": score_before} if score_before is not None else {})},
        after=after,
        actor=principal,
        reason=data.note,
        via=via,
    )
    await session.commit()
    return await _correction_detail(session, row)


async def approve_correction(
    session: AsyncSession,
    principal: Principal,
    correction_id: uuid.UUID,
    data: CorrectionDecision,
    *,
    via: str = "api",
) -> CorrectionOut:
    return await _decide(session, principal, correction_id, data, approve=True, via=via)


async def reject_correction(
    session: AsyncSession,
    principal: Principal,
    correction_id: uuid.UUID,
    data: CorrectionDecision,
    *,
    via: str = "api",
) -> CorrectionOut:
    return await _decide(session, principal, correction_id, data, approve=False, via=via)


async def get_correction(
    session: AsyncSession,
    principal: Principal,
    correction_id: uuid.UUID,
) -> CorrectionOut:
    row = await common.live_correction(session, correction_id)
    await scoping.assert_visible(
        session,
        principal,
        "assessment.view",
        section_id=row.section_id,
        subject_id=row.subject_id,
    )
    return await _correction_detail(session, row)


async def list_corrections(
    session: AsyncSession,
    principal: Principal,
    query: CorrectionQuery,
) -> Page[CorrectionOut]:
    stmt = select(CorrectionRequest).where(CorrectionRequest.deleted_at.is_(None))
    narrowed = scoping.condition(
        await scoping.visible_access(session, principal, "assessment.view"),
        CorrectionRequest,
    )
    if narrowed is not None:
        stmt = stmt.where(narrowed)
    if query.year_id is not None:
        stmt = stmt.where(CorrectionRequest.year_id == query.year_id)
    if query.term_id is not None:
        stmt = stmt.where(CorrectionRequest.term_id == query.term_id)
    if query.section_id is not None:
        stmt = stmt.where(CorrectionRequest.section_id == query.section_id)
    if query.subject_id is not None:
        stmt = stmt.where(CorrectionRequest.subject_id == query.subject_id)
    if query.score_id is not None:
        stmt = stmt.where(CorrectionRequest.score_id == query.score_id)
    if query.status is not None:
        stmt = stmt.where(CorrectionRequest.status == query.status)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows, next_cursor = await paginate(
        session,
        stmt,
        PageParams(limit=query.limit, cursor=query.cursor, sort=query.sort, order=query.order),
        sort_columns=CORRECTION_SORT,
        default_sort="requested_at",
        id_column=CorrectionRequest.id,
    )
    cache: dict[tuple[type, uuid.UUID], Any] = {}
    items = [await _correction_out(session, row, cache) for row in rows]
    return Page[CorrectionOut](items=items, next_cursor=next_cursor, total=total)


__all__ = [
    "approve_correction",
    "approve_marks",
    "assert_entry_open",
    "create_correction",
    "create_window",
    "delete_window",
    "ensure_submission",
    "get_correction",
    "get_submission",
    "get_window",
    "list_corrections",
    "list_submissions",
    "list_windows",
    "lock_marks",
    "publish_marks",
    "reject_correction",
    "reject_marks",
    "submit_marks",
    "update_window",
]
