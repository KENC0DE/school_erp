"""Term and year results, ranks and immutable publish snapshots (P4-08).

Results are always derived from the stored raw scores; this module never writes
a score. A term sheet recomputes each subject's total from the current mark
structure, grades it with the most specific effective grade scale, and ranks the
students of the section. Publishing copies the sheet into ``ResultSnapshot`` and
refreshes ``TermResult`` with the scale version that produced each label, so a
later scale edit changes future labels but not history. Re-publishing is a
separate audited action that links the new snapshot to the one it supersedes.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.errors import Conflict, Forbidden, NotFound, ValidationFailed
from core.api.pagination import PageParams, paginate
from core.audit.service import record
from core.auth.principal import Principal
from core.people.models import Person, full_name
from sqlalchemy import false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics.models import AcademicYear, GradeLevel, Section, Subject, Term
from modules.assessment import common, grading, ranking, scoping
from modules.assessment.common import MODULE, decimal_out
from modules.assessment.engine import (
    AggregationMode,
    RoundingMode,
    ScoreStatus,
    YearMode,
    YearRule,
    round_mark,
    term_total,
    year_result,
)
from modules.assessment.engine import Component as EngineComponent
from modules.assessment.engine import Score as EngineScore
from modules.assessment.models import (
    Assessment,
    AssessmentComponent,
    AssessmentStructure,
    GradeBand,
    GradeScale,
    ResultSnapshot,
    ScaleAssignment,
    Score,
    Submission,
    TermResult,
)
from modules.assessment.schemas import (
    ResultSnapshotList,
    ResultSnapshotOut,
    ResultSnapshotQuery,
    StudentResult,
    SubjectResult,
    TermInfo,
    TermResultPublish,
    TermResultQuery,
    TermResultSheet,
    YearResultPublish,
    YearResultQuery,
    YearResultSheet,
)
from modules.students.models import StudentEnrollment, StudentProfile

STATUS_ORDER = ["draft", "submitted", "approved", "published", "locked"]
READY_STATUSES = {"approved", "published", "locked"}
SNAPSHOT_SORT = {"published_at": ResultSnapshot.published_at}


@dataclass(frozen=True)
class _ScaleRef:
    row: GradeScale
    scale: grading.GradeScale


@dataclass
class _SubjectRow:
    subject: Subject
    structure: AssessmentStructure
    scale: GradeScale | None
    total: Decimal
    out_of: Decimal
    percent: Decimal
    grade: grading.GradeResult | None
    status: str
    rank: int | None = None
    rank_size: int | None = None
    # Year sheets only: the term total that fed the year total.
    term_totals: dict[uuid.UUID, Decimal] = field(default_factory=dict)


@dataclass
class _TermComputed:
    year: AcademicYear
    term: Term
    section: Section
    level: GradeLevel
    roster: list[tuple[StudentProfile, Person, StudentEnrollment]]
    rows: dict[uuid.UUID, dict[uuid.UUID, _SubjectRow]]
    subjects: dict[uuid.UUID, Subject]
    subject_status: dict[uuid.UUID, str]


def _status_rank(value: str) -> int:
    try:
        return STATUS_ORDER.index(value)
    except ValueError:
        return 0


def _worst_status(values: list[str]) -> str:
    return min(values, key=_status_rank) if values else "draft"


def _clamp(value: Decimal, scale: grading.GradeScale) -> Decimal:
    lower = Decimal(str(scale.lower_bound))
    upper = Decimal(str(scale.upper_bound))
    return min(max(value, lower), upper)


def _percent(total: Decimal, out_of: Decimal, *, precision: int, rounding: RoundingMode) -> Decimal:
    if out_of <= 0:
        return Decimal(0)
    return round_mark(total / out_of * 100, precision=precision, rounding=rounding)


def _rounding(structure: AssessmentStructure) -> RoundingMode:
    return common.rounding_mode(structure.rounding)


def _year_rule(structure: AssessmentStructure, term_count: int) -> YearRule:
    if structure.year_mode == YearMode.WEIGHTED_AVERAGE.value:
        weights = structure.year_weights or []
        if len(weights) != term_count:
            raise ValidationFailed(
                "The year weights do not match the term count",
                message_key="assessment.error.year_weights_required",
                details={"terms": term_count, "weights": len(weights)},
            )
        return YearRule(
            mode=YearMode.WEIGHTED_AVERAGE,
            weights=[Decimal(str(weight)) for weight in weights],
        )
    return YearRule(mode=YearMode(structure.year_mode))


async def _scale_refs(
    session: AsyncSession,
) -> tuple[list[_ScaleRef], list[grading.ScaleAssignment]]:
    scale_rows = (
        (
            await session.execute(
                select(GradeScale).where(
                    GradeScale.deleted_at.is_(None),
                    GradeScale.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    if not scale_rows:
        return [], []
    band_rows = (
        (
            await session.execute(
                select(GradeBand)
                .where(
                    GradeBand.scale_id.in_([row.id for row in scale_rows]),
                    GradeBand.deleted_at.is_(None),
                )
                .order_by(GradeBand.scale_id, GradeBand.sort_order, GradeBand.min_value)
            )
        )
        .scalars()
        .all()
    )
    bands: dict[uuid.UUID, list[grading.Band]] = {}
    for row in band_rows:
        bands.setdefault(row.scale_id, []).append(
            grading.Band(
                min_value=row.min_value,
                max_value=row.max_value,
                label=row.label,
                remark=row.remark,
                gpa_points=row.gpa_points,
                is_pass=row.is_pass,
                color=row.color,
            )
        )
    refs: list[_ScaleRef] = []
    by_id: dict[uuid.UUID, _ScaleRef] = {}
    for row in scale_rows:
        if row.id not in bands:
            continue
        ref = _ScaleRef(
            row=row,
            scale=grading.GradeScale(
                name=row.name,
                bands=bands[row.id],
                type=grading.ScaleType(row.type),
                version=row.version,
                is_default=row.is_default,
                lower_bound=row.lower_bound,
                upper_bound=row.upper_bound,
                rounding=common.rounding_mode(row.rounding),
                precision=row.precision,
                effective_from=row.effective_from,
                effective_to=row.effective_to,
            ),
        )
        refs.append(ref)
        by_id[row.id] = ref
    assignment_rows = (
        (await session.execute(select(ScaleAssignment).where(ScaleAssignment.deleted_at.is_(None))))
        .scalars()
        .all()
    )
    assignments: list[grading.ScaleAssignment] = []
    for row in assignment_rows:
        ref = by_id.get(row.scale_id)
        if ref is None:
            continue
        try:
            context = grading.ScaleContext(row.context)
        except ValueError:
            continue
        key: str | None
        if context is grading.ScaleContext.DEFAULT:
            key = None
        elif context is grading.ScaleContext.ASSESSMENT:
            key = str(row.assessment_id) if row.assessment_id else None
        elif context is grading.ScaleContext.SUBJECT:
            key = str(row.subject_id) if row.subject_id else None
        elif context is grading.ScaleContext.LEVEL:
            key = str(row.level_id) if row.level_id else None
        else:
            key = str(row.stage_id) if row.stage_id else None
        if context is not grading.ScaleContext.DEFAULT and key is None:
            continue
        assignments.append(grading.ScaleAssignment(context=context, scale=ref.scale, key=key))
    return refs, assignments


def _grade(
    refs: list[_ScaleRef],
    assignments: list[grading.ScaleAssignment],
    *,
    value: Decimal,
    level_id: uuid.UUID,
    subject_id: uuid.UUID | None,
    at: date | None,
) -> tuple[grading.GradeResult | None, GradeScale | None]:
    scale = grading.resolve_scale(
        assignments,
        subject_id=str(subject_id) if subject_id is not None else None,
        level_id=str(level_id),
        at=at,
    )
    if scale is None:
        return None, None
    row = next((ref.row for ref in refs if ref.scale is scale), None)
    return grading.grade_for(scale, _clamp(value, scale)), row


async def _compute_term(
    session: AsyncSession,
    *,
    year: AcademicYear,
    term: Term,
    section: Section,
    level: GradeLevel,
    subject_id: uuid.UUID | None = None,
    refs: list[_ScaleRef],
    assignments: list[grading.ScaleAssignment],
) -> _TermComputed:
    roster = await common.enrolled_roster(session, year.id, section.id)
    assessment_stmt = select(Assessment).where(
        Assessment.year_id == year.id,
        Assessment.term_id == term.id,
        Assessment.section_id == section.id,
        Assessment.deleted_at.is_(None),
    )
    if subject_id is not None:
        assessment_stmt = assessment_stmt.where(Assessment.subject_id == subject_id)
    assessments = (
        (await session.execute(assessment_stmt.order_by(Assessment.assessment_date, Assessment.created_at)))
        .scalars()
        .all()
    )
    computed = _TermComputed(
        year=year,
        term=term,
        section=section,
        level=level,
        roster=roster,
        rows={},
        subjects={},
        subject_status={},
    )
    if not assessments or not roster:
        return computed

    assessment_ids = [row.id for row in assessments]
    score_rows = (
        (
            await session.execute(
                select(Score).where(
                    Score.assessment_id.in_(assessment_ids),
                    Score.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    score_map = {(row.assessment_id, row.student_id): row for row in score_rows}

    submissions = (
        (
            await session.execute(
                select(Submission)
                .where(
                    Submission.year_id == year.id,
                    Submission.term_id == term.id,
                    Submission.section_id == section.id,
                    Submission.deleted_at.is_(None),
                )
                .order_by(Submission.created_at, Submission.id)
            )
        )
        .scalars()
        .all()
    )
    for submission in submissions:
        computed.subject_status[submission.subject_id] = submission.status

    subject_rows = (
        (
            await session.execute(
                select(Subject).where(Subject.id.in_({row.subject_id for row in assessments}))
            )
        )
        .scalars()
        .all()
    )
    computed.subjects = {row.id: row for row in subject_rows}

    components: dict[uuid.UUID, AssessmentComponent] = {}
    for assessment in assessments:
        if assessment.component_id not in components:
            components[assessment.component_id] = await common.live_component(
                session, assessment.component_id
            )

    subject_assessments: dict[uuid.UUID, list[Assessment]] = {}
    for assessment in assessments:
        subject_assessments.setdefault(assessment.subject_id, []).append(assessment)

    for current_subject_id, current_assessments in subject_assessments.items():
        try:
            structure = await common.structure_for(
                session,
                year_id=year.id,
                level_id=level.id,
                subject_id=current_subject_id,
            )
        except NotFound:
            continue
        structure_components = [
            row for row in await common.structure_components(session, structure.id) if row.is_active
        ]
        if not structure_components:
            continue
        component_by_id = {row.id: row for row in structure_components}
        out_of = sum((Decimal(str(row.max_points)) for row in structure_components), Decimal(0))
        if out_of <= 0:
            continue
        assessments_by_component: dict[uuid.UUID, list[Assessment]] = {}
        for assessment in current_assessments:
            if assessment.component_id not in component_by_id:
                continue
            assessments_by_component.setdefault(assessment.component_id, []).append(assessment)

        status = computed.subject_status.get(current_subject_id, "draft")
        subject_percents: dict[uuid.UUID, _SubjectRow] = {}
        for profile, _person, _enrollment in roster:
            engine_components: list[EngineComponent] = []
            for component in structure_components:
                engine_scores: list[EngineScore] = []
                for assessment in assessments_by_component.get(component.id, []):
                    score = score_map.get((assessment.id, profile.id))
                    if score is None:
                        continue
                    engine_scores.append(
                        EngineScore(
                            out_of=score.out_of,
                            raw=score.raw_score,
                            status=ScoreStatus(score.status),
                            weight=assessment.weight,
                            allow_bonus=assessment.allow_bonus,
                        )
                    )
                engine_components.append(
                    EngineComponent(
                        key=component.key,
                        max_points=component.max_points,
                        scores=engine_scores,
                        aggregation=AggregationMode(component.aggregation),
                        absent_counts_as_zero=component.absent_counts_as_zero,
                        best_n=component.best_n,
                        cap=component.cap,
                    )
                )
            total = term_total(
                engine_components,
                precision=structure.precision,
                rounding=_rounding(structure),
            )
            if total is None:
                continue
            percent = _percent(
                total,
                out_of,
                precision=structure.precision,
                rounding=_rounding(structure),
            )
            grade, scale_row = _grade(
                refs,
                assignments,
                value=percent,
                level_id=level.id,
                subject_id=current_subject_id,
                at=term.end_date,
            )
            subject_percents[profile.id] = _SubjectRow(
                subject=computed.subjects[current_subject_id],
                structure=structure,
                scale=scale_row,
                total=total,
                out_of=out_of,
                percent=percent,
                grade=grade,
                status=status,
            )

        ranked = ranking.rank_students({str(key): row.percent for key, row in subject_percents.items()})
        for item in ranked:
            student_id = uuid.UUID(item.student_id)
            subject_percents[student_id].rank = item.rank
            subject_percents[student_id].rank_size = len(ranked)
        for student_id, row in subject_percents.items():
            computed.rows.setdefault(student_id, {})[current_subject_id] = row
    return computed


def _student_out(
    profile: StudentProfile,
    person: Person,
    enrollment: StudentEnrollment,
    subject_rows: list[_SubjectRow],
    *,
    refs: list[_ScaleRef],
    assignments: list[grading.ScaleAssignment],
    level_id: uuid.UUID,
    at: date | None,
    include_terms: bool,
) -> StudentResult:
    subjects: list[SubjectResult] = []
    total = Decimal(0)
    out_of = Decimal(0)
    statuses: list[str] = []
    for row in sorted(subject_rows, key=lambda item: item.subject.name):
        subjects.append(
            SubjectResult(
                subject_id=str(row.subject.id),
                subject_name=row.subject.name,
                structure_id=str(row.structure.id),
                structure_version=row.structure.version,
                scale_id=str(row.scale.id) if row.scale is not None else None,
                scale_version=row.scale.version if row.scale is not None else None,
                total=decimal_out(row.total) or "0",
                out_of=decimal_out(row.out_of) or "0",
                percent=decimal_out(row.percent) or "0",
                grade_label=row.grade.label if row.grade is not None else None,
                grade_remark=row.grade.remark if row.grade is not None else None,
                gpa_points=decimal_out(row.grade.gpa_points) if row.grade is not None else None,
                is_pass=row.grade.is_pass if row.grade is not None else True,
                rank=row.rank,
                rank_size=row.rank_size,
                status=row.status,
                terms=(
                    {str(term_id): decimal_out(value) or "0" for term_id, value in row.term_totals.items()}
                    if include_terms
                    else None
                ),
            )
        )
        total += row.total
        out_of += row.out_of
        statuses.append(row.status)
    percent = _percent(total, out_of, precision=2, rounding=RoundingMode.HALF_UP)
    grade, _scale = _grade(
        refs,
        assignments,
        value=percent,
        level_id=level_id,
        subject_id=None,
        at=at,
    )
    return StudentResult(
        student_id=str(profile.id),
        student_number=profile.student_number,
        student_name=full_name(person),
        student_name_am=full_name(person, "am"),
        roll_number=enrollment.roll_number,
        subjects=subjects,
        total=decimal_out(total) or "0",
        out_of=decimal_out(out_of) or "0",
        percent=decimal_out(percent) or "0",
        grade_label=grade.label if grade is not None else None,
        grade_remark=grade.remark if grade is not None else None,
        gpa_points=decimal_out(grade.gpa_points) if grade is not None else None,
        is_pass=grade.is_pass if grade is not None else True,
        status=_worst_status(statuses),
    )


def _visible_subjects(
    subjects: set[uuid.UUID],
    access: scoping.MarkAccess | None,
    section_id: uuid.UUID,
) -> set[uuid.UUID]:
    if access is None:
        return subjects
    return {subject_id for subject_id in subjects if access.allows(section_id, subject_id)}


def _overall_rank(
    totals: dict[uuid.UUID, tuple[Decimal, Decimal]],
) -> dict[uuid.UUID, tuple[int, int]]:
    ranked = ranking.rank_students(
        {
            str(student_id): _percent(total, out_of, precision=2, rounding=RoundingMode.HALF_UP)
            for student_id, (total, out_of) in totals.items()
        }
    )
    return {uuid.UUID(item.student_id): (item.rank, len(ranked)) for item in ranked}


def _term_sheet(
    computed: _TermComputed,
    access: scoping.MarkAccess | None,
    refs: list[_ScaleRef],
    assignments: list[grading.ScaleAssignment],
) -> TermResultSheet:
    subject_ids = _visible_subjects(set(computed.subjects), access, computed.section.id)
    totals: dict[uuid.UUID, tuple[Decimal, Decimal]] = {}
    selected_rows: dict[uuid.UUID, list[_SubjectRow]] = {}
    for profile, _person, _enrollment in computed.roster:
        selected = [
            row for subject_id, row in computed.rows.get(profile.id, {}).items() if subject_id in subject_ids
        ]
        if not selected:
            continue
        selected_rows[profile.id] = selected
        totals[profile.id] = (
            sum((row.total for row in selected), Decimal(0)),
            sum((row.out_of for row in selected), Decimal(0)),
        )
    rank_map = _overall_rank(totals) if access is None else {}

    students: list[StudentResult] = []
    for profile, person, enrollment in computed.roster:
        selected = selected_rows.get(profile.id)
        if not selected:
            continue
        student = _student_out(
            profile,
            person,
            enrollment,
            selected,
            refs=refs,
            assignments=assignments,
            level_id=computed.level.id,
            at=computed.term.end_date,
            include_terms=False,
        )
        if profile.id in rank_map:
            student.rank, student.rank_size = rank_map[profile.id]
        students.append(student)
    return TermResultSheet(
        year_id=str(computed.year.id),
        year_code=computed.year.code,
        term_id=str(computed.term.id),
        term_name=computed.term.name,
        section_id=str(computed.section.id),
        section_code=computed.section.code,
        level_id=str(computed.level.id),
        level_name=computed.level.name,
        students=students,
        subject_count=len(subject_ids),
    )


async def _term_inputs(
    session: AsyncSession,
    year_id: uuid.UUID,
    term_id: uuid.UUID,
    section_id: uuid.UUID,
) -> tuple[AcademicYear, Term, Section, GradeLevel]:
    year = await common.live_year(session, year_id)
    term = await common.live_term(session, term_id)
    if term.year_id != year.id:
        raise ValidationFailed(
            "The term does not belong to that academic year",
            message_key="assessment.error.term_year",
        )
    section = await common.live_section(session, section_id)
    if section.year_id != year.id:
        raise ValidationFailed(
            "The section does not belong to that academic year",
            message_key="assessment.error.section_year",
        )
    level = await common.live_level(session, section.level_id)
    return year, term, section, level


async def _assert_view_scope(
    session: AsyncSession,
    principal: Principal,
    *,
    section_id: uuid.UUID,
    subject_id: uuid.UUID | None,
    present_subjects: set[uuid.UUID],
) -> scoping.MarkAccess | None:
    access = await scoping.visible_access(session, principal, "assessment.view")
    if access is None:
        return None
    if subject_id is not None:
        await scoping.assert_visible(
            session,
            principal,
            "assessment.view",
            section_id=section_id,
            subject_id=subject_id,
        )
    allowed = _visible_subjects(present_subjects, access, section_id)
    if present_subjects and not allowed:
        raise Forbidden(
            "These results are outside your assessment scope",
            message_key="error.scope_denied",
            details={"section_id": str(section_id)},
        )
    return access


async def term_results(
    session: AsyncSession,
    principal: Principal,
    query: TermResultQuery,
) -> TermResultSheet:
    year, term, section, level = await _term_inputs(session, query.year_id, query.term_id, query.section_id)
    refs, assignments = await _scale_refs(session)
    computed = await _compute_term(
        session,
        year=year,
        term=term,
        section=section,
        level=level,
        subject_id=query.subject_id,
        refs=refs,
        assignments=assignments,
    )
    access = await _assert_view_scope(
        session,
        principal,
        section_id=section.id,
        subject_id=query.subject_id,
        present_subjects=set(computed.subjects),
    )
    return _term_sheet(computed, access, refs, assignments)


async def _year_sheets(
    session: AsyncSession,
    *,
    year: AcademicYear,
    section: Section,
    level: GradeLevel,
) -> tuple[list[Term], list[_TermComputed], list[_ScaleRef], list[grading.ScaleAssignment]]:
    terms = (
        (
            await session.execute(
                select(Term).where(Term.year_id == year.id, Term.deleted_at.is_(None)).order_by(Term.number)
            )
        )
        .scalars()
        .all()
    )
    refs, assignments = await _scale_refs(session)
    sheets = [
        await _compute_term(
            session,
            year=year,
            term=term,
            section=section,
            level=level,
            refs=refs,
            assignments=assignments,
        )
        for term in terms
    ]
    return list(terms), sheets, refs, assignments


def _year_out_of(
    structure: AssessmentStructure,
    terms: list[Term],
    present: list[tuple[int, _SubjectRow]],
) -> Decimal:
    mode = structure.year_mode
    if mode == YearMode.SUM.value:
        return sum((row.out_of for _, row in present), Decimal(0))
    if mode == YearMode.AVERAGE.value:
        return sum((row.out_of for _, row in present), Decimal(0)) / len(present)
    weights = [Decimal(str(weight)) for weight in structure.year_weights or []]
    if len(weights) != len(terms):
        raise ValidationFailed(
            "The year weights do not match the term count",
            message_key="assessment.error.year_weights_required",
            details={"terms": len(terms), "weights": len(weights)},
        )
    total_weight = sum((weights[index] for index, _ in present), Decimal(0))
    if total_weight <= 0:
        return present[-1][1].out_of
    return sum((weights[index] * row.out_of for index, row in present), Decimal(0)) / total_weight


def _year_sheet(
    year: AcademicYear,
    section: Section,
    level: GradeLevel,
    terms: list[Term],
    sheets: list[_TermComputed],
    access: scoping.MarkAccess | None,
    refs: list[_ScaleRef],
    assignments: list[grading.ScaleAssignment],
) -> YearResultSheet:
    subject_ids: set[uuid.UUID] = set()
    for sheet in sheets:
        subject_ids |= set(sheet.subjects)
    subject_ids = _visible_subjects(subject_ids, access, section.id)

    # student -> subject -> term -> computed subject row
    collected: dict[uuid.UUID, dict[uuid.UUID, dict[uuid.UUID, _SubjectRow]]] = {}
    for sheet in sheets:
        for student_id, rows in sheet.rows.items():
            for subject_id, row in rows.items():
                if subject_id not in subject_ids:
                    continue
                collected.setdefault(student_id, {}).setdefault(subject_id, {})[sheet.term.id] = row

    year_rows: dict[uuid.UUID, dict[uuid.UUID, _SubjectRow]] = {}
    for student_id, by_subject in collected.items():
        for subject_id, by_term in by_subject.items():
            values: list[Decimal | None] = []
            present: list[tuple[int, _SubjectRow]] = []
            for index, term in enumerate(terms):
                row = by_term.get(term.id)
                values.append(row.total if row is not None else None)
                if row is not None:
                    present.append((index, row))
            if not present:
                continue
            structure = present[-1][1].structure
            rule = _year_rule(structure, len(terms))
            combined = year_result(
                values,
                rule,
                precision=structure.precision,
                rounding=_rounding(structure),
            )
            if combined is None:
                continue
            out_of = _year_out_of(structure, terms, present)
            if out_of <= 0:
                continue
            percent = _percent(
                combined,
                out_of,
                precision=structure.precision,
                rounding=_rounding(structure),
            )
            grade, scale_row = _grade(
                refs,
                assignments,
                value=percent,
                level_id=level.id,
                subject_id=subject_id,
                at=year.end_date,
            )
            year_rows.setdefault(student_id, {})[subject_id] = _SubjectRow(
                subject=present[-1][1].subject,
                structure=structure,
                scale=scale_row,
                total=combined,
                out_of=out_of,
                percent=percent,
                grade=grade,
                status=_worst_status([row.status for _, row in present]),
                term_totals={terms[index].id: row.total for index, row in present},
            )

    for subject_id in subject_ids:
        values = {
            str(student_id): rows[subject_id].percent
            for student_id, rows in year_rows.items()
            if subject_id in rows
        }
        ranked = ranking.rank_students(values)
        for item in ranked:
            rows = year_rows.get(uuid.UUID(item.student_id))
            if rows is not None and subject_id in rows:
                rows[subject_id].rank = item.rank
                rows[subject_id].rank_size = len(ranked)

    totals: dict[uuid.UUID, tuple[Decimal, Decimal]] = {}
    for student_id, rows in year_rows.items():
        totals[student_id] = (
            sum((row.total for row in rows.values()), Decimal(0)),
            sum((row.out_of for row in rows.values()), Decimal(0)),
        )
    rank_map = _overall_rank(totals) if access is None else {}

    roster = next((sheet.roster for sheet in sheets if sheet.roster), [])
    students: list[StudentResult] = []
    for profile, person, enrollment in roster:
        rows = year_rows.get(profile.id)
        if not rows:
            continue
        student = _student_out(
            profile,
            person,
            enrollment,
            list(rows.values()),
            refs=refs,
            assignments=assignments,
            level_id=level.id,
            at=year.end_date,
            include_terms=True,
        )
        if profile.id in rank_map:
            student.rank, student.rank_size = rank_map[profile.id]
        students.append(student)
    return YearResultSheet(
        year_id=str(year.id),
        year_code=year.code,
        section_id=str(section.id),
        section_code=section.code,
        level_id=str(level.id),
        level_name=level.name,
        terms=[TermInfo(id=str(term.id), number=term.number, name=term.name) for term in terms],
        students=students,
        subject_count=len(subject_ids),
    )


async def year_results(
    session: AsyncSession,
    principal: Principal,
    query: YearResultQuery,
) -> YearResultSheet:
    year = await common.live_year(session, query.year_id)
    section = await common.live_section(session, query.section_id)
    if section.year_id != year.id:
        raise ValidationFailed(
            "The section does not belong to that academic year",
            message_key="assessment.error.section_year",
        )
    level = await common.live_level(session, section.level_id)
    terms, sheets, refs, assignments = await _year_sheets(session, year=year, section=section, level=level)
    present_subjects: set[uuid.UUID] = set()
    for sheet in sheets:
        present_subjects |= set(sheet.subjects)
    access = await _assert_view_scope(
        session,
        principal,
        section_id=section.id,
        subject_id=None,
        present_subjects=present_subjects,
    )
    return _year_sheet(year, section, level, terms, sheets, access, refs, assignments)


def _assert_ready(sheets: list[_TermComputed]) -> None:
    blocked: list[str] = []
    for computed in sheets:
        for subject_id in sorted(computed.subjects, key=str):
            status = computed.subject_status.get(subject_id, "draft")
            if status not in READY_STATUSES:
                blocked.append(f"{computed.subjects[subject_id].name}: {status}")
    if blocked:
        raise Conflict(
            "Marks must be approved before results are published",
            message_key="assessment.error.results_not_ready",
            details={"blocked": sorted(blocked)},
        )


async def _assert_can_publish(session: AsyncSession, principal: Principal) -> None:
    access = await scoping.visible_access(session, principal, "assessment.publish")
    if access is not None:
        raise Forbidden(
            "Publishing results needs school-wide access",
            message_key="error.scope_denied",
        )


def _checksum(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _snapshot_out(row: ResultSnapshot) -> ResultSnapshotOut:
    return ResultSnapshotOut(
        id=str(row.id),
        kind=row.kind,
        year_id=str(row.year_id),
        term_id=str(row.term_id) if row.term_id else None,
        section_id=str(row.section_id) if row.section_id else None,
        student_id=str(row.student_id) if row.student_id else None,
        structure_id=str(row.structure_id) if row.structure_id else None,
        structure_version=row.structure_version,
        scale_id=str(row.scale_id) if row.scale_id else None,
        scale_version=row.scale_version,
        checksum=row.checksum,
        published_at=common.as_utc(row.published_at),
        published_by=str(row.published_by) if row.published_by else None,
        note=row.note,
        supersedes_id=str(row.supersedes_id) if row.supersedes_id else None,
        payload=row.payload,
    )


async def _previous_snapshot(
    session: AsyncSession,
    *,
    kind: str,
    year_id: uuid.UUID,
    term_id: uuid.UUID | None,
    section_id: uuid.UUID,
) -> ResultSnapshot | None:
    stmt = select(ResultSnapshot).where(
        ResultSnapshot.kind == kind,
        ResultSnapshot.year_id == year_id,
        ResultSnapshot.section_id == section_id,
        ResultSnapshot.student_id.is_(None),
        ResultSnapshot.deleted_at.is_(None),
    )
    if term_id is None:
        stmt = stmt.where(ResultSnapshot.term_id.is_(None))
    else:
        stmt = stmt.where(ResultSnapshot.term_id == term_id)
    return (
        (await session.execute(stmt.order_by(ResultSnapshot.published_at.desc(), ResultSnapshot.id.desc())))
        .scalars()
        .first()
    )


def _shared_structure(students: list[StudentResult]) -> tuple[uuid.UUID | None, int | None]:
    found = {
        (row.structure_id, row.structure_version)
        for student in students
        for row in student.subjects
        if row.structure_id is not None
    }
    if len(found) != 1:
        return None, None
    structure_id, version = found.pop()
    return uuid.UUID(str(structure_id)), version


def _shared_scale(students: list[StudentResult]) -> tuple[uuid.UUID | None, int | None]:
    found = {
        (row.scale_id, row.scale_version)
        for student in students
        for row in student.subjects
        if row.scale_id is not None
    }
    if len(found) != 1:
        return None, None
    scale_id, version = found.pop()
    return uuid.UUID(str(scale_id)), version


def _actor_id(principal: Principal) -> uuid.UUID | None:
    if principal.actor_type != "user":
        return None
    try:
        return uuid.UUID(principal.user_id)
    except ValueError:  # pragma: no cover - guarded by auth
        return None


async def _write_term_rows(
    session: AsyncSession,
    principal: Principal,
    *,
    computed: _TermComputed,
    sheet: TermResultSheet,
    published_at: datetime,
) -> None:
    existing = (
        (
            await session.execute(
                select(TermResult).where(
                    TermResult.year_id == computed.year.id,
                    TermResult.term_id == computed.term.id,
                    TermResult.section_id == computed.section.id,
                    TermResult.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    by_key = {(row.subject_id, row.student_id): row for row in existing}
    actor_id = _actor_id(principal)
    for student in sheet.students:
        for subject in student.subjects:
            key = (uuid.UUID(subject.subject_id), uuid.UUID(student.student_id))
            row = by_key.get(key)
            if row is None:
                row = TermResult(
                    year_id=computed.year.id,
                    term_id=computed.term.id,
                    section_id=computed.section.id,
                    subject_id=key[0],
                    student_id=key[1],
                    created_by=actor_id,
                )
                session.add(row)
            else:
                row.row_version = (row.row_version or 0) + 1
            row.updated_by = actor_id
            row.structure_id = uuid.UUID(subject.structure_id) if subject.structure_id else None
            row.structure_version = subject.structure_version
            row.scale_id = uuid.UUID(subject.scale_id) if subject.scale_id else None
            row.scale_version = subject.scale_version
            row.total = Decimal(subject.total)
            row.out_of = Decimal(subject.out_of)
            row.percent = Decimal(subject.percent)
            row.grade_label = subject.grade_label
            row.grade_remark = subject.grade_remark
            row.gpa_points = Decimal(subject.gpa_points) if subject.gpa_points is not None else None
            row.is_pass = subject.is_pass
            row.rank = subject.rank
            row.rank_size = subject.rank_size
            row.status = "published"
            row.published_at = published_at
    await session.flush()


async def _create_snapshot(
    session: AsyncSession,
    principal: Principal,
    *,
    kind: str,
    year_id: uuid.UUID,
    term_id: uuid.UUID | None,
    section_id: uuid.UUID,
    sheet: TermResultSheet | YearResultSheet,
    note: str | None,
    supersedes: ResultSnapshot | None,
    action: str,
    via: str,
    published_at: datetime,
) -> ResultSnapshotOut:
    students = sheet.students
    structure_id, structure_version = _shared_structure(students)
    scale_id, scale_version = _shared_scale(students)
    payload = sheet.model_dump(mode="json")
    payload["kind"] = kind
    payload["published_at"] = published_at.isoformat()
    payload["snapshot"] = {
        "structure_id": str(structure_id) if structure_id else None,
        "structure_version": structure_version,
        "scale_id": str(scale_id) if scale_id else None,
        "scale_version": scale_version,
        "supersedes_id": str(supersedes.id) if supersedes is not None else None,
    }
    row = ResultSnapshot(
        year_id=year_id,
        term_id=term_id,
        section_id=section_id,
        kind=kind,
        structure_id=structure_id,
        structure_version=structure_version,
        scale_id=scale_id,
        scale_version=scale_version,
        payload=payload,
        checksum=_checksum(payload),
        published_at=published_at,
        published_by=_actor_id(principal),
        note=note,
        supersedes_id=supersedes.id if supersedes is not None else None,
        created_by=_actor_id(principal),
        updated_by=_actor_id(principal),
    )
    session.add(row)
    await session.flush()
    await record(
        session,
        action=action,
        module=MODULE,
        entity_type="result_snapshot",
        entity_id=str(row.id),
        after={
            "kind": kind,
            "section_id": str(section_id),
            "term_id": str(term_id) if term_id else None,
            "students": len(students),
            "checksum": row.checksum,
            "supersedes_id": str(supersedes.id) if supersedes is not None else None,
        },
        actor=principal,
        reason=note,
        via=via,
    )
    return _snapshot_out(row)


async def publish_term_results(
    session: AsyncSession,
    principal: Principal,
    data: TermResultPublish,
    *,
    republish: bool = False,
    via: str = "api",
) -> ResultSnapshotOut:
    await _assert_can_publish(session, principal)
    year, term, section, level = await _term_inputs(session, data.year_id, data.term_id, data.section_id)
    refs, assignments = await _scale_refs(session)
    computed = await _compute_term(
        session,
        year=year,
        term=term,
        section=section,
        level=level,
        refs=refs,
        assignments=assignments,
    )
    if not computed.rows:
        raise ValidationFailed(
            "There are no results to publish",
            message_key="assessment.error.results_empty",
        )
    _assert_ready([computed])
    sheet = _term_sheet(computed, None, refs, assignments)
    previous = await _previous_snapshot(
        session,
        kind="term",
        year_id=year.id,
        term_id=term.id,
        section_id=section.id,
    )
    if previous is not None and not republish:
        raise Conflict(
            "These results are already published; use re-publish",
            message_key="assessment.error.results_already_published",
            details={"snapshot_id": str(previous.id)},
        )
    if previous is None and republish:
        raise Conflict(
            "These results have not been published yet",
            message_key="assessment.error.no_published_result",
        )
    published_at = common.utcnow()
    result = await _create_snapshot(
        session,
        principal,
        kind="term",
        year_id=year.id,
        term_id=term.id,
        section_id=section.id,
        sheet=sheet,
        note=data.note,
        supersedes=previous,
        action="assessment.results.republish" if republish else "assessment.results.publish",
        via=via,
        published_at=published_at,
    )
    await _write_term_rows(
        session,
        principal,
        computed=computed,
        sheet=sheet,
        published_at=published_at,
    )
    await session.commit()
    return result


async def republish_term_results(
    session: AsyncSession,
    principal: Principal,
    data: TermResultPublish,
    *,
    via: str = "api",
) -> ResultSnapshotOut:
    return await publish_term_results(session, principal, data, republish=True, via=via)


async def publish_year_results(
    session: AsyncSession,
    principal: Principal,
    data: YearResultPublish,
    *,
    republish: bool = False,
    via: str = "api",
) -> ResultSnapshotOut:
    await _assert_can_publish(session, principal)
    year = await common.live_year(session, data.year_id)
    section = await common.live_section(session, data.section_id)
    if section.year_id != year.id:
        raise ValidationFailed(
            "The section does not belong to that academic year",
            message_key="assessment.error.section_year",
        )
    level = await common.live_level(session, section.level_id)
    terms, sheets, refs, assignments = await _year_sheets(session, year=year, section=section, level=level)
    if not any(sheet.rows for sheet in sheets):
        raise ValidationFailed(
            "There are no results to publish",
            message_key="assessment.error.results_empty",
        )
    _assert_ready(sheets)
    sheet = _year_sheet(year, section, level, terms, sheets, None, refs, assignments)
    previous = await _previous_snapshot(
        session,
        kind="year",
        year_id=year.id,
        term_id=None,
        section_id=section.id,
    )
    if previous is not None and not republish:
        raise Conflict(
            "These results are already published; use re-publish",
            message_key="assessment.error.results_already_published",
            details={"snapshot_id": str(previous.id)},
        )
    if previous is None and republish:
        raise Conflict(
            "These results have not been published yet",
            message_key="assessment.error.no_published_result",
        )
    result = await _create_snapshot(
        session,
        principal,
        kind="year",
        year_id=year.id,
        term_id=None,
        section_id=section.id,
        sheet=sheet,
        note=data.note,
        supersedes=previous,
        action="assessment.results.republish" if republish else "assessment.results.publish",
        via=via,
        published_at=common.utcnow(),
    )
    await session.commit()
    return result


async def republish_year_results(
    session: AsyncSession,
    principal: Principal,
    data: YearResultPublish,
    *,
    via: str = "api",
) -> ResultSnapshotOut:
    return await publish_year_results(session, principal, data, republish=True, via=via)


async def _snapshot_visible(
    session: AsyncSession,
    principal: Principal,
    row: ResultSnapshot,
) -> None:
    if row.section_id is None:
        return
    access = await scoping.visible_access(session, principal, "assessment.view")
    if access is None:
        return
    allowed = row.section_id in access.sections or any(pair[0] == row.section_id for pair in access.pairs)
    if not allowed:
        raise Forbidden(
            "These results are outside your assessment scope",
            message_key="error.scope_denied",
            details={"section_id": str(row.section_id)},
        )


async def get_snapshot(
    session: AsyncSession,
    principal: Principal,
    snapshot_id: uuid.UUID,
) -> ResultSnapshotOut:
    row = (
        await session.execute(
            select(ResultSnapshot).where(
                ResultSnapshot.id == snapshot_id,
                ResultSnapshot.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The result snapshot does not exist",
            message_key="assessment.error.snapshot_not_found",
        )
    await _snapshot_visible(session, principal, row)
    return _snapshot_out(row)


async def list_snapshots(
    session: AsyncSession,
    principal: Principal,
    query: ResultSnapshotQuery,
) -> ResultSnapshotList:
    stmt = select(ResultSnapshot).where(ResultSnapshot.deleted_at.is_(None))
    if query.year_id is not None:
        stmt = stmt.where(ResultSnapshot.year_id == query.year_id)
    if query.term_id is not None:
        stmt = stmt.where(ResultSnapshot.term_id == query.term_id)
    if query.section_id is not None:
        stmt = stmt.where(ResultSnapshot.section_id == query.section_id)
    if query.student_id is not None:
        stmt = stmt.where(ResultSnapshot.student_id == query.student_id)
    if query.kind is not None:
        stmt = stmt.where(ResultSnapshot.kind == query.kind)
    access = await scoping.visible_access(session, principal, "assessment.view")
    if access is not None:
        sections = set(access.sections) | {pair[0] for pair in access.pairs}
        if not sections:
            stmt = stmt.where(false())
        else:
            stmt = stmt.where(ResultSnapshot.section_id.in_(sorted(sections)))
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows, next_cursor = await paginate(
        session,
        stmt,
        PageParams(limit=query.limit, cursor=query.cursor, order=query.order),
        sort_columns=SNAPSHOT_SORT,
        default_sort="published_at",
        id_column=ResultSnapshot.id,
    )
    return ResultSnapshotList(
        items=[_snapshot_out(row) for row in rows],
        next_cursor=next_cursor,
        total=total,
    )


__all__ = [
    "get_snapshot",
    "list_snapshots",
    "publish_term_results",
    "publish_year_results",
    "republish_term_results",
    "republish_year_results",
    "term_results",
    "year_results",
]
