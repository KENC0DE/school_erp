"""Single and bulk document generation (P5-08).

The API only authorises a batch; the worker does the expensive work. This module
holds the orchestration so both the HTTP route and the Celery task call the same
code:

* a target is resolved to a list of students once, at request time, so an empty
  section is rejected before a job is queued;
* each issued document copies the template version's layout and the data it was
  rendered from, so a reprint never reads today's student record;
* numbers are allocated atomically and each document gets its own unguessable
  verification code for the public page;
* separate files are the default; a combined PDF is assembled with pypdf and
  stored on the batch. Both keep every document individually downloadable.

Generation runs as a system actor. The route already checked
``documents.generate``; the batch records the requester as issuer and as audit
actor, but the data reads are not narrowed a second time by that user's scopes.
See docs/DECISIONS.md for why.
"""

from __future__ import annotations

import io
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from app.settings import Settings
from core.audit.service import record
from core.auth.principal import Principal
from core.documents.binding import resolve_path
from core.documents.layout import ImageElement, Layout
from core.documents.render import RenderAsset, RenderContext, render_layout
from core.events.models import Job
from core.events.service import create_job
from core.files.models import StoredFile
from core.files.service import upload_file
from core.files.storage import Storage
from core.people.models import Person, full_name, normalize_name
from core.settings.service import load_model
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.academics import years as year_service
from modules.academics.models import AcademicYear, GradeLevel, Section
from modules.documents.models import (
    DocTemplate,
    DocTemplateVersion,
    DocumentBatch,
    IssuedDocument,
)
from modules.documents.numbering import allocate_number, new_verification_code
from modules.documents.preview import common_context, staff_context, student_context
from modules.documents.schemas import (
    DocumentGenerationRequest,
    GenerationLevelOut,
    GenerationSectionOut,
    GenerationStaffList,
    GenerationStaffOut,
    GenerationStudentList,
    GenerationStudentOut,
    GenerationTarget,
    GenerationTargetsOut,
    GenerationYearOut,
)
from modules.documents.service import parse_layout
from modules.documents.settings import DocumentSettings
from modules.staff.models import StaffDepartment, StaffPosition, StaffProfile
from modules.students.lookups import AcademicLabels
from modules.students.models import StudentEnrollment, StudentProfile

logger = logging.getLogger("erp.documents")

MODULE = "documents"
PLACED_STATUSES = ("active", "promoted", "repeating")
# A certificate is a claim the school makes, so a school may ask for a second
# pair of eyes before one is numbered. Report cards, receipts and ID cards are
# operational paperwork and are never held by this switch.
APPROVAL_DOC_TYPES = ("certificate_completion", "certificate_appreciation")
ProgressCallback = Callable[[int, int], Awaitable[None]]


@dataclass(frozen=True)
class Target:
    """One document to issue, resolved before the job starts."""

    recipient_type: str
    recipient_id: uuid.UUID
    year_id: uuid.UUID | None


def _year_of(value: date) -> int:
    return value.year


async def _current_year(session: AsyncSession) -> AcademicYear | None:
    years = await year_service.list_years(session)
    if years.current_year_id:
        return await session.get(AcademicYear, uuid.UUID(years.current_year_id))
    if not years.items:
        return None
    return await session.get(AcademicYear, uuid.UUID(years.items[0].id))


async def _student_year(session: AsyncSession, student_id: uuid.UUID) -> uuid.UUID | None:
    row = (
        await session.execute(
            select(StudentEnrollment)
            .where(
                StudentEnrollment.student_id == student_id,
                StudentEnrollment.deleted_at.is_(None),
            )
            .order_by(StudentEnrollment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row.year_id if row is not None else None


async def resolve_targets(
    session: AsyncSession,
    target: GenerationTarget,
) -> list[Target]:
    """Turn a requested target into the students a batch will print."""
    if target.type == "student":
        assert target.student_id is not None  # guarded by the request schema
        student = (
            await session.execute(
                select(StudentProfile).where(
                    StudentProfile.id == target.student_id,
                    StudentProfile.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if student is None:
            raise NotFound(
                "The student does not exist",
                message_key="students.error.not_found",
            )
        year_id = target.year_id or await _student_year(session, student.id)
        return [Target("student", student.id, year_id)]

    if target.type == "staff":
        assert target.staff_id is not None  # guarded by the request schema
        staff = (
            await session.execute(
                select(StaffProfile).where(
                    StaffProfile.id == target.staff_id,
                    StaffProfile.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if staff is None:
            raise NotFound("The staff member does not exist", message_key="staff.error.not_found")
        return [Target("staff", staff.id, None)]

    if target.type == "section":
        assert target.section_id is not None
        section = (
            await session.execute(
                select(Section).where(
                    Section.id == target.section_id,
                    Section.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if section is None:
            raise NotFound("The section does not exist", message_key="academics.error.section_not_found")
        if target.year_id is not None and target.year_id != section.year_id:
            raise ValidationFailed(
                "The section does not belong to that academic year",
                message_key="error.documents.target_mismatch",
            )
        return await _enrollment_targets(session, section.year_id, section_id=section.id)

    assert target.level_id is not None
    level = (
        await session.execute(
            select(GradeLevel).where(
                GradeLevel.id == target.level_id,
                GradeLevel.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if level is None:
        raise NotFound("The grade level does not exist", message_key="academics.error.level_not_found")
    year = (
        await _current_year(session)
        if target.year_id is None
        else await session.get(AcademicYear, target.year_id)
    )
    if year is None:
        raise ValidationFailed(
            "A grade batch needs an academic year",
            message_key="error.documents.year_required",
        )
    return await _enrollment_targets(session, year.id, level_id=level.id)


async def _enrollment_targets(
    session: AsyncSession,
    year_id: uuid.UUID,
    *,
    section_id: uuid.UUID | None = None,
    level_id: uuid.UUID | None = None,
) -> list[Target]:
    stmt = (
        select(StudentEnrollment.student_id)
        .join(StudentProfile, StudentProfile.id == StudentEnrollment.student_id)
        .where(
            StudentEnrollment.year_id == year_id,
            StudentEnrollment.deleted_at.is_(None),
            StudentEnrollment.status.in_(PLACED_STATUSES),
            StudentProfile.deleted_at.is_(None),
        )
        .order_by(StudentEnrollment.roll_number, StudentProfile.student_number)
    )
    if section_id is not None:
        stmt = stmt.where(StudentEnrollment.section_id == section_id)
    if level_id is not None:
        stmt = stmt.where(StudentEnrollment.level_id == level_id)
    ids = list((await session.execute(stmt)).scalars().all())
    return [Target("student", student_id, year_id) for student_id in dict.fromkeys(ids)]


async def _published_version(
    session: AsyncSession,
    template: DocTemplate,
    version_id: uuid.UUID | None,
) -> DocTemplateVersion:
    stmt = select(DocTemplateVersion).where(
        DocTemplateVersion.template_id == template.id,
        DocTemplateVersion.deleted_at.is_(None),
        DocTemplateVersion.status == "published",
    )
    if version_id is not None:
        stmt = stmt.where(DocTemplateVersion.id == version_id)
    else:
        stmt = stmt.order_by(DocTemplateVersion.version_number.desc()).limit(1)
    version = (await session.execute(stmt)).scalar_one_or_none()
    if version is None:
        raise ValidationFailed(
            "Generate from a published version; publish the draft first",
            message_key="error.documents.version_not_published",
            details={"template_id": str(template.id)},
        )
    return version


async def approval_required(
    session: AsyncSession,
    template: DocTemplate,
) -> bool:
    """Whether this template's documents must wait for ``documents.approve``."""
    if template.doc_type not in APPROVAL_DOC_TYPES:
        return False
    settings = await load_model(session, MODULE, DocumentSettings)
    return bool(settings.require_certificate_approval)


async def create_batch(
    session: AsyncSession,
    principal: Principal,
    payload: DocumentGenerationRequest,
) -> tuple[DocumentBatch, Job]:
    """Validate a request, snapshot its target list and queue the work."""
    template = (
        await session.execute(
            select(DocTemplate).where(
                DocTemplate.id == payload.template_id,
                DocTemplate.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if template is None:
        raise NotFound("The template does not exist", message_key="error.documents.template_not_found")

    version = await _published_version(session, template, payload.version_id)
    targets = await resolve_targets(session, payload.target)
    if not targets:
        raise ValidationFailed(
            "There is nobody in that target to generate for",
            message_key="error.documents.target_empty",
        )
    year_id = payload.target.year_id or targets[0].year_id
    needs_approval = await approval_required(session, template)

    batch = DocumentBatch(
        template_id=template.id,
        template_version_id=version.id,
        mode=payload.target.type,
        year_id=year_id,
        level_id=payload.target.level_id,
        section_id=payload.target.section_id,
        student_id=payload.target.student_id,
        staff_id=payload.target.staff_id,
        combine=payload.combine,
        count=len(targets),
        approval_required=needs_approval,
        status="pending_approval" if needs_approval else "queued",
        context={
            "actor_id": principal.actor_id,
            "display_name": principal.display_name,
            "locale": principal.locale,
            "roles": list(principal.roles),
            "version_number": version.version_number,
        },
        created_by=_actor(principal),
        updated_by=_actor(principal),
    )
    session.add(batch)
    await session.flush()

    job = await create_job(
        session,
        "documents.generate",
        {"batch_id": str(batch.id), "approval_required": needs_approval},
        created_by=principal.actor_id,
    )
    batch.job_id = job.id
    await record(
        session,
        action="documents.batch.create",
        module=MODULE,
        entity_type="doc_generation_batch",
        entity_id=str(batch.id),
        after={
            "template_id": str(template.id),
            "version": version.version_number,
            "mode": payload.target.type,
            "combine": payload.combine,
            "count": len(targets),
            "approval_required": needs_approval,
        },
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    await session.refresh(batch)
    return batch, job


def _actor(principal: Principal) -> uuid.UUID | None:
    try:
        return uuid.UUID(principal.actor_id)
    except (TypeError, ValueError):
        return None


async def _batch_for_decision(
    session: AsyncSession,
    batch_id: uuid.UUID,
) -> DocumentBatch:
    """Load a batch under a row lock so two approvers cannot race."""
    row = (
        await session.execute(
            select(DocumentBatch)
            .where(
                DocumentBatch.id == batch_id,
                DocumentBatch.deleted_at.is_(None),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The generation batch does not exist",
            message_key="error.documents.batch_not_found",
        )
    return row


def _ensure_pending(row: DocumentBatch) -> None:
    if row.status != "pending_approval":
        raise Conflict(
            "This batch is not waiting for approval",
            message_key="error.documents.batch_not_pending",
            details={"status": row.status},
        )


async def approve_batch(
    session: AsyncSession,
    principal: Principal,
    batch_id: uuid.UUID,
    *,
    note: str | None = None,
) -> tuple[DocumentBatch, Job | None]:
    """Release a held certificate batch to the worker."""
    row = await _batch_for_decision(session, batch_id)
    _ensure_pending(row)
    now = datetime.now(UTC)
    row.status = "queued"
    row.approved_by = _actor(principal)
    row.approved_at = now
    row.rejection_reason = None
    row.updated_by = _actor(principal)
    job = await session.get(Job, row.job_id) if row.job_id else None
    if job is not None:
        job.status = "queued"
        job.progress = 0
        job.started_at = None
        job.finished_at = None
        job.result = None
        job.error = None
    await record(
        session,
        action="documents.batch.approve",
        module=MODULE,
        entity_type="doc_generation_batch",
        entity_id=str(row.id),
        after={
            "template_id": str(row.template_id),
            "count": row.count,
            "note": note,
            "approved_at": now.isoformat(),
        },
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    await session.refresh(row)
    return row, job


async def reject_batch(
    session: AsyncSession,
    principal: Principal,
    batch_id: uuid.UUID,
    *,
    reason: str,
) -> DocumentBatch:
    """Stop a held certificate batch; nothing is numbered or printed."""
    row = await _batch_for_decision(session, batch_id)
    _ensure_pending(row)
    now = datetime.now(UTC)
    row.status = "rejected"
    row.rejection_reason = reason
    row.approved_by = None
    row.approved_at = None
    row.updated_by = _actor(principal)
    job = await session.get(Job, row.job_id) if row.job_id else None
    if job is not None:
        job.status = "cancelled"
        job.finished_at = now
        job.error = reason
    await record(
        session,
        action="documents.batch.reject",
        module=MODULE,
        entity_type="doc_generation_batch",
        entity_id=str(row.id),
        after={
            "template_id": str(row.template_id),
            "count": row.count,
            "reason": reason,
        },
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    await session.refresh(row)
    return row


def system_principal(batch: DocumentBatch) -> Principal:
    """The trusted worker identity, carrying the requester's actor and locale."""
    context = batch.context or {}
    return Principal(
        actor_id=str(context.get("actor_id") or ""),
        actor_type="user",
        via="automation",
        display_name=str(context.get("display_name") or ""),
        locale=str(context.get("locale") or "en"),
        permissions={"*"},
    )


async def _image_assets(
    session: AsyncSession,
    storage: Storage,
    layout: Layout,
    data: dict[str, Any],
) -> dict[str, RenderAsset]:
    """Resolve file-backed images into bytes the renderer can inline.

    Only image elements participate. A field value that is an uploaded file id
    is loaded; a URL or a data URI is left to the browser. Missing files render
    nothing rather than failing the whole batch.
    """
    assets: dict[str, RenderAsset] = {}
    for element in layout.elements:
        if not isinstance(element, ImageElement):
            continue
        if element.source.kind == "file":
            file_id = element.source.value
        elif element.source.kind == "field":
            value = resolve_path(data, element.source.value)
            file_id = value if isinstance(value, str) else None
        else:
            continue
        if not file_id:
            continue
        try:
            identifier = uuid.UUID(file_id)
        except ValueError:
            continue
        if file_id in assets:
            continue
        row = (
            await session.execute(
                select(StoredFile).where(
                    StoredFile.id == identifier,
                    StoredFile.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            continue
        content = await storage.get(row.object_key)
        assets[file_id] = RenderAsset(content, row.original_name, row.mime)
    return assets


def _number_year(today: date) -> int:
    """Numbering restarts each Gregorian January, independent of the school year."""
    return _year_of(today)


async def _issue_one(
    session: AsyncSession,
    *,
    batch: DocumentBatch,
    template: DocTemplate,
    version: DocTemplateVersion,
    layout: Layout,
    target: Target,
    principal: Principal,
    storage: Storage,
    settings: Settings,
) -> tuple[IssuedDocument, bytes, str]:
    """Render, number, store and audit one document. Commits on success."""
    if target.recipient_type == "staff":
        data, recipient_name = await staff_context(session, principal, target.recipient_id)
    else:
        data, recipient_name = await student_context(session, principal, target.recipient_id)
    data = {**data, **await common_context(session)}
    data["person"] = {"full_name": recipient_name}
    if "school" in data:
        data["school"].setdefault("short_name", data["school"].get("name"))
    year_number = _number_year(date.today())
    number = await allocate_number(session, year=year_number)
    code = await new_verification_code(session)
    verify_url = f"{settings.web_base_url.rstrip('/')}/verify/{code}"
    data["document"] = {
        "number": number,
        "verification_code": code,
        "verify_url": verify_url,
    }

    assets = await _image_assets(session, storage, layout, data)
    rendered = render_layout(layout, RenderContext(data=data, assets=assets, locale=principal.locale))
    if not rendered.pdf.startswith(b"%PDF"):
        raise ValidationFailed(
            "The renderer did not produce a PDF",
            message_key="error.documents.render_failed",
        )

    issued_at = datetime.now(UTC)
    issued = IssuedDocument(
        template_id=template.id,
        template_version_id=version.id,
        template_version_number=version.version_number,
        doc_type=template.doc_type,
        layout=version.layout,
        data_snapshot=data,
        number=number,
        verification_code=code,
        issuer_id=_actor(principal),
        issued_at=issued_at,
        batch_id=batch.id,
        recipient_type=target.recipient_type,
        recipient_id=target.recipient_id,
        recipient_name=recipient_name,
        created_by=_actor(principal),
        updated_by=_actor(principal),
    )
    session.add(issued)
    await session.flush()

    stored = await upload_file(
        session,
        principal,
        storage,
        settings,
        filename=f"{number}.pdf",
        content_type="application/pdf",
        data=rendered.pdf,
        owner_entity_type="document",
        owner_entity_id=str(issued.id),
        is_private=True,
        commit=False,
        thumbnail=False,
    )
    issued.file_id = uuid.UUID(str(stored["id"]))
    await record(
        session,
        action="documents.issue",
        module=MODULE,
        entity_type="issued_document",
        entity_id=str(issued.id),
        after={
            "number": number,
            "template_id": str(template.id),
            "version": version.version_number,
            "recipient_type": target.recipient_type,
            "recipient_id": str(target.recipient_id),
            "batch_id": str(batch.id),
        },
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    return issued, rendered.pdf, number


async def generate_batch(
    session: AsyncSession,
    *,
    batch_id: uuid.UUID,
    principal: Principal,
    storage: Storage,
    settings: Settings,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Issue every document in a batch, committing one document at a time."""
    batch = await session.get(DocumentBatch, batch_id)
    if batch is None:
        raise NotFound("The generation batch does not exist", message_key="error.documents.batch_not_found")
    if batch.status == "pending_approval":
        raise Conflict(
            "This batch is waiting for approval before anything is printed",
            message_key="error.documents.batch_pending_approval",
        )
    if batch.status == "rejected":
        raise Conflict(
            "This batch was rejected and cannot be generated",
            message_key="error.documents.batch_rejected",
        )
    if batch.status in {"succeeded", "cancelled"}:
        return _batch_result(batch)

    template = await session.get(DocTemplate, batch.template_id)
    version = await session.get(DocTemplateVersion, batch.template_version_id)
    if template is None or version is None:
        raise NotFound(
            "The template version no longer exists", message_key="error.documents.template_not_found"
        )
    layout = parse_layout(version.layout)

    batch.status = "running"
    batch.progress = 5
    batch.failure_summary = None
    await session.commit()

    targets = await _batch_targets(session, batch)
    total = len(targets)
    batch.count = total
    await session.commit()

    writer = _PdfWriter() if batch.combine else None
    failures = 0
    for index, target in enumerate(targets, start=1):
        try:
            issued, pdf, _number = await _issue_one(
                session,
                batch=batch,
                template=template,
                version=version,
                layout=layout,
                target=target,
                principal=principal,
                storage=storage,
                settings=settings,
            )
            if writer is not None:
                writer.add(pdf)
            batch.issued_count += 1
            batch.progress = int(95 * index / total) if total else 95
            if on_progress is not None:
                await on_progress(index, total)
            await session.commit()
        except Exception as exc:  # one bad record must not lose the rest of a bulk run
            logger.warning("document generation failed for %s: %s", target.recipient_id, exc)
            failures += 1
            batch.failed_count += 1
            await session.rollback()
            batch = await session.get(DocumentBatch, batch_id)
            if batch is None:  # pragma: no cover - the row cannot vanish mid-run
                raise
            batch.failed_count = failures
            batch.progress = int(95 * index / total) if total else 95
            if on_progress is not None:
                await on_progress(index, total)
            await session.commit()

    if writer is not None and writer.count:
        combined = writer.finish()
        stored = await upload_file(
            session,
            principal,
            storage,
            settings,
            filename=f"batch-{batch.id}.pdf",
            content_type="application/pdf",
            data=combined,
            owner_entity_type="document_batch",
            owner_entity_id=str(batch.id),
            is_private=True,
            commit=False,
            thumbnail=False,
        )
        batch.file_id = uuid.UUID(str(stored["id"]))

    batch.progress = 100
    batch.issued_at = datetime.now(UTC)
    batch.status = "succeeded" if batch.issued_count else "failed"
    if failures:
        batch.failure_summary = f"{failures} document(s) could not be generated"
    await record(
        session,
        action="documents.batch.complete",
        module=MODULE,
        entity_type="doc_generation_batch",
        entity_id=str(batch.id),
        after={
            "issued": batch.issued_count,
            "failed": batch.failed_count,
            "status": batch.status,
        },
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    if batch.status == "failed":
        raise RuntimeError("No document could be generated; see the job log")
    return _batch_result(batch)


async def _batch_targets(session: AsyncSession, batch: DocumentBatch) -> list[Target]:
    if batch.mode == "student":
        return [
            Target("student", batch.student_id, batch.year_id)
            for batch.student_id in ([batch.student_id] if batch.student_id else [])
        ]
    if batch.mode == "staff":
        return [
            Target("staff", batch.staff_id, None)
            for batch.staff_id in ([batch.staff_id] if batch.staff_id else [])
        ]
    return await _enrollment_targets(
        session,
        batch.year_id,
        section_id=batch.section_id,
        level_id=batch.level_id,
    )


async def generation_targets(session: AsyncSession) -> GenerationTargetsOut:
    """The current year's levels and sections, for the generation dialog."""
    years = await year_service.list_years(session)
    current_id = years.current_year_id
    year = await session.get(AcademicYear, uuid.UUID(current_id)) if current_id else None
    levels = list(
        (
            await session.execute(
                select(GradeLevel)
                .where(
                    GradeLevel.deleted_at.is_(None),
                    GradeLevel.is_active.is_(True),
                )
                .order_by(GradeLevel.sort_order, GradeLevel.code)
            )
        )
        .scalars()
        .all()
    )
    sections: list[Section] = []
    if year is not None:
        sections = list(
            (
                await session.execute(
                    select(Section)
                    .where(
                        Section.year_id == year.id,
                        Section.deleted_at.is_(None),
                        Section.is_active.is_(True),
                    )
                    .order_by(Section.level_id, Section.code)
                )
            )
            .scalars()
            .all()
        )
    return GenerationTargetsOut(
        year=GenerationYearOut(
            id=str(year.id),
            code=year.code,
            name=year.name,
            is_current=True,
        )
        if year is not None
        else None,
        levels=[
            GenerationLevelOut(
                id=str(level.id),
                code=level.code,
                name=level.name,
                name_am=level.name_am,
            )
            for level in levels
        ],
        sections=[
            GenerationSectionOut(
                id=str(section.id),
                year_id=str(section.year_id),
                level_id=str(section.level_id),
                code=section.code,
                name=section.name,
            )
            for section in sections
        ],
    )


async def search_generation_students(
    session: AsyncSession,
    *,
    q: str | None,
    limit: int,
    locale: str,
) -> GenerationStudentList:
    """A lightweight student picker for single-document generation."""
    year = await _current_year(session)
    join = [
        StudentEnrollment.student_id == StudentProfile.id,
        StudentEnrollment.deleted_at.is_(None),
    ]
    if year is not None:
        join.append(StudentEnrollment.year_id == year.id)
    stmt = (
        select(StudentProfile, Person, StudentEnrollment)
        .join(Person, Person.id == StudentProfile.person_id)
        .join(StudentEnrollment, and_(*join), isouter=True)
        .where(
            StudentProfile.deleted_at.is_(None),
            Person.deleted_at.is_(None),
        )
        .order_by(StudentProfile.student_number)
    )
    if q and q.strip():
        terms = normalize_name(q).split()
        matches = [StudentProfile.student_number.ilike(f"%{q.strip()}%")]
        if terms:
            matches.append(and_(*[Person.search_name.like(f"%{term}%") for term in terms]))
        stmt = stmt.where(or_(*matches))
    rows = (await session.execute(stmt.limit(max(1, min(limit, 50))))).all()
    labels = AcademicLabels(session)
    seen: set[uuid.UUID] = set()
    items: list[GenerationStudentOut] = []
    for profile, person, enrollment in rows:
        if profile.id in seen:
            continue
        seen.add(profile.id)
        level_name = None
        section_code = None
        if enrollment is not None:
            level = await labels.level(enrollment.level_id)
            section = await labels.section(enrollment.section_id) if enrollment.section_id else None
            level_name = level.name if level else None
            section_code = section.code if section else None
        items.append(
            GenerationStudentOut(
                id=str(profile.id),
                student_number=profile.student_number,
                full_name=full_name(person, locale),
                level_name=level_name,
                section_code=section_code,
            )
        )
    return GenerationStudentList(items=items)


def _localized(english: str, amharic: str | None, locale: str) -> str:
    return amharic if locale == "am" and amharic else english


async def search_generation_staff(
    session: AsyncSession,
    *,
    q: str | None,
    limit: int,
    locale: str,
) -> GenerationStaffList:
    """A lightweight staff picker for experience letters and staff certificates."""
    stmt = (
        select(StaffProfile, Person)
        .join(Person, Person.id == StaffProfile.person_id)
        .where(
            StaffProfile.deleted_at.is_(None),
            Person.deleted_at.is_(None),
        )
        .order_by(StaffProfile.staff_number)
    )
    if q and q.strip():
        terms = normalize_name(q).split()
        matches = [StaffProfile.staff_number.ilike(f"%{q.strip()}%")]
        if terms:
            matches.append(and_(*[Person.search_name.like(f"%{term}%") for term in terms]))
        stmt = stmt.where(or_(*matches))
    rows = (await session.execute(stmt.limit(max(1, min(limit, 50))))).all()
    items: list[GenerationStaffOut] = []
    for profile, person in rows:
        position_name = None
        department_name = None
        if profile.position_id is not None:
            position = await session.get(StaffPosition, profile.position_id)
            if position is not None:
                position_name = _localized(position.name, position.name_am, locale)
        if profile.department_id is not None:
            department = await session.get(StaffDepartment, profile.department_id)
            if department is not None:
                department_name = _localized(department.name, department.name_am, locale)
        items.append(
            GenerationStaffOut(
                id=str(profile.id),
                staff_number=profile.staff_number,
                full_name=full_name(person, locale),
                position_name=position_name,
                department_name=department_name,
            )
        )
    return GenerationStaffList(items=items)


def _batch_result(batch: DocumentBatch) -> dict[str, Any]:
    return {
        "batch_id": str(batch.id),
        "status": batch.status,
        "issued": batch.issued_count,
        "failed": batch.failed_count,
        "count": batch.count,
        "file_id": str(batch.file_id) if batch.file_id else None,
    }


class _PdfWriter:
    """Tiny wrapper around pypdf so an unreadable PDF names the failure."""

    def __init__(self) -> None:
        from pypdf import PdfWriter

        self._writer = PdfWriter()

    @property
    def count(self) -> int:
        return len(self._writer.pages)

    def add(self, pdf: bytes) -> None:
        from pypdf import PdfReader

        for page in PdfReader(io.BytesIO(pdf)).pages:
            self._writer.add_page(page)

    def finish(self) -> bytes:
        buffer = io.BytesIO()
        self._writer.write(buffer)
        return buffer.getvalue()


__all__ = [
    "APPROVAL_DOC_TYPES",
    "PLACED_STATUSES",
    "Target",
    "approval_required",
    "approve_batch",
    "create_batch",
    "generate_batch",
    "generation_targets",
    "reject_batch",
    "resolve_targets",
    "search_generation_staff",
    "search_generation_students",
    "system_principal",
]
