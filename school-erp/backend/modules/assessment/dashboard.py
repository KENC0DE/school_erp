"""Manager progress dashboard: completion, overdue marks and anomaly warnings (P4-14).

The dashboard is a read model over the assessment tables: one row per
(section, subject) pair for a year and term, with the number of assessments,
the expected number of marks, how many were entered, the submission state and
the marking deadline. Two anomalies are warnings only and never block entry:

* every recorded raw mark of an assessment is identical (a possible copy), and
* an assessment average is far from the norm of its own section and subject.

Reminders reuse the core notification service and its seeded
``assessment.entry_reminder`` template. They are explicit, audited actions: a
manager (or a scheduled job) calls the endpoint, and only overdue draft rows
with a named, linked teacher receive a message.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from app.errors import ValidationFailed
from core.audit.service import record
from core.auth.principal import Principal
from core.notifications.service import send_notification
from core.people.models import Person, full_name
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from modules.academics.models import GradeLevel, Section, Subject
from modules.assessment import common, scoping
from modules.assessment.common import MODULE, decimal_out
from modules.assessment.models import (
    Assessment,
    AssessmentComponent,
    MarkingWindow,
    Score,
    Submission,
)
from modules.assessment.schemas import (
    DashboardAnomaly,
    DashboardOut,
    DashboardQuery,
    DashboardRow,
    DashboardSummary,
    DashboardTeacher,
    ReminderRecipient,
    ReminderRequest,
    ReminderResult,
)
from modules.staff.models import StaffProfile, StaffTeachingAssignment
from modules.students.models import StudentEnrollment, StudentProfile

# A whole class has to have at least this many marks before an identical run
# is worth flagging; small classes can legitimately all score the same.
IDENTICAL_MIN = 5
# Percentage points away from the section/subject norm before a warning shows.
OUTLIER_THRESHOLD = Decimal("25")
OVERDUE_STATUSES = frozenset({"draft", "missing"})
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class _Teacher:
    staff_id: str
    user_id: str | None
    name: str


@dataclass
class _Collected:
    out: DashboardOut
    year_code: str
    term_name: str
    sections: dict[uuid.UUID, tuple[Section, GradeLevel]] = field(default_factory=dict)
    subjects: dict[uuid.UUID, Subject] = field(default_factory=dict)
    teachers: dict[tuple[uuid.UUID, uuid.UUID], list[_Teacher]] = field(default_factory=dict)


def _percent(part: int, whole: int, places: str = "0.1") -> Decimal:
    if whole <= 0:
        return Decimal("0")
    return (Decimal(part) * HUNDRED / Decimal(whole)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _filters(query: DashboardQuery) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = [
        Assessment.year_id == query.year_id,
        Assessment.term_id == query.term_id,
        Assessment.deleted_at.is_(None),
        Assessment.status == "active",
    ]
    if query.section_id is not None:
        clauses.append(Assessment.section_id == query.section_id)
    if query.subject_id is not None:
        clauses.append(Assessment.subject_id == query.subject_id)
    return clauses


def _window_state(rows: list[MarkingWindow], now: datetime) -> tuple[datetime | None, str | None]:
    if not rows:
        return None, None
    closes = [common.as_utc(row.closes_at) for row in rows]
    opens = [common.as_utc(row.opens_at) for row in rows]
    deadline = max(closes)
    if any(start <= now <= end for start, end in zip(opens, closes, strict=True)):
        return deadline, "open"
    if all(end < now for end in closes):
        return deadline, "closed"
    return deadline, "scheduled"


async def _roster_counts(
    session: AsyncSession,
    year_id: uuid.UUID,
    section_ids: set[uuid.UUID],
) -> dict[uuid.UUID, int]:
    if not section_ids:
        return {}
    rows = (
        await session.execute(
            select(StudentEnrollment.section_id, func.count())
            .join(StudentProfile, StudentProfile.id == StudentEnrollment.student_id)
            .join(Person, Person.id == StudentProfile.person_id)
            .where(
                StudentEnrollment.year_id == year_id,
                StudentEnrollment.section_id.in_(section_ids),
                StudentEnrollment.deleted_at.is_(None),
                StudentEnrollment.status == "active",
                StudentProfile.deleted_at.is_(None),
                Person.deleted_at.is_(None),
            )
            .group_by(StudentEnrollment.section_id)
        )
    ).all()
    return {section_id: int(count) for section_id, count in rows}


async def _teachers(
    session: AsyncSession,
    year_id: uuid.UUID,
    section_ids: set[uuid.UUID],
) -> dict[tuple[uuid.UUID, uuid.UUID], list[_Teacher]]:
    if not section_ids:
        return {}
    rows = (
        await session.execute(
            select(
                StaffTeachingAssignment.section_id,
                StaffTeachingAssignment.subject_id,
                StaffProfile.id,
                StaffProfile.user_id,
                Person,
            )
            .join(StaffProfile, StaffProfile.id == StaffTeachingAssignment.staff_id)
            .join(Person, Person.id == StaffProfile.person_id)
            .where(
                StaffTeachingAssignment.year_id == year_id,
                StaffTeachingAssignment.section_id.in_(section_ids),
                StaffTeachingAssignment.deleted_at.is_(None),
                StaffProfile.deleted_at.is_(None),
                Person.deleted_at.is_(None),
            )
        )
    ).all()
    result: dict[tuple[uuid.UUID, uuid.UUID], list[_Teacher]] = defaultdict(list)
    for section_id, subject_id, staff_id, user_id, person in rows:
        result[(section_id, subject_id)].append(
            _Teacher(
                staff_id=str(staff_id),
                user_id=str(user_id) if user_id is not None else None,
                name=full_name(person),
            )
        )
    for entries in result.values():
        entries.sort(key=lambda item: item.name)
    return dict(result)


async def _anomalies(
    session: AsyncSession,
    filters: list[ColumnElement[bool]],
    assessments: list[Assessment],
    sections: dict[uuid.UUID, tuple[Section, GradeLevel]],
    subjects: dict[uuid.UUID, Subject],
    components: dict[uuid.UUID, AssessmentComponent],
) -> list[DashboardAnomaly]:
    if not assessments:
        return []
    rows = (
        await session.execute(
            select(
                Assessment.id,
                Score.raw_score,
                Score.converted,
            )
            .join(Assessment, Assessment.id == Score.assessment_id)
            .where(*filters, Score.deleted_at.is_(None))
        )
    ).all()
    raw: dict[uuid.UUID, list[Decimal]] = defaultdict(list)
    converted: dict[uuid.UUID, list[Decimal]] = defaultdict(list)
    for assessment_id, raw_score, converted_value in rows:
        if raw_score is not None:
            raw[assessment_id].append(raw_score)
        if converted_value is not None:
            converted[assessment_id].append(converted_value)

    anomalies: list[DashboardAnomaly] = []
    pair_averages: dict[tuple[uuid.UUID, uuid.UUID], list[tuple[Assessment, Decimal]]] = defaultdict(list)
    for assessment in assessments:
        section = sections.get(assessment.section_id)
        subject = subjects.get(assessment.subject_id)
        if section is None or subject is None:
            continue
        base = {
            "assessment_id": str(assessment.id),
            "title": assessment.title,
            "section_id": str(assessment.section_id),
            "section_code": section[0].code,
            "subject_id": str(assessment.subject_id),
            "subject_name": subject.name,
        }
        values = raw.get(assessment.id, [])
        if len(values) >= IDENTICAL_MIN and len(set(values)) == 1:
            anomalies.append(
                DashboardAnomaly(
                    kind="identical",
                    count=len(values),
                    value=decimal_out(values[0]),
                    threshold=str(IDENTICAL_MIN),
                    **base,
                )
            )
        scores = converted.get(assessment.id, [])
        component = components.get(assessment.component_id)
        if not scores or component is None or component.max_points <= 0:
            continue
        average = (sum(scores, Decimal(0)) / len(scores)) * HUNDRED / component.max_points
        pair_averages[(assessment.section_id, assessment.subject_id)].append(
            (assessment, average.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        )

    for entries in pair_averages.values():
        if len(entries) < 3:
            continue
        for assessment, average in entries:
            others = [value for other, value in entries if other.id != assessment.id]
            if not others:
                continue
            norm = sum(others, Decimal(0)) / len(others)
            if abs(average - norm) < OUTLIER_THRESHOLD:
                continue
            section = sections.get(assessment.section_id)
            subject = subjects.get(assessment.subject_id)
            if section is None or subject is None:
                continue
            anomalies.append(
                DashboardAnomaly(
                    kind="average_outlier",
                    assessment_id=str(assessment.id),
                    title=assessment.title,
                    section_id=str(assessment.section_id),
                    section_code=section[0].code,
                    subject_id=str(assessment.subject_id),
                    subject_name=subject.name,
                    count=len(converted.get(assessment.id, [])),
                    threshold=str(OUTLIER_THRESHOLD),
                    average_percent=decimal_out(average),
                    norm_percent=decimal_out(norm.quantize(Decimal("0.01"))),
                )
            )
    anomalies.sort(
        key=lambda item: (
            item.section_code,
            item.subject_name,
            item.kind,
            item.title,
        )
    )
    return anomalies


async def _collect(
    session: AsyncSession,
    principal: Principal,
    query: DashboardQuery,
    *,
    now: datetime | None = None,
) -> _Collected:
    year = await common.live_year(session, query.year_id)
    term = await common.live_term(session, query.term_id)
    if term.year_id != year.id:
        raise ValidationFailed(
            "The term does not belong to that academic year",
            message_key="assessment.error.term_year",
            details={"term_id": str(term.id), "year_id": str(year.id)},
        )
    moment = now or common.utcnow()
    filters = _filters(query)
    access = await scoping.visible_access(session, principal, "assessment.view")
    narrowed = scoping.condition(access, Assessment)
    if narrowed is not None:
        filters.append(narrowed)

    assessments = (await session.execute(select(Assessment).where(*filters))).scalars().all()
    groups: dict[tuple[uuid.UUID, uuid.UUID], list[Assessment]] = defaultdict(list)
    for assessment in assessments:
        groups[(assessment.section_id, assessment.subject_id)].append(assessment)

    section_ids = {assessment.section_id for assessment in assessments}
    subject_ids = {assessment.subject_id for assessment in assessments}
    component_ids = {assessment.component_id for assessment in assessments}

    sections: dict[uuid.UUID, tuple[Section, GradeLevel]] = {}
    if section_ids:
        rows = (
            await session.execute(
                select(Section, GradeLevel)
                .join(GradeLevel, GradeLevel.id == Section.level_id)
                .where(Section.id.in_(section_ids))
            )
        ).all()
        sections = {section.id: (section, level) for section, level in rows}
    subjects: dict[uuid.UUID, Subject] = {}
    if subject_ids:
        rows = (await session.execute(select(Subject).where(Subject.id.in_(subject_ids)))).scalars().all()
        subjects = {subject.id: subject for subject in rows}
    components: dict[uuid.UUID, AssessmentComponent] = {}
    if component_ids:
        rows = (
            (
                await session.execute(
                    select(AssessmentComponent).where(AssessmentComponent.id.in_(component_ids))
                )
            )
            .scalars()
            .all()
        )
        components = {component.id: component for component in rows}

    rosters = await _roster_counts(session, query.year_id, section_ids)
    teachers = await _teachers(session, query.year_id, section_ids)

    submissions: dict[tuple[uuid.UUID, uuid.UUID], str] = {}
    windows: list[MarkingWindow] = []
    if groups:
        submission_stmt = select(Submission).where(
            Submission.year_id == query.year_id,
            Submission.term_id == query.term_id,
            Submission.deleted_at.is_(None),
        )
        narrowed_submission = scoping.condition(access, Submission)
        if narrowed_submission is not None:
            submission_stmt = submission_stmt.where(narrowed_submission)
        for row in (await session.execute(submission_stmt)).scalars():
            submissions[(row.section_id, row.subject_id)] = row.status
        windows = list(
            (
                await session.execute(
                    select(MarkingWindow).where(
                        MarkingWindow.year_id == query.year_id,
                        MarkingWindow.term_id == query.term_id,
                        MarkingWindow.is_active.is_(True),
                        MarkingWindow.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )

    entered: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
    if groups:
        rows = (
            await session.execute(
                select(
                    Assessment.section_id,
                    Assessment.subject_id,
                    func.count(Score.id),
                )
                .join(Assessment, Assessment.id == Score.assessment_id)
                .where(*filters, Score.deleted_at.is_(None))
                .group_by(Assessment.section_id, Assessment.subject_id)
            )
        ).all()
        entered = {(section_id, subject_id): int(count) for section_id, subject_id, count in rows}

    result_rows: list[DashboardRow] = []
    total_expected = 0
    total_entered = 0
    overdue_count = 0
    for (section_id, subject_id), group in groups.items():
        section = sections.get(section_id)
        subject = subjects.get(subject_id)
        if section is None or subject is None:
            continue
        row_section, level = section
        applicable = [
            window
            for window in windows
            if window.scope_key in ("all", f"level:{level.id}", f"section:{section_id}")
        ]
        deadline, window_state = _window_state(applicable, moment)
        status = submissions.get((section_id, subject_id), "missing")
        students = rosters.get(section_id, 0)
        expected = students * len(group)
        entered_count = entered.get((section_id, subject_id), 0)
        completion = _percent(entered_count, expected)
        overdue = (
            deadline is not None and moment > deadline and completion < HUNDRED and status in OVERDUE_STATUSES
        )
        total_expected += expected
        total_entered += entered_count
        overdue_count += 1 if overdue else 0
        result_rows.append(
            DashboardRow(
                section_id=str(section_id),
                section_code=row_section.code,
                level_id=str(level.id),
                level_name=level.name,
                subject_id=str(subject_id),
                subject_name=subject.name,
                teachers=[
                    DashboardTeacher(staff_id=teacher.staff_id, name=teacher.name)
                    for teacher in teachers.get((section_id, subject_id), [])
                ],
                assessments=len(group),
                students=students,
                expected=expected,
                entered=entered_count,
                missing=max(expected - entered_count, 0),
                completion_percent=decimal_out(completion) or "0",
                status=status,
                deadline=deadline,
                window_state=window_state,
                overdue=overdue,
            )
        )
    result_rows.sort(
        key=lambda row: (
            row.level_name,
            row.section_code,
            row.subject_name,
        )
    )
    anomalies = await _anomalies(session, filters, list(assessments), sections, subjects, components)
    summary = DashboardSummary(
        sections=len({row.section_id for row in result_rows}),
        assessments=len(assessments),
        expected=total_expected,
        entered=total_entered,
        completion_percent=decimal_out(_percent(total_entered, total_expected)) or "0",
        overdue=overdue_count,
        anomalies=len(anomalies),
    )
    return _Collected(
        out=DashboardOut(
            year_id=str(year.id),
            term_id=str(term.id),
            rows=result_rows,
            anomalies=anomalies,
            summary=summary,
        ),
        year_code=year.code,
        term_name=term.name,
        sections=sections,
        subjects=subjects,
        teachers=teachers,
    )


async def dashboard(
    session: AsyncSession,
    principal: Principal,
    query: DashboardQuery,
) -> DashboardOut:
    """Return completion, overdue rows and anomaly warnings for one term."""
    return (await _collect(session, principal, query)).out


async def send_reminders(
    session: AsyncSession,
    principal: Principal,
    request: ReminderRequest,
    *,
    via: str = "api",
) -> ReminderResult:
    """Notify linked teachers of every overdue draft row.

    The action is idempotent only in the sense that repeating it sends again;
    callers schedule it (or press the button) deliberately. A teacher without a
    linked user account is counted as skipped instead of silently dropped.
    """
    collected = await _collect(
        session,
        principal,
        DashboardQuery(
            year_id=request.year_id,
            term_id=request.term_id,
            section_id=request.section_id,
            subject_id=request.subject_id,
        ),
    )
    overdue_rows = [row for row in collected.out.rows if row.overdue]
    recipients: list[ReminderRecipient] = []
    sent = 0
    skipped = 0
    for row in overdue_rows:
        pair = (uuid.UUID(row.section_id), uuid.UUID(row.subject_id))
        section = collected.sections.get(pair[0])
        section_name = f"{section[1].name} {section[0].code}".strip() if section is not None else ""
        params = {
            "section": section_name,
            "subject": row.subject_name,
            "term": collected.term_name,
            "year": collected.year_code,
            "deadline": row.deadline.date().isoformat() if row.deadline else "",
            "entered": row.entered,
            "expected": row.expected,
            "completion": row.completion_percent,
        }
        for teacher in collected.teachers.get(pair, []):
            if teacher.user_id is None:
                skipped += 1
                continue
            await send_notification(
                session,
                user_id=teacher.user_id,
                template_key="assessment.entry_reminder",
                params=params,
                channels=["in_app"],
                link="/assessment",
                actor=principal,
                module=MODULE,
            )
            sent += 1
            recipients.append(
                ReminderRecipient(
                    user_id=teacher.user_id,
                    staff_id=teacher.staff_id,
                    name=teacher.name,
                    section_id=row.section_id,
                    subject_id=row.subject_id,
                )
            )
    await record(
        session,
        action="assessment.dashboard.remind",
        module=MODULE,
        entity_type="assessment_dashboard",
        entity_id=f"{request.year_id}:{request.term_id}",
        after={
            "year_id": str(request.year_id),
            "term_id": str(request.term_id),
            "rows": len(overdue_rows),
            "sent": sent,
            "skipped": skipped,
        },
        actor=principal,
        via=via,
    )
    await session.commit()
    return ReminderResult(
        rows=len(overdue_rows),
        sent=sent,
        skipped=skipped,
        recipients=recipients,
    )


__all__ = ["dashboard", "send_reminders"]
