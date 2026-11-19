"""Documents attached to an admission application.

Files are private and scoped to one application: a caller with the admissions
permission still cannot read or delete another application's attachment.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import NotFound
from app.settings import Settings
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import soft_delete
from core.files.models import StoredFile
from core.files.service import get_row, list_files, upload_file
from core.files.storage import Storage
from sqlalchemy.ext.asyncio import AsyncSession

from modules.admissions.service import live_application

MODULE = "admissions"
OWNER_TYPE = "admission_application"


async def list_documents(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    application_id: uuid.UUID,
) -> list[dict[str, Any]]:
    await live_application(session, application_id)
    return await list_files(
        session,
        storage,
        settings,
        owner_entity_type=OWNER_TYPE,
        owner_entity_id=str(application_id),
    )


async def upload_document(
    session: AsyncSession,
    principal: Principal,
    storage: Storage,
    settings: Settings,
    application_id: uuid.UUID,
    *,
    filename: str | None,
    content_type: str | None,
    data: bytes,
) -> dict[str, Any]:
    await live_application(session, application_id)
    result = await upload_file(
        session,
        principal,
        storage,
        settings,
        filename=filename,
        content_type=content_type,
        data=data,
        owner_entity_type=OWNER_TYPE,
        owner_entity_id=str(application_id),
        is_private=True,
        commit=False,
    )
    await record(
        session,
        action="admissions.documents.upload",
        module=MODULE,
        entity_type="file",
        entity_id=str(result["id"]),
        after={"name": result["name"], "application_id": str(application_id)},
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    return result


async def _owned_file(session: AsyncSession, application_id: uuid.UUID, file_id: str) -> StoredFile:
    await live_application(session, application_id)
    row = await get_row(session, file_id)
    if (
        row.deleted_at is not None
        or row.owner_entity_type != OWNER_TYPE
        or row.owner_entity_id != str(application_id)
    ):
        raise NotFound("No file with that id", message_key="error.file.not_found")
    return row


async def delete_document(
    session: AsyncSession,
    principal: Principal,
    application_id: uuid.UUID,
    file_id: str,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    row = await _owned_file(session, application_id, file_id)
    await soft_delete(
        session,
        row,
        action="admissions.documents.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=principal.via,
        entity_type="file",
    )
    await session.commit()
    return {"id": file_id, "deleted": True}


__all__ = ["delete_document", "list_documents", "upload_document"]
