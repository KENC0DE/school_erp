"""Student documents, scoped to the student record instead of all files."""

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

from modules.students.common import live_person, live_student

MODULE = "students"
OWNER_TYPE = "student"
PHOTO_OWNER_TYPE = "person"


async def list_documents(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    student_id: uuid.UUID,
) -> list[dict[str, Any]]:
    await live_student(session, student_id)
    return await list_files(
        session,
        storage,
        settings,
        owner_entity_type=OWNER_TYPE,
        owner_entity_id=str(student_id),
    )


async def upload_document(
    session: AsyncSession,
    principal: Principal,
    storage: Storage,
    settings: Settings,
    student_id: uuid.UUID,
    *,
    filename: str | None,
    content_type: str | None,
    data: bytes,
) -> dict[str, Any]:
    await live_student(session, student_id)
    result = await upload_file(
        session,
        principal,
        storage,
        settings,
        filename=filename,
        content_type=content_type,
        data=data,
        owner_entity_type=OWNER_TYPE,
        owner_entity_id=str(student_id),
        is_private=True,
        commit=False,
    )
    await record(
        session,
        action="students.documents.upload",
        module=MODULE,
        entity_type="file",
        entity_id=str(result["id"]),
        after={"name": result["name"], "student_id": str(student_id)},
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    return result


async def _owned_file(session: AsyncSession, student_id: uuid.UUID, file_id: str) -> StoredFile:
    await live_student(session, student_id)
    row = await get_row(session, file_id)
    if (
        row.deleted_at is not None
        or row.owner_entity_type != OWNER_TYPE
        or row.owner_entity_id != str(student_id)
    ):
        raise NotFound("No file with that id", message_key="error.file.not_found")
    return row


async def delete_document(
    session: AsyncSession,
    principal: Principal,
    student_id: uuid.UUID,
    file_id: str,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    row = await _owned_file(session, student_id, file_id)
    await soft_delete(
        session,
        row,
        action="students.documents.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=principal.via,
        entity_type="file",
    )
    await session.commit()
    return {"id": file_id, "deleted": True}


async def upload_photo(
    session: AsyncSession,
    principal: Principal,
    storage: Storage,
    settings: Settings,
    *,
    filename: str | None,
    content_type: str | None,
    data: bytes,
    person_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Store a person photo.

    A brand-new student has no person id yet, so the file is uploaded before the
    record exists and the id returned to the caller becomes ``photo_file_id``.
    Replacing a photo passes the existing person id, which keeps the file scoped
    to that person for later cleanup.
    """
    result = await upload_file(
        session,
        principal,
        storage,
        settings,
        filename=filename,
        content_type=content_type,
        data=data,
        owner_entity_type=PHOTO_OWNER_TYPE if person_id is not None else None,
        owner_entity_id=str(person_id) if person_id is not None else None,
        is_private=True,
        commit=False,
    )
    await record(
        session,
        action="students.photo.upload",
        module=MODULE,
        entity_type="file",
        entity_id=str(result["id"]),
        after={"name": result["name"], "person_id": str(person_id) if person_id else None},
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    return result


async def get_photo(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    student_id: uuid.UUID,
) -> dict[str, Any]:
    profile = await live_student(session, student_id)
    person = await live_person(session, profile.person_id)
    if person.photo_file_id is None:
        raise NotFound(
            "This student has no photo",
            message_key="students.error.photo_missing",
        )
    row = await get_row(session, str(person.photo_file_id))
    if row.deleted_at is not None:
        raise NotFound(
            "This student has no photo",
            message_key="students.error.photo_missing",
        )
    signed = storage.signed_url(row.object_key, expires_in=settings.storage_signed_url_seconds)
    thumbnail = (
        storage.signed_url(row.thumbnail_key, expires_in=settings.storage_signed_url_seconds).url
        if row.thumbnail_key
        else None
    )
    return {
        "file_id": str(row.id),
        "name": row.original_name,
        "mime": row.mime,
        "url": signed.url,
        "thumbnail_url": thumbnail,
        "expires_in": signed.expires_in,
    }


__all__ = [
    "delete_document",
    "get_photo",
    "list_documents",
    "upload_document",
    "upload_photo",
]
