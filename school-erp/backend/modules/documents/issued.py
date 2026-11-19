"""Reading batches and issued documents, and serving reprints (P5-08).

An issued document is evidence, so reads return the stored artifact rather than
re-rendering today's data. Download URLs are short-lived signed links; the
reprint read is audited because fetching a student's document is a sensitive
read, not an anonymous file download.
"""

from __future__ import annotations

import uuid

from app.errors import NotFound
from app.settings import Settings
from core.api.pagination import PageParams, contains, paginate
from core.audit.service import record_read
from core.auth.principal import Principal
from core.files.models import StoredFile
from core.files.storage import Storage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.documents.models import DocTemplate, DocumentBatch, IssuedDocument
from modules.documents.schemas import (
    FileLinkOut,
    GenerationBatchList,
    GenerationBatchOut,
    IssuedDocumentDetail,
    IssuedDocumentList,
    IssuedDocumentSummary,
    ReprintOut,
)

SORTS = {
    "issued_at": IssuedDocument.issued_at,
    "number": IssuedDocument.number,
}


async def _file(session: AsyncSession, file_id: uuid.UUID | None) -> StoredFile | None:
    if file_id is None:
        return None
    return (await session.execute(select(StoredFile).where(StoredFile.id == file_id))).scalar_one_or_none()


async def _download_url(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    file_id: uuid.UUID | None,
) -> str | None:
    row = await _file(session, file_id)
    if row is None or row.deleted_at is not None:
        return None
    return storage.signed_url(row.object_key, expires_in=settings.storage_signed_url_seconds).url


def _summary(
    row: IssuedDocument,
    template_name: str,
    *,
    download_url: str | None,
) -> IssuedDocumentSummary:
    return IssuedDocumentSummary(
        id=str(row.id),
        number=row.number,
        verification_code=row.verification_code,
        template_id=str(row.template_id),
        template_name=template_name,
        doc_type=row.doc_type,
        template_version_number=row.template_version_number,
        recipient_type=row.recipient_type,
        recipient_id=str(row.recipient_id) if row.recipient_id else None,
        recipient_name=row.recipient_name,
        batch_id=str(row.batch_id) if row.batch_id else None,
        file_id=str(row.file_id) if row.file_id else None,
        download_url=download_url,
        issued_at=row.issued_at,
    )


async def _template_names(session: AsyncSession, template_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not template_ids:
        return {}
    rows = (
        await session.execute(
            select(DocTemplate.id, DocTemplate.name).where(DocTemplate.id.in_(template_ids))
        )
    ).all()
    return {row[0]: row[1] for row in rows}


async def list_issued(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    params: PageParams,
    *,
    template_id: uuid.UUID | None = None,
    batch_id: uuid.UUID | None = None,
    recipient_id: uuid.UUID | None = None,
    q: str | None = None,
) -> IssuedDocumentList:
    stmt = select(IssuedDocument).where(IssuedDocument.deleted_at.is_(None))
    if template_id is not None:
        stmt = stmt.where(IssuedDocument.template_id == template_id)
    if batch_id is not None:
        stmt = stmt.where(IssuedDocument.batch_id == batch_id)
    if recipient_id is not None:
        stmt = stmt.where(IssuedDocument.recipient_id == recipient_id)
    if q and q.strip():
        stmt = stmt.where(
            contains(IssuedDocument.recipient_name, q.strip()) | contains(IssuedDocument.number, q.strip())
        )
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows, next_cursor = await paginate(
        session,
        stmt,
        params,
        sort_columns=SORTS,
        default_sort="issued_at",
        id_column=IssuedDocument.id,
    )
    names = await _template_names(session, {row.template_id for row in rows})
    items = [
        _summary(
            row,
            names.get(row.template_id, ""),
            download_url=await _download_url(session, storage, settings, row.file_id),
        )
        for row in rows
    ]
    return IssuedDocumentList(items=items, next_cursor=next_cursor, total=total)


async def get_issued(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    issued_id: uuid.UUID,
) -> IssuedDocumentDetail:
    row = (
        await session.execute(
            select(IssuedDocument).where(
                IssuedDocument.id == issued_id,
                IssuedDocument.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The issued document does not exist",
            message_key="error.documents.issued_not_found",
        )
    names = await _template_names(session, {row.template_id})
    summary = _summary(
        row,
        names.get(row.template_id, ""),
        download_url=await _download_url(session, storage, settings, row.file_id),
    )
    return IssuedDocumentDetail(
        **summary.model_dump(),
        layout=row.layout,
        data_snapshot=row.data_snapshot,
    )


async def reprint(
    session: AsyncSession,
    principal: Principal,
    storage: Storage,
    settings: Settings,
    issued_id: uuid.UUID,
) -> ReprintOut:
    row = (
        await session.execute(
            select(IssuedDocument).where(
                IssuedDocument.id == issued_id,
                IssuedDocument.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The issued document does not exist",
            message_key="error.documents.issued_not_found",
        )
    stored = await _file(session, row.file_id)
    if stored is None or stored.deleted_at is not None:
        raise NotFound(
            "The stored PDF is no longer available",
            message_key="error.file.not_found",
        )
    await record_read(
        session,
        entity_type="issued_document",
        entity_id=str(row.id),
        actor=principal,
        action="documents.reprint",
        module="documents",
        via=principal.via,
    )
    await session.commit()
    return ReprintOut(
        id=str(row.id),
        number=row.number,
        file_id=str(stored.id),
        url=storage.signed_url(stored.object_key, expires_in=settings.storage_signed_url_seconds).url,
        checksum_sha256=stored.checksum_sha256,
    )


def _batch_out(row: DocumentBatch, template_name: str, download_url: str | None) -> GenerationBatchOut:
    return GenerationBatchOut(
        id=str(row.id),
        template_id=str(row.template_id),
        template_name=template_name,
        template_version_id=str(row.template_version_id),
        template_version_number=row.context.get("version_number", 0) if isinstance(row.context, dict) else 0,
        mode=row.mode,
        combine=row.combine,
        count=row.count,
        issued_count=row.issued_count,
        failed_count=row.failed_count,
        progress=row.progress,
        status=row.status,
        approval_required=row.approval_required,
        requested_by=row.context.get("display_name") if isinstance(row.context, dict) else None,
        approved_at=row.approved_at,
        rejection_reason=row.rejection_reason,
        file_id=str(row.file_id) if row.file_id else None,
        download_url=download_url,
        failure_summary=row.failure_summary,
        created_at=row.created_at,
        issued_at=row.issued_at,
    )


async def list_batches(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    *,
    template_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 25,
) -> GenerationBatchList:
    stmt = select(DocumentBatch).where(DocumentBatch.deleted_at.is_(None))
    if template_id is not None:
        stmt = stmt.where(DocumentBatch.template_id == template_id)
    if status is not None:
        stmt = stmt.where(DocumentBatch.status == status)
    rows = list(
        (await session.execute(stmt.order_by(DocumentBatch.created_at.desc()).limit(max(1, min(limit, 100)))))
        .scalars()
        .all()
    )
    names = await _template_names(session, {row.template_id for row in rows})
    items = [
        _batch_out(
            row,
            names.get(row.template_id, ""),
            await _download_url(session, storage, settings, row.file_id),
        )
        for row in rows
    ]
    return GenerationBatchList(items=items)


async def get_batch(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    batch_id: uuid.UUID,
) -> GenerationBatchOut:
    row = (
        await session.execute(
            select(DocumentBatch).where(
                DocumentBatch.id == batch_id,
                DocumentBatch.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The generation batch does not exist",
            message_key="error.documents.batch_not_found",
        )
    names = await _template_names(session, {row.template_id})
    return _batch_out(
        row,
        names.get(row.template_id, ""),
        await _download_url(session, storage, settings, row.file_id),
    )


async def batch_download(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    batch_id: uuid.UUID,
) -> FileLinkOut:
    """The combined PDF of a batch, when the caller asked for one file."""
    row = (
        await session.execute(
            select(DocumentBatch).where(
                DocumentBatch.id == batch_id,
                DocumentBatch.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "The generation batch does not exist",
            message_key="error.documents.batch_not_found",
        )
    stored = await _file(session, row.file_id)
    if stored is None or stored.deleted_at is not None:
        raise NotFound(
            "This batch has no combined file; download its documents one by one",
            message_key="error.documents.batch_file_missing",
        )
    return FileLinkOut(
        file_id=str(stored.id),
        filename=stored.original_name,
        url=storage.signed_url(stored.object_key, expires_in=settings.storage_signed_url_seconds).url,
        checksum_sha256=stored.checksum_sha256,
    )


__all__ = [
    "batch_download",
    "get_batch",
    "get_issued",
    "list_batches",
    "list_issued",
    "reprint",
]
