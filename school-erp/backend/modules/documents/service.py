"""Document template lifecycle (P5-04).

A template is the stable identity a school generates documents from; its layout
lives in a numbered version. The rules that make generation reproducible are all
here:

* one draft per template, enforced by a partial unique index as well as by this
  service, so two editors cannot fork a design;
* a published version is immutable — only drafts can be saved, and publishing
  never rewrites the layout;
* deleting a template soft-deletes its versions too, so nothing is ever removed
  from history;
* every mutation writes an audit entry. Layouts are summarised by digest and
  element count rather than copied into the audit log, which keeps the chain
  readable while still proving what changed.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import apply_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.db.base import uuid7
from core.db.soft_delete import actor_uuid, mark_deleted, soft_delete
from core.documents.layout import Layout, validate_layout
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.documents.models import DOC_TYPES, DocTemplate, DocTemplateVersion
from modules.documents.schemas import (
    TemplateCreate,
    TemplateDetail,
    TemplateDuplicate,
    TemplateFile,
    TemplateFileVersion,
    TemplateSummary,
    TemplateUpdate,
    VersionCreate,
    VersionDetail,
    VersionSave,
    VersionSummary,
)
from modules.documents.starters import STARTERS_BY_KEY

MODULE = "documents"
TEMPLATE = "doc_template"
VERSION = "doc_template_version"
DRAFT_EXISTS = "error.documents.draft_exists"
TEMPLATE_NOT_FOUND = "error.documents.template_not_found"
VERSION_NOT_FOUND = "error.documents.version_not_found"


# --- small helpers ----------------------------------------------------------


def _digest(layout: dict[str, Any]) -> str:
    canonical = json.dumps(layout, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _layout_json(layout: Layout) -> dict[str, Any]:
    """The canonical stored form: defaults filled, absent optionals omitted."""
    return layout.model_dump(mode="json", exclude_none=True)


def parse_layout(value: Any) -> Layout:
    """Validate a layout payload, reporting schema errors as a 422."""
    try:
        return validate_layout(value)
    except ValidationError as error:
        raise ValidationFailed(
            "The layout does not match the document schema",
            message_key="error.documents.layout_invalid",
            details={
                "errors": [{"path": list(item["loc"]), "message": item["msg"]} for item in error.errors()]
            },
        ) from error


def _validated_layout(value: Any) -> dict[str, Any]:
    return _layout_json(parse_layout(value))


def _blank_layout() -> dict[str, Any]:
    return _layout_json(validate_layout({"version": 1, "page": {"size": "A4"}}))


def _new_key(doc_type: str) -> str:
    # UUIDv7's leading bits are a millisecond timestamp, so two keys created in
    # the same tick would share any prefix. The trailing 48 random bits are the
    # part that actually identifies the row.
    return f"{doc_type.replace('_', '-')}-{uuid7().hex[-12:]}"


def _template_state(row: DocTemplate) -> dict[str, Any]:
    return {
        "key": row.key,
        "name": row.name,
        "description": row.description,
        "doc_type": row.doc_type,
        "row_version": row.row_version,
    }


def _version_state(row: DocTemplateVersion) -> dict[str, Any]:
    layout = row.layout or {}
    elements = layout.get("elements") or []
    return {
        "version_number": row.version_number,
        "status": row.status,
        "change_note": row.change_note,
        "layout_digest": _digest(layout),
        "elements": len(elements),
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "row_version": row.row_version,
    }


def _version_summary(row: DocTemplateVersion) -> VersionSummary:
    return VersionSummary(
        id=row.id,
        version_number=row.version_number,
        status=row.status,
        change_note=row.change_note,
        published_at=row.published_at,
        row_version=row.row_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _version_detail(row: DocTemplateVersion) -> VersionDetail:
    return VersionDetail(
        **_version_summary(row).model_dump(),
        template_id=row.template_id,
        layout=row.layout,
    )


def _live(rows: list[DocTemplateVersion]) -> list[DocTemplateVersion]:
    return [row for row in rows if row.deleted_at is None]


def _current(versions: list[DocTemplateVersion]) -> DocTemplateVersion | None:
    published = [row for row in versions if row.status == "published"]
    return max(published, key=lambda row: row.version_number, default=None)


def _draft(versions: list[DocTemplateVersion]) -> DocTemplateVersion | None:
    return next((row for row in versions if row.status == "draft"), None)


def _summary(row: DocTemplate, versions: list[DocTemplateVersion]) -> TemplateSummary:
    live = _live(versions)
    current = _current(live)
    draft = _draft(live)
    return TemplateSummary(
        id=row.id,
        key=row.key,
        name=row.name,
        description=row.description,
        doc_type=row.doc_type,
        row_version=row.row_version,
        current_version_id=current.id if current else None,
        current_version_number=current.version_number if current else None,
        draft_version_id=draft.id if draft else None,
        draft_version_number=draft.version_number if draft else None,
        version_count=len(live),
        updated_at=row.updated_at,
    )


def _detail(row: DocTemplate, versions: list[DocTemplateVersion]) -> TemplateDetail:
    # Chronological order, the same order the export file uses: a reader (and
    # an importer) sees version 1 before the draft that succeeds it.
    live = sorted(_live(versions), key=lambda item: item.version_number)
    return TemplateDetail(
        **_summary(row, versions).model_dump(),
        versions=[_version_summary(item) for item in live],
    )


async def _versions(session: AsyncSession, template_id: uuid.UUID) -> list[DocTemplateVersion]:
    rows = (
        await session.execute(
            select(DocTemplateVersion)
            .where(DocTemplateVersion.template_id == template_id)
            .order_by(DocTemplateVersion.version_number)
        )
    ).scalars()
    return _live(list(rows))


async def _get_template(session: AsyncSession, template_id: uuid.UUID) -> DocTemplate:
    row = await session.get(DocTemplate, template_id)
    if row is None or row.deleted_at is not None:
        raise NotFound("No template with that id", message_key=TEMPLATE_NOT_FOUND)
    return row


async def _get_version(
    session: AsyncSession, template_id: uuid.UUID, version_id: uuid.UUID
) -> DocTemplateVersion:
    row = await session.get(DocTemplateVersion, version_id)
    if row is None or row.deleted_at is not None or row.template_id != template_id:
        raise NotFound("No version with that id", message_key=VERSION_NOT_FOUND)
    return row


async def _key_in_use(session: AsyncSession, key: str, *, exclude: uuid.UUID | None = None) -> bool:
    statement = select(DocTemplate.id).where(DocTemplate.key == key, DocTemplate.deleted_at.is_(None))
    if exclude is not None:
        statement = statement.where(DocTemplate.id != exclude)
    return (await session.execute(statement.limit(1))).first() is not None


async def _free_key(session: AsyncSession, doc_type: str) -> str:
    for _ in range(10):
        key = _new_key(doc_type)
        if not await _key_in_use(session, key):
            return key
    raise Conflict(  # pragma: no cover - requires ten colliding UUIDv7 values
        "Could not allocate a template key",
        message_key="error.documents.template_key_taken",
    )


def _next_number(versions: list[DocTemplateVersion]) -> int:
    return max((row.version_number for row in versions), default=0) + 1


# --- template reads ---------------------------------------------------------


async def list_templates(
    session: AsyncSession,
    *,
    doc_type: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[TemplateSummary], int]:
    filters = [DocTemplate.deleted_at.is_(None)]
    if doc_type:
        filters.append(DocTemplate.doc_type == doc_type)
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(DocTemplate.name.ilike(pattern) | DocTemplate.key.ilike(pattern))

    total = (
        await session.execute(select(func.count()).select_from(DocTemplate).where(*filters))
    ).scalar_one()
    rows = list(
        (
            await session.execute(
                select(DocTemplate)
                .where(*filters)
                .order_by(DocTemplate.updated_at.desc(), DocTemplate.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
    )
    if not rows:
        return [], total

    versions: dict[uuid.UUID, list[DocTemplateVersion]] = {row.id: [] for row in rows}
    for version in (
        await session.execute(
            select(DocTemplateVersion).where(
                DocTemplateVersion.template_id.in_(versions),
            )
        )
    ).scalars():
        versions[version.template_id].append(version)
    return [_summary(row, versions[row.id]) for row in rows], total


async def template_detail(session: AsyncSession, template_id: uuid.UUID) -> TemplateDetail:
    row = await _get_template(session, template_id)
    return _detail(row, await _versions(session, template_id))


async def version_detail(
    session: AsyncSession, template_id: uuid.UUID, version_id: uuid.UUID
) -> VersionDetail:
    await _get_template(session, template_id)
    return _version_detail(await _get_version(session, template_id, version_id))


# --- template writes --------------------------------------------------------


async def create_template(
    session: AsyncSession,
    principal: Principal,
    data: TemplateCreate,
    *,
    via: str = "api",
) -> TemplateDetail:
    if data.starter and data.layout is not None:
        raise ValidationFailed(
            "Choose a starter or a layout, not both",
            message_key="error.documents.starter_layout_conflict",
        )
    starter = None
    if data.starter:
        starter = STARTERS_BY_KEY.get(data.starter)
        if starter is None:
            raise ValidationFailed(
                "No starter with that key",
                message_key="error.documents.starter_unknown",
                details={"starter": data.starter},
            )
        if data.doc_type is not None and data.doc_type != starter.doc_type:
            raise ValidationFailed(
                "The starter belongs to a different document type",
                message_key="error.documents.starter_type_mismatch",
                details={"starter": data.starter, "doc_type": starter.doc_type},
            )
    doc_type = data.doc_type or (starter.doc_type if starter else "custom")
    if doc_type not in DOC_TYPES:  # pragma: no cover - the schema is a Literal
        raise ValidationFailed("Unknown document type", details={"doc_type": doc_type})

    if data.layout is not None:
        layout = _validated_layout(data.layout)
    elif starter is not None:
        layout = _validated_layout(starter.layout)
    else:
        layout = _blank_layout()

    key = data.key or await _free_key(session, doc_type)
    if await _key_in_use(session, key):
        raise ValidationFailed(
            "That template key is already in use",
            message_key="error.documents.template_key_taken",
            details={"key": key},
        )

    template = DocTemplate(
        key=key,
        name=data.name,
        description=data.description,
        doc_type=doc_type,
        created_by=actor_uuid(principal),
        updated_by=actor_uuid(principal),
    )
    session.add(template)
    await session.flush()
    version = DocTemplateVersion(
        template_id=template.id,
        version_number=1,
        status="draft",
        layout=layout,
        change_note=data.change_note,
        created_by=actor_uuid(principal),
        updated_by=actor_uuid(principal),
    )
    session.add(version)
    await session.flush()
    await record(
        session,
        action="document.template.create",
        module=MODULE,
        entity_type=TEMPLATE,
        entity_id=str(template.id),
        after={**_template_state(template), "starter": data.starter, "version": 1},
        actor=principal,
        via=via,
    )
    template_id = template.id
    await session.commit()
    session.expire_all()
    return await template_detail(session, template_id)


async def update_template(
    session: AsyncSession,
    principal: Principal,
    template_id: uuid.UUID,
    data: TemplateUpdate,
    *,
    via: str = "api",
) -> TemplateDetail:
    row = await _get_template(session, template_id)
    before = _template_state(row)
    values: dict[str, Any] = {}
    fields = data.model_fields_set
    if "name" in fields and data.name is not None:
        values["name"] = data.name
    if "description" in fields:
        values["description"] = data.description
    if "doc_type" in fields and data.doc_type is not None:
        values["doc_type"] = data.doc_type
    changes = apply_row_version(row, data.row_version, values, current_state=before)
    if changes:
        row.updated_by = actor_uuid(principal)
        await record(
            session,
            action="document.template.update",
            module=MODULE,
            entity_type=TEMPLATE,
            entity_id=str(row.id),
            before=before,
            after=_template_state(row),
            actor=principal,
            via=via,
        )
    await session.commit()
    session.expire_all()
    return await template_detail(session, template_id)


async def delete_template(
    session: AsyncSession,
    principal: Principal,
    template_id: uuid.UUID,
    *,
    via: str = "api",
) -> dict[str, Any]:
    row = await _get_template(session, template_id)
    versions = await _versions(session, template_id)
    for version in versions:
        mark_deleted(version, actor=principal)
    await soft_delete(
        session,
        row,
        action="document.template.delete",
        module=MODULE,
        actor=principal,
        via=via,
        entity_type=TEMPLATE,
    )
    await session.commit()
    return {
        "id": row.id,
        "key": row.key,
        "deleted": True,
        "versions_deleted": len(versions),
    }


async def duplicate_template(
    session: AsyncSession,
    principal: Principal,
    template_id: uuid.UUID,
    data: TemplateDuplicate,
    *,
    via: str = "api",
) -> TemplateDetail:
    source = await _get_template(session, template_id)
    versions = await _versions(session, template_id)
    base = _current(versions) or (versions[-1] if versions else None)
    layout = base.layout if base is not None else _blank_layout()

    key = data.key or await _free_key(session, source.doc_type)
    if await _key_in_use(session, key):
        raise ValidationFailed(
            "That template key is already in use",
            message_key="error.documents.template_key_taken",
            details={"key": key},
        )

    copy = DocTemplate(
        key=key,
        name=data.name,
        description=data.description if data.description is not None else source.description,
        doc_type=source.doc_type,
        created_by=actor_uuid(principal),
        updated_by=actor_uuid(principal),
    )
    session.add(copy)
    await session.flush()
    version = DocTemplateVersion(
        template_id=copy.id,
        version_number=1,
        status="draft",
        layout=layout,
        change_note=None,
        created_by=actor_uuid(principal),
        updated_by=actor_uuid(principal),
    )
    session.add(version)
    await session.flush()
    await record(
        session,
        action="document.template.duplicate",
        module=MODULE,
        entity_type=TEMPLATE,
        entity_id=str(copy.id),
        after={**_template_state(copy), "source_template_id": str(source.id)},
        actor=principal,
        via=via,
    )
    copy_id = copy.id
    await session.commit()
    session.expire_all()
    return await template_detail(session, copy_id)


# --- versions ---------------------------------------------------------------


async def create_version(
    session: AsyncSession,
    principal: Principal,
    template_id: uuid.UUID,
    data: VersionCreate,
    *,
    via: str = "api",
) -> VersionDetail:
    template = await _get_template(session, template_id)
    versions = await _versions(session, template_id)
    draft = _draft(versions)
    if draft is not None:
        raise Conflict(
            "This template already has a draft",
            message_key=DRAFT_EXISTS,
            details={
                "draft_version_id": str(draft.id),
                "draft_version_number": draft.version_number,
            },
        )

    if data.layout is not None:
        layout = _validated_layout(data.layout)
    else:
        base = _current(versions) or (versions[-1] if versions else None)
        layout = base.layout if base is not None else _blank_layout()

    version = DocTemplateVersion(
        template_id=template.id,
        version_number=_next_number(versions),
        status="draft",
        layout=layout,
        change_note=data.change_note,
        created_by=actor_uuid(principal),
        updated_by=actor_uuid(principal),
    )
    template.row_version = (template.row_version or 0) + 1
    template.updated_by = actor_uuid(principal)
    session.add(version)
    try:
        await session.flush()
    except IntegrityError as error:  # the partial unique index won the race
        await session.rollback()
        raise Conflict(
            "This template already has a draft",
            message_key=DRAFT_EXISTS,
        ) from error
    await record(
        session,
        action="document.template.version.create",
        module=MODULE,
        entity_type=VERSION,
        entity_id=str(version.id),
        after={
            **_version_state(version),
            "template_id": str(template.id),
            "source_version": (_current(versions).version_number if _current(versions) is not None else None),
        },
        actor=principal,
        via=via,
    )
    version_id = version.id
    await session.commit()
    session.expire_all()
    return await version_detail(session, template_id, version_id)


async def save_version(
    session: AsyncSession,
    principal: Principal,
    template_id: uuid.UUID,
    version_id: uuid.UUID,
    data: VersionSave,
    *,
    via: str = "api",
) -> VersionDetail:
    template = await _get_template(session, template_id)
    row = await _get_version(session, template_id, version_id)
    if row.status != "draft":
        raise Conflict(
            "A published version cannot be edited",
            message_key="error.documents.version_not_draft",
            details={"version_number": row.version_number, "status": row.status},
        )
    before = _version_state(row)
    values: dict[str, Any] = {"layout": _validated_layout(data.layout)}
    if "change_note" in data.model_fields_set:
        values["change_note"] = data.change_note
    changes = apply_row_version(row, data.row_version, values, current_state=before)
    if changes:
        row.updated_by = actor_uuid(principal)
        template.row_version = (template.row_version or 0) + 1
        template.updated_by = actor_uuid(principal)
        await record(
            session,
            action="document.template.version.save",
            module=MODULE,
            entity_type=VERSION,
            entity_id=str(row.id),
            before=before,
            after=_version_state(row),
            actor=principal,
            via=via,
        )
    saved_id = row.id
    await session.commit()
    session.expire_all()
    return await version_detail(session, template_id, saved_id)


async def publish_version(
    session: AsyncSession,
    principal: Principal,
    template_id: uuid.UUID,
    version_id: uuid.UUID,
    *,
    via: str = "api",
) -> VersionDetail:
    template = await _get_template(session, template_id)
    row = await _get_version(session, template_id, version_id)
    if row.status != "draft":
        raise Conflict(
            "Only a draft can be published",
            message_key="error.documents.version_not_draft",
            details={"version_number": row.version_number, "status": row.status},
        )
    # Re-validate the stored layout: a database edited outside this service must
    # not be able to publish something the renderer cannot print.
    row.layout = _validated_layout(row.layout)
    before = _version_state(row)
    row.status = "published"
    row.published_at = datetime.now(UTC)
    row.published_by = actor_uuid(principal)
    row.row_version = (row.row_version or 0) + 1
    row.updated_by = actor_uuid(principal)
    template.row_version = (template.row_version or 0) + 1
    template.updated_by = actor_uuid(principal)
    await record(
        session,
        action="document.template.version.publish",
        module=MODULE,
        entity_type=VERSION,
        entity_id=str(row.id),
        before=before,
        after=_version_state(row),
        actor=principal,
        via=via,
    )
    published_id = row.id
    await session.commit()
    session.expire_all()
    return await version_detail(session, template_id, published_id)


# --- file interchange -------------------------------------------------------


async def export_template(session: AsyncSession, template_id: uuid.UUID) -> TemplateFile:
    row = await _get_template(session, template_id)
    versions = await _versions(session, template_id)
    if not versions:  # pragma: no cover - create always makes a first version
        raise ValidationFailed(
            "A template without versions cannot be exported",
            message_key="error.documents.import_invalid",
        )
    return TemplateFile(
        format="school-erp.doc-template",
        format_version=1,
        exported_at=datetime.now(UTC),
        template={
            "key": row.key,
            "name": row.name,
            "description": row.description,
            "doc_type": row.doc_type,
        },
        versions=[
            TemplateFileVersion(
                version_number=version.version_number,
                status=version.status,
                change_note=version.change_note,
                published_at=version.published_at,
                layout=version.layout,
            )
            for version in versions
        ],
    )


def _check_file(payload: TemplateFile) -> dict[int, dict[str, Any]]:
    numbers: set[int] = set()
    drafts = 0
    layouts: dict[int, dict[str, Any]] = {}
    for version in payload.versions:
        if version.version_number in numbers:
            raise ValidationFailed(
                "Two versions share a version number",
                message_key="error.documents.import_invalid",
                details={"version_number": version.version_number},
            )
        numbers.add(version.version_number)
        if version.status == "draft":
            drafts += 1
        layouts[version.version_number] = _validated_layout(version.layout)
    if drafts > 1:
        raise ValidationFailed(
            "An imported template can have at most one draft",
            message_key="error.documents.import_invalid",
            details={"drafts": drafts},
        )
    return layouts


async def import_template(
    session: AsyncSession,
    principal: Principal,
    payload: TemplateFile,
    *,
    via: str = "api",
) -> TemplateDetail:
    layouts = _check_file(payload)
    source = payload.template
    key = source.key
    if await _key_in_use(session, key):
        key = await _free_key(session, source.doc_type)

    template = DocTemplate(
        key=key,
        name=source.name,
        description=source.description,
        doc_type=source.doc_type,
        created_by=actor_uuid(principal),
        updated_by=actor_uuid(principal),
    )
    session.add(template)
    await session.flush()
    versions: list[DocTemplateVersion] = []
    for spec in sorted(payload.versions, key=lambda item: item.version_number):
        published = spec.status == "published"
        version = DocTemplateVersion(
            template_id=template.id,
            version_number=spec.version_number,
            status=spec.status,
            layout=layouts[spec.version_number],
            change_note=spec.change_note,
            published_at=spec.published_at or (datetime.now(UTC) if published else None),
            published_by=actor_uuid(principal) if published else None,
            created_by=actor_uuid(principal),
            updated_by=actor_uuid(principal),
        )
        session.add(version)
        versions.append(version)
    await session.flush()
    await record(
        session,
        action="document.template.import",
        module=MODULE,
        entity_type=TEMPLATE,
        entity_id=str(template.id),
        after={
            **_template_state(template),
            "source_key": source.key,
            "versions": len(versions),
        },
        actor=principal,
        via=via,
    )
    imported_id = template.id
    await session.commit()
    session.expire_all()
    return await template_detail(session, imported_id)


__all__ = [
    "create_template",
    "create_version",
    "delete_template",
    "duplicate_template",
    "export_template",
    "import_template",
    "list_templates",
    "publish_version",
    "save_version",
    "template_detail",
    "update_template",
    "version_detail",
]
