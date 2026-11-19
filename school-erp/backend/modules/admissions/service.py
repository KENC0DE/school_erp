"""Admission applications: intake, decisions, placement and conversion (ARCH §9.2)."""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, date, datetime
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from app.settings import Settings
from core.api.concurrency import ensure_row_version
from core.api.pagination import PageParams, contains, paginate
from core.audit.service import record
from core.auth.models import User
from core.auth.principal import Principal
from core.auth.recovery import send_reset_link
from core.auth.security import hash_password
from core.custom_fields.service import (
    definition_view,
    definitions_for,
    merge_custom,
    validate_entity_values,
)
from core.db.soft_delete import get_including_deleted, get_live, restore, soft_delete
from core.events.service import emit
from core.notifications.service import send_notification
from core.people.models import Person, full_name, normalize_name
from core.people.service import (
    create_person,
    prepare_person,
    update_person,
)
from core.people.service import (
    duplicate_warnings as person_duplicate_warnings,
)
from core.rbac.models import Role, UserRole
from core.settings.core_schema import CoreSettings
from core.settings.service import load_model
from fastapi import Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics import section_service
from modules.academics import service as catalog
from modules.academics import years as year_service
from modules.admissions import numbering
from modules.admissions.models import (
    ADMISSION_STATUSES,
    TRANSITIONS,
    AdmissionApplication,
    AdmissionGuardian,
)
from modules.admissions.schemas import (
    AdmissionFormOut,
    ApplicationCreate,
    ApplicationList,
    ApplicationOut,
    ApplicationPreview,
    ApplicationQuery,
    ApplicationSummary,
    ApplicationUpdate,
    ConversionInput,
    ConversionOut,
    ConversionPreview,
    DecisionInput,
    DecisionOut,
    GuardianAccountPlan,
)
from modules.admissions.settings import AdmissionSettings
from modules.students import enrollment_service, guardian_service
from modules.students import numbering as student_numbering
from modules.students import service as student_service
from modules.students.lookups import AcademicLabels
from modules.students.schemas import EnrollmentInput, GuardianInput
from modules.students.views import person_out

logger = logging.getLogger("erp.admissions")

MODULE = "admissions"
ENTITY = "admission_application"
SORT_COLUMNS = {
    "created_at": AdmissionApplication.created_at,
    "application_number": AdmissionApplication.application_number,
    "status": AdmissionApplication.status,
}
STATUS_VALUES = set(ADMISSION_STATUSES)
# A decision closes the application; only an open application may be edited.
ACCOUNT_OPEN_STATUSES = {"applied", "reviewed", "test", "offered"}


async def load_settings(session: AsyncSession) -> AdmissionSettings:
    return await load_model(session, MODULE, AdmissionSettings)


def _assert_status(value: str) -> None:
    if value not in STATUS_VALUES:
        raise ValidationFailed(
            "Unknown admission status",
            message_key="admissions.error.status_invalid",
            details={"status": value},
        )


def application_state(row: AdmissionApplication, *, guardians: list[str] | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "application_number": row.application_number,
        "person_id": str(row.person_id),
        "year_id": str(row.year_id),
        "level_id": str(row.level_id),
        "section_id": str(row.section_id) if row.section_id else None,
        "status": row.status,
        "entrance_test_score": row.entrance_test_score,
        "student_id": str(row.student_id) if row.student_id else None,
        "row_version": row.row_version,
    }
    if guardians is not None:
        state["guardian_ids"] = guardians
    return state


def _guardian_state(row: AdmissionGuardian) -> dict[str, Any]:
    return {
        "application_id": str(row.application_id),
        "person_id": str(row.person_id),
        "relationship": row.relationship,
        "is_primary": row.is_primary,
        "can_pickup": row.can_pickup,
        "wants_account": row.wants_account,
        "account_user_id": str(row.account_user_id) if row.account_user_id else None,
        "row_version": row.row_version,
    }


async def live_application(session: AsyncSession, application_id: uuid.UUID) -> AdmissionApplication:
    row = (
        await session.execute(
            select(AdmissionApplication).where(
                AdmissionApplication.id == application_id,
                AdmissionApplication.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The application does not exist",
            message_key="admissions.error.not_found",
        )
    return row


async def _guardians(session: AsyncSession, application_id: uuid.UUID) -> list[AdmissionGuardian]:
    return list(
        (
            await session.execute(
                select(AdmissionGuardian)
                .where(
                    AdmissionGuardian.application_id == application_id,
                    AdmissionGuardian.deleted_at.is_(None),
                )
                .order_by(AdmissionGuardian.created_at, AdmissionGuardian.id)
            )
        )
        .scalars()
        .all()
    )


async def _person(session: AsyncSession, person_id: uuid.UUID) -> Person:
    return await get_live(session, Person, person_id)


async def _guardian_out(
    row: AdmissionGuardian,
    person: Person,
    *,
    locale: str,
) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "application_id": str(row.application_id),
        "person_id": str(row.person_id),
        "relationship": row.relationship,
        "is_primary": row.is_primary,
        "can_pickup": row.can_pickup,
        "wants_account": row.wants_account,
        "account_user_id": str(row.account_user_id) if row.account_user_id else None,
        "notes": row.notes,
        "person": person_out(person, locale),
        "row_version": row.row_version,
    }


async def _decided_by_name(session: AsyncSession, user_id: uuid.UUID | None) -> str | None:
    if user_id is None:
        return None
    user = await session.get(User, user_id)
    return user.display_name if user is not None else None


def _test_passed(score: int | None, settings: AdmissionSettings) -> bool | None:
    if score is None or not settings.entrance_test.enabled:
        return None
    if settings.entrance_test.pass_score is None:
        return True
    return score >= settings.entrance_test.pass_score


async def _base_out(
    session: AsyncSession,
    row: AdmissionApplication,
    person: Person,
    *,
    locale: str,
    settings: AdmissionSettings,
    labels: AcademicLabels,
) -> dict[str, Any]:
    year = await labels.year(row.year_id)
    level = await labels.level(row.level_id)
    section = await labels.section(row.section_id) if row.section_id else None
    student_number = (
        await student_service.student_number_for(session, row.student_id)
        if row.student_id is not None
        else None
    )
    return {
        "id": str(row.id),
        "application_number": row.application_number,
        "status": row.status,
        "applied_on": row.applied_on,
        "source": row.source,
        "person": person_out(person, locale),
        "year_id": str(row.year_id),
        "year_code": year.code if year else None,
        "year_name": year.name if year else None,
        "level_id": str(row.level_id),
        "level_code": level.code if level else None,
        "level_name": level.name if level else None,
        "section_id": str(row.section_id) if row.section_id else None,
        "section_code": section.code if section else None,
        "entrance_test_score": row.entrance_test_score,
        "student_id": str(row.student_id) if row.student_id else None,
        "student_number": student_number,
        "row_version": row.row_version,
        "notes": row.notes,
        "custom": row.custom or {},
        "decision_notes": row.decision_notes,
        "decided_by": await _decided_by_name(session, row.decided_by),
        "decided_at": row.decided_at,
        "converted_at": row.converted_at,
        "test_max_score": settings.entrance_test.max_score,
        "test_pass_score": settings.entrance_test.pass_score,
        "test_passed": _test_passed(row.entrance_test_score, settings),
    }


async def application_view(
    session: AsyncSession,
    row: AdmissionApplication,
    *,
    locale: str = "en",
    include_guardians: bool = True,
) -> ApplicationOut:
    settings = await load_settings(session)
    labels = AcademicLabels(session)
    person = await _person(session, row.person_id)
    data = await _base_out(session, row, person, locale=locale, settings=settings, labels=labels)
    if include_guardians:
        items = []
        for guardian in await _guardians(session, row.id):
            guardian_person = await _person(session, guardian.person_id)
            items.append(await _guardian_out(guardian, guardian_person, locale=locale))
        data["guardians"] = items
    return ApplicationOut(**data)


async def list_applications(session: AsyncSession, query: ApplicationQuery) -> ApplicationList:
    stmt = (
        select(AdmissionApplication)
        .join(Person, Person.id == AdmissionApplication.person_id)
        .where(
            AdmissionApplication.deleted_at.is_(None),
            Person.deleted_at.is_(None),
        )
    )
    if query.status is not None:
        _assert_status(query.status)
        stmt = stmt.where(AdmissionApplication.status == query.status)
    if query.year_id is not None:
        stmt = stmt.where(AdmissionApplication.year_id == query.year_id)
    if query.level_id is not None:
        stmt = stmt.where(AdmissionApplication.level_id == query.level_id)
    if query.section_id is not None:
        stmt = stmt.where(AdmissionApplication.section_id == query.section_id)
    if query.q:
        terms = normalize_name(query.q).split()
        matches = [contains(AdmissionApplication.application_number, query.q)]
        if terms:
            matches.append(and_(*[Person.search_name.like(f"%{term}%") for term in terms]))
        stmt = stmt.where(or_(*matches))

    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    params = PageParams(limit=query.limit, cursor=query.cursor, sort=query.sort, order=query.order)
    rows, next_cursor = await paginate(
        session,
        stmt,
        params,
        sort_columns=SORT_COLUMNS,
        default_sort="created_at",
        id_column=AdmissionApplication.id,
    )
    settings = await load_settings(session)
    labels = AcademicLabels(session)
    people = {
        person.id: person
        for person in (
            await session.execute(select(Person).where(Person.id.in_([row.person_id for row in rows])))
        )
        .scalars()
        .all()
    }
    items: list[ApplicationSummary] = []
    for row in rows:
        person = people.get(row.person_id)
        if person is None:  # pragma: no cover - the join guarantees a live person
            continue
        data = await _base_out(session, row, person, locale="en", settings=settings, labels=labels)
        for key in (
            "notes",
            "custom",
            "decision_notes",
            "decided_by",
            "decided_at",
            "converted_at",
            "test_max_score",
            "test_pass_score",
            "test_passed",
        ):
            data.pop(key, None)
        items.append(ApplicationSummary(**data))
    return ApplicationList(items=items, next_cursor=next_cursor, total=total)


async def _assert_year_open(session: AsyncSession, year_id: uuid.UUID) -> Any:
    year = await year_service.get_year(session, year_id)
    if year.status == "closed":
        raise Conflict(
            "A closed academic year cannot take applications",
            message_key="admissions.error.year_closed",
            details={"year_id": str(year_id), "status": year.status},
        )
    return year


async def _assert_section_matches(
    session: AsyncSession,
    year_id: uuid.UUID,
    level_id: uuid.UUID,
    section_id: uuid.UUID | None,
) -> Any:
    if section_id is None:
        return None
    section = await section_service.get_section(session, section_id)
    if section.year_id != str(year_id) or section.level_id != str(level_id):
        raise ValidationFailed(
            "The section does not belong to that academic year and level",
            message_key="admissions.error.section_mismatch",
            details={"section_id": str(section_id)},
        )
    if not section.is_active:
        raise ValidationFailed(
            "An inactive section cannot receive applications",
            message_key="admissions.error.section_inactive",
            details={"section_id": str(section_id)},
        )
    return section


def _validate_score(score: int | None, settings: AdmissionSettings) -> None:
    if score is None:
        return
    if not settings.entrance_test.enabled:
        raise ValidationFailed(
            "The entrance test is disabled",
            message_key="admissions.error.test_disabled",
        )
    if score > settings.entrance_test.max_score:
        raise ValidationFailed(
            "The entrance test score is above the maximum",
            message_key="admissions.error.test_score_range",
            details={"score": score, "max_score": settings.entrance_test.max_score},
        )


async def _resolve_year(session: AsyncSession, requested: uuid.UUID | None) -> uuid.UUID:
    if requested is not None:
        await _assert_year_open(session, requested)
        return requested
    years = await year_service.list_years(session)
    if not years.items:
        raise ValidationFailed(
            "Create an academic year before taking applications",
            message_key="admissions.error.year_required",
        )
    chosen = next((item for item in years.items if item.status == "open"), None)
    if chosen is None:
        chosen = next((item for item in years.items if item.status != "closed"), None)
    if chosen is None:
        raise Conflict(
            "A closed academic year cannot take applications",
            message_key="admissions.error.year_closed",
        )
    return uuid.UUID(chosen.id)


def _validate_guardians(guardians: list[Any], *, require_guardian: bool) -> None:
    if require_guardian and not guardians:
        raise ValidationFailed(
            "An application needs at least one guardian",
            message_key="admissions.error.guardian_required",
        )
    seen: set[uuid.UUID] = set()
    for guardian in guardians:
        if guardian.person_id is None:
            continue
        if guardian.person_id in seen:
            raise ValidationFailed(
                "The same guardian appears twice",
                message_key="admissions.error.guardian_duplicate",
                details={"person_id": str(guardian.person_id)},
            )
        seen.add(guardian.person_id)


async def _person_already_applied(
    session: AsyncSession,
    person_id: uuid.UUID,
    year_id: uuid.UUID,
    *,
    current_id: uuid.UUID | None = None,
) -> bool:
    stmt = select(AdmissionApplication.id).where(
        AdmissionApplication.person_id == person_id,
        AdmissionApplication.year_id == year_id,
        AdmissionApplication.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(AdmissionApplication.id != current_id)
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _duplicate_warnings_for(
    session: AsyncSession,
    data: ApplicationCreate,
) -> tuple[Person, list[dict[str, Any]]]:
    if data.person is not None:
        return await prepare_person(session, data.person.model_dump())
    assert data.person_id is not None  # guaranteed by the schema validator
    person = await _person(session, data.person_id)
    return person, await person_duplicate_warnings(session, person)


async def preview_application(session: AsyncSession, data: ApplicationCreate) -> ApplicationPreview:
    settings = await load_settings(session)
    year_id = await _resolve_year(session, data.year_id)
    level = await catalog.get_level(session, data.level_id)
    section = await _assert_section_matches(session, year_id, data.level_id, data.section_id)
    _validate_guardians(data.guardians, require_guardian=settings.form.require_guardian)
    _validate_score(data.entrance_test_score, settings)
    custom_count = 0
    cleaned = await validate_entity_values(session, ENTITY, data.custom or {})
    custom_count = len(cleaned)
    person, warnings = await _duplicate_warnings_for(session, data)
    number = await numbering.peek_number(session, year_id=year_id)
    year = await year_service.get_year(session, year_id)
    return ApplicationPreview(
        application_number=number.application_number,
        full_name=full_name(person),
        year_code=year.code,
        level_code=level.code,
        section_code=section.code if section else None,
        guardian_count=len(data.guardians),
        custom_field_count=custom_count,
        duplicate_warnings=warnings,
    )


async def create_application(
    session: AsyncSession,
    principal: Principal,
    data: ApplicationCreate,
    *,
    via: str = "api",
) -> tuple[AdmissionApplication, list[dict[str, Any]]]:
    settings = await load_settings(session)
    year_id = await _resolve_year(session, data.year_id)
    await catalog.get_level(session, data.level_id)
    await _assert_section_matches(session, year_id, data.level_id, data.section_id)
    _validate_guardians(data.guardians, require_guardian=settings.form.require_guardian)
    _validate_score(data.entrance_test_score, settings)
    cleaned = await validate_entity_values(session, ENTITY, data.custom or {})
    custom = merge_custom(None, cleaned)

    person: Person | None = None
    warnings: list[dict[str, Any]] = []
    if data.person_id is not None:
        person = await _person(session, data.person_id)
        if await _person_already_applied(session, person.id, year_id):
            raise Conflict(
                "That person already has an application for this academic year",
                message_key="admissions.error.application_exists",
                details={"person_id": str(person.id), "year_id": str(year_id)},
            )
        warnings = await person_duplicate_warnings(session, person)

    # Reserving the number commits its own short transaction, so do it before
    # staging the person and application writes. A failed create leaves a gap,
    # never a duplicate.
    allocation = await numbering.allocate_number(session, year_id=year_id)
    if person is None:
        person, warnings = await create_person(
            session,
            principal,
            data.person.model_dump() if data.person else {},
            via=via,
            commit=False,
        )

    row = AdmissionApplication(
        person_id=person.id,
        application_number=allocation.application_number,
        year_id=year_id,
        level_id=data.level_id,
        section_id=data.section_id,
        status="applied",
        entrance_test_score=data.entrance_test_score,
        applied_on=data.applied_on or date.today(),
        source=data.source,
        notes=data.notes,
        custom=custom,
    )
    session.add(row)
    await session.flush()

    guardian_ids: list[str] = []
    seen: set[uuid.UUID] = set()
    for guardian in data.guardians:
        if guardian.person is not None:
            guardian_person, _ = await create_person(
                session, principal, guardian.person.model_dump(), via=via, commit=False
            )
        else:
            assert guardian.person_id is not None  # guaranteed by the schema validator
            guardian_person = await _person(session, guardian.person_id)
        if guardian_person.id in seen:
            raise ValidationFailed(
                "The same guardian appears twice",
                message_key="admissions.error.guardian_duplicate",
                details={"person_id": str(guardian_person.id)},
            )
        if guardian_person.id == person.id:
            raise ValidationFailed(
                "An applicant cannot be their own guardian",
                message_key="admissions.error.guardian_is_applicant",
            )
        seen.add(guardian_person.id)
        link = AdmissionGuardian(
            application_id=row.id,
            person_id=guardian_person.id,
            relationship=guardian.relationship,
            is_primary=guardian.is_primary,
            can_pickup=guardian.can_pickup,
            wants_account=guardian.wants_account,
            notes=guardian.notes,
        )
        session.add(link)
        await session.flush()
        guardian_ids.append(str(link.id))

    await record(
        session,
        action="admissions.application.create",
        module=MODULE,
        entity_type=ENTITY,
        entity_id=str(row.id),
        after=application_state(row, guardians=guardian_ids),
        actor=principal,
        via=via,
    )
    await emit(
        session,
        "admission.application_created",
        {
            "application_id": str(row.id),
            "application_number": row.application_number,
            "person_id": str(person.id),
            "year_id": str(year_id),
            "level_id": str(data.level_id),
        },
        actor_id=principal.actor_id,
    )
    await session.commit()
    return row, warnings


async def get_application(
    session: AsyncSession,
    principal: Principal,
    application_id: uuid.UUID,
) -> ApplicationOut:
    row = await live_application(session, application_id)
    return await application_view(session, row, locale=principal.locale)


async def update_application(
    session: AsyncSession,
    principal: Principal,
    application_id: uuid.UUID,
    data: ApplicationUpdate,
    *,
    via: str = "api",
) -> ApplicationOut:
    row = await live_application(session, application_id)
    ensure_row_version(row, data.row_version, current_state=application_state(row))
    if row.status not in ACCOUNT_OPEN_STATUSES:
        raise Conflict(
            "A decided application can no longer be edited",
            message_key="admissions.error.locked",
            details={"status": row.status},
        )
    settings = await load_settings(session)
    payload = data.model_dump(exclude_unset=True)
    if data.person is not None:
        await update_person(
            session,
            principal,
            row.person_id,
            data.person.model_dump(exclude_unset=True),
            via=via,
            commit=False,
        )
    year_id = data.year_id or row.year_id
    level_id = data.level_id or row.level_id
    section_id = payload.get("section_id", row.section_id)
    if data.year_id is not None or data.level_id is not None:
        if data.section_id is None:
            section_id = None
        await _assert_year_open(session, year_id)
        await catalog.get_level(session, level_id)
        await _assert_section_matches(session, year_id, level_id, section_id)
        payload["section_id"] = section_id
    elif data.section_id is not None:
        await _assert_section_matches(session, year_id, level_id, data.section_id)
    if "entrance_test_score" in payload:
        _validate_score(data.entrance_test_score, settings)
    if "custom" in payload and data.custom is not None:
        cleaned = await validate_entity_values(session, ENTITY, data.custom, partial=True)
        payload["custom"] = merge_custom(row.custom, cleaned)

    for key in (
        "year_id",
        "level_id",
        "section_id",
        "entrance_test_score",
        "applied_on",
        "notes",
        "custom",
    ):
        if key in payload:
            setattr(row, key, payload[key])
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="admissions.application.update",
        module=MODULE,
        entity_type=ENTITY,
        entity_id=str(row.id),
        after=application_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return await application_view(session, row, locale=principal.locale)


async def decide_application(
    session: AsyncSession,
    principal: Principal,
    application_id: uuid.UUID,
    data: DecisionInput,
    *,
    via: str = "api",
) -> DecisionOut:
    row = await live_application(session, application_id)
    ensure_row_version(row, data.row_version, current_state=application_state(row))
    _assert_status(data.status)
    previous = row.status
    before_score = row.entrance_test_score
    allowed = TRANSITIONS.get(previous, ())
    if data.status not in allowed:
        raise Conflict(
            "That decision is not allowed from the current status",
            message_key="admissions.error.transition",
            details={"from": previous, "to": data.status, "allowed": list(allowed)},
        )
    settings = await load_settings(session)
    score = data.entrance_test_score if data.entrance_test_score is not None else before_score
    _validate_score(score, settings)
    if data.status in {"test", "offered"} and settings.entrance_test.enabled and score is None:
        raise ValidationFailed(
            "Record the entrance test score before this step",
            message_key="admissions.error.test_required",
        )
    if (
        data.status == "offered"
        and settings.entrance_test.enabled
        and settings.entrance_test.pass_score is not None
        and score is not None
        and score < settings.entrance_test.pass_score
    ):
        raise ValidationFailed(
            "The entrance test score is below the pass mark",
            message_key="admissions.error.test_below_pass",
            details={"score": score, "pass_score": settings.entrance_test.pass_score},
        )

    row.status = data.status
    if data.entrance_test_score is not None:
        row.entrance_test_score = data.entrance_test_score
    if data.notes is not None:
        row.decision_notes = data.notes
    if data.status in {"reviewed", "test", "offered", "accepted", "rejected"}:
        row.decided_by = uuid.UUID(principal.actor_id) if principal.actor_id else None
        row.decided_at = datetime.now(UTC)
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="admissions.application.decide",
        module=MODULE,
        entity_type=ENTITY,
        entity_id=str(row.id),
        before={"status": previous, "entrance_test_score": before_score},
        after={"status": row.status, "entrance_test_score": row.entrance_test_score},
        actor=principal,
        via=via,
        reason=data.notes,
    )
    await emit(
        session,
        "admission.decision",
        {
            "application_id": str(row.id),
            "from": previous,
            "to": row.status,
            "entrance_test_score": row.entrance_test_score,
        },
        actor_id=principal.actor_id,
    )
    await session.commit()
    return DecisionOut(
        application=await application_view(session, row, locale=principal.locale),
        previous_status=previous,  # type: ignore[arg-type]
        status=row.status,  # type: ignore[arg-type]
    )


async def _auto_section(
    session: AsyncSession,
    *,
    year_id: uuid.UUID,
    level_id: uuid.UUID,
    settings: AdmissionSettings,
) -> Any:
    if not settings.assignment.auto_assign_section:
        return None
    sections = await section_service.list_sections(
        session, year_id=year_id, level_id=level_id, include_inactive=False
    )
    if not sections.items:
        return None
    occupancy = await enrollment_service.section_occupancy(session, year_id=year_id, level_id=level_id)
    open_sections = [
        section
        for section in sections.items
        if section.capacity is None or occupancy.get(uuid.UUID(section.id), 0) < section.capacity
    ]
    if not open_sections:
        return None
    if settings.assignment.section_strategy == "first":
        return open_sections[0]
    return min(
        open_sections,
        key=lambda section: (occupancy.get(uuid.UUID(section.id), 0), section.code),
    )


async def _placement(
    session: AsyncSession,
    row: AdmissionApplication,
    settings: AdmissionSettings,
) -> tuple[Any, Any, Any, str, list[str]]:
    warnings: list[str] = []
    year = await year_service.get_year(session, row.year_id)
    level = await catalog.get_level(session, row.level_id)
    source = "none"
    section = None
    if row.section_id is not None:
        section = await section_service.get_section(session, row.section_id)
        source = "application"
    else:
        section = await _auto_section(session, year_id=row.year_id, level_id=row.level_id, settings=settings)
        if section is not None:
            source = "auto"
        elif settings.assignment.auto_assign_section:
            warnings.append("no_section_capacity")
    return year, level, section, source, warnings


async def _account_plan(
    session: AsyncSession,
    application_id: uuid.UUID,
    settings: AdmissionSettings,
) -> list[GuardianAccountPlan]:
    role = (
        await session.execute(
            select(Role).where(
                Role.key == settings.form.guardian_role_key,
                Role.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    plans: list[GuardianAccountPlan] = []
    for guardian in await _guardians(session, application_id):
        if not guardian.wants_account:
            continue
        person = await _person(session, guardian.person_id)
        email = (person.email or "").strip().lower() or None
        if role is None:
            action = "role_missing"
        elif email is None:
            action = "no_email"
        else:
            exists = (await session.execute(select(User.id).where(User.email == email))).scalar_one_or_none()
            action = "existing_user" if exists is not None else "create"
        plans.append(
            GuardianAccountPlan(
                person_id=str(person.id),
                name=full_name(person),
                email=email,
                action=action,  # type: ignore[arg-type]
            )
        )
    return plans


async def preview_conversion(
    session: AsyncSession,
    application_id: uuid.UUID,
) -> ConversionPreview:
    row = await live_application(session, application_id)
    settings = await load_settings(session)
    can_convert = row.status == "accepted" and row.student_id is None
    if row.student_id is not None:
        reason = "already_converted"
    elif not can_convert:
        reason = f"status_{row.status}"
    else:
        reason = None
    student_number = None
    if can_convert:
        preview = await student_numbering.peek_number(session, year_id=row.year_id)
        student_number = preview.student_number
    year, level, section, source, warnings = await _placement(session, row, settings)
    accounts = await _account_plan(session, row.id, settings)
    return ConversionPreview(
        can_convert=can_convert,
        reason=reason,
        student_number=student_number,
        year_code=year.code,
        level_code=level.code,
        section_code=section.code if section else None,
        section_source=source,  # type: ignore[arg-type]
        guardian_count=len(await _guardians(session, row.id)),
        accounts=accounts,
        warnings=warnings,
    )


async def _default_locale(session: AsyncSession) -> str:
    try:
        settings = await load_model(session, "core", CoreSettings)
    except Exception:  # pragma: no cover - settings always exist after setup
        return "en"
    return settings.school_profile.default_language


async def _create_guardian_account(
    session: AsyncSession,
    principal: Principal,
    guardian: AdmissionGuardian,
    person: Person,
    settings: AdmissionSettings,
    *,
    request: Request | None,
    app_settings: Settings | None,
    via: str,
) -> tuple[str, str | None, str | None]:
    """Return ``(action, user_id, warning)`` for one guardian account."""
    email = (person.email or "").strip().lower()
    if not email:
        return "no_email", None, "guardian_email_missing"
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        guardian.account_user_id = existing.id
        await session.flush()
        return "existing_user", str(existing.id), "existing_guardian_account"
    role = (
        await session.execute(
            select(Role).where(
                Role.key == settings.form.guardian_role_key,
                Role.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if role is None:
        return "role_missing", None, "guardian_role_missing"
    phone = person.phone
    if phone:
        taken = (await session.execute(select(User.id).where(User.phone == phone))).scalar_one_or_none()
        if taken is not None:
            phone = None
    user = User(
        email=email,
        phone=phone,
        display_name=full_name(person),
        password_hash=hash_password(secrets.token_urlsafe(32)),
        locale=await _default_locale(session),
        is_active=True,
        must_change_password=True,
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    guardian.account_user_id = user.id
    await session.flush()
    warning = None
    if request is not None and app_settings is not None:
        try:
            await send_reset_link(
                session,
                app_settings,
                user,
                request,
                subject="Your school guardian account",
                intro=(
                    "An account has been created so you can follow your child's "
                    "school information. Choose your password with the link below."
                ),
            )
        except Exception as exc:  # pragma: no cover - mail outages are operational
            logger.warning("guardian invitation failed: %s", exc)
            warning = "guardian_invitation_failed"
    await record(
        session,
        action="admissions.guardian_account.create",
        module=MODULE,
        entity_type="user",
        entity_id=str(user.id),
        after={"email": user.email, "person_id": str(person.id), "role": role.key},
        actor=principal,
        via=via,
    )
    return "create", str(user.id), warning


async def convert_application(
    session: AsyncSession,
    principal: Principal,
    application_id: uuid.UUID,
    data: ConversionInput,
    *,
    request: Request | None = None,
    app_settings: Settings | None = None,
    via: str = "api",
) -> ConversionOut:
    row = await live_application(session, application_id)
    ensure_row_version(row, data.row_version, current_state=application_state(row))
    if row.student_id is not None:
        raise Conflict(
            "This application has already been converted",
            message_key="admissions.error.already_converted",
            details={"student_id": str(row.student_id)},
        )
    if row.status != "accepted":
        raise Conflict(
            "Accept the application before converting it",
            message_key="admissions.error.accept_first",
            details={"status": row.status},
        )
    person = await _person(session, row.person_id)
    settings = await load_settings(session)
    _year, _level, section, _source, warnings = await _placement(session, row, settings)

    profile = await student_service.create_profile_for_person(
        session,
        principal,
        person.id,
        admission_date=data.admission_date,
        via=via,
    )
    enrollment = await enrollment_service.create_enrollment(
        session,
        principal,
        profile.id,
        EnrollmentInput(
            year_id=row.year_id,
            level_id=row.level_id,
            section_id=uuid.UUID(section.id) if section is not None else None,
            roll_number=data.roll_number,
            status="active",
        ),
        via=via,
    )

    guardian_ids: list[str] = []
    accounts: list[GuardianAccountPlan] = []
    accounts_enabled = (
        data.create_guardian_accounts
        if data.create_guardian_accounts is not None
        else settings.form.guardian_accounts_on_conversion
    )
    for guardian in await _guardians(session, row.id):
        link = await guardian_service.add_guardian(
            session,
            principal,
            profile.id,
            GuardianInput(
                person_id=guardian.person_id,
                relationship=guardian.relationship,
                is_primary=guardian.is_primary,
                can_pickup=guardian.can_pickup,
                notes=guardian.notes,
            ),
            via=via,
        )
        guardian_ids.append(str(link.id))
        if not accounts_enabled or not guardian.wants_account:
            continue
        guardian_person = await _person(session, guardian.person_id)
        action, _user_id, warning = await _create_guardian_account(
            session,
            principal,
            guardian,
            guardian_person,
            settings,
            request=request,
            app_settings=app_settings,
            via=via,
        )
        if warning and warning not in warnings:
            warnings.append(warning)
        accounts.append(
            GuardianAccountPlan(
                person_id=str(guardian_person.id),
                name=full_name(guardian_person),
                email=(guardian_person.email or "").strip().lower() or None,
                action=action,  # type: ignore[arg-type]
            )
        )

    row.student_id = profile.id
    row.section_id = enrollment.section_id
    row.status = "enrolled"
    row.converted_at = datetime.now(UTC)
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="admissions.convert",
        module=MODULE,
        entity_type=ENTITY,
        entity_id=str(row.id),
        before={"status": "accepted"},
        after={
            **application_state(row),
            "student_number": profile.student_number,
            "enrollment_id": str(enrollment.id),
            "guardian_ids": guardian_ids,
        },
        actor=principal,
        via=via,
    )
    await emit(
        session,
        "admission.converted",
        {
            "application_id": str(row.id),
            "student_id": str(profile.id),
            "student_number": profile.student_number,
            "year_id": str(row.year_id),
            "level_id": str(row.level_id),
            "section_id": str(enrollment.section_id) if enrollment.section_id else None,
        },
        actor_id=principal.actor_id,
    )
    await session.commit()

    school_name = (await load_model(session, "core", CoreSettings)).school_profile.name
    for account in accounts:
        if account.action != "create" or account.email is None:
            continue
        user = (await session.execute(select(User).where(User.email == account.email))).scalar_one_or_none()
        if user is None:  # pragma: no cover - created above
            continue
        try:
            await send_notification(
                session,
                user_id=user.id,
                template_key="account.welcome",
                params={"name": user.display_name, "school": school_name},
                actor=principal,
                module=MODULE,
            )
        except Exception as exc:  # pragma: no cover - template/mail outages are operational
            logger.warning("guardian welcome notification failed: %s", exc)

    return ConversionOut(
        application=await application_view(session, row, locale=principal.locale),
        student_id=str(profile.id),
        student_number=profile.student_number,
        enrollment_id=str(enrollment.id),
        guardian_ids=guardian_ids,
        accounts=accounts,
        warnings=warnings,
    )


async def delete_application(
    session: AsyncSession,
    principal: Principal,
    application_id: uuid.UUID,
    *,
    row_version: int | None = None,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await live_application(session, application_id)
    if row_version is not None:
        ensure_row_version(row, row_version, current_state=application_state(row))
    if row.student_id is not None:
        raise Conflict(
            "A converted application cannot be deleted",
            message_key="admissions.error.converted_delete",
            details={"student_id": str(row.student_id)},
        )
    await soft_delete(
        session,
        row,
        action="admissions.application.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type=ENTITY,
    )
    await session.commit()
    return {"id": str(row.id), "deleted": True}


async def restore_application(
    session: AsyncSession,
    principal: Principal,
    application_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> ApplicationOut:
    row = await get_including_deleted(session, AdmissionApplication, application_id)
    if row is None:
        raise NotFound(
            "The application does not exist",
            message_key="admissions.error.not_found",
        )
    await restore(
        session,
        row,
        action="admissions.application.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type=ENTITY,
    )
    await session.commit()
    return await application_view(session, row, locale=principal.locale)


async def form_view(session: AsyncSession, principal: Principal) -> AdmissionFormOut:
    settings = await load_settings(session)
    definitions = await definitions_for(session, ENTITY, principal=principal)
    return AdmissionFormOut(
        fields=[definition_view(item) for item in definitions],
        entrance_test_enabled=settings.entrance_test.enabled,
        entrance_test_max_score=settings.entrance_test.max_score,
        entrance_test_pass_score=settings.entrance_test.pass_score,
        require_guardian=settings.form.require_guardian,
        public_form_enabled=settings.form.public_enabled,
    )


__all__ = [
    "application_state",
    "application_view",
    "convert_application",
    "create_application",
    "decide_application",
    "delete_application",
    "form_view",
    "get_application",
    "list_applications",
    "live_application",
    "load_settings",
    "preview_application",
    "preview_conversion",
    "restore_application",
    "update_application",
]
