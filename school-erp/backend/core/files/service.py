"""File metadata, access rules, signed URLs and thumbnail generation (P1-22)."""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import re
import uuid
from typing import Any

from app.errors import Forbidden, NotFound, ValidationFailed
from app.settings import Settings
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import actor_uuid, soft_delete
from core.events.service import create_job, emit
from core.files.models import StoredFile
from core.files.storage import Storage, new_object_key
from core.files.validation import ValidatedUpload, validate_upload

logger = logging.getLogger("erp.files")

OWNER_TYPE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
OWNER_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
THUMBNAIL_SIZE = (320, 320)


def _view(row: StoredFile) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "name": row.original_name,
        "mime": row.mime,
        "size_bytes": row.size_bytes,
        "checksum_sha256": row.checksum_sha256,
        "owner_entity_type": row.owner_entity_type,
        "owner_entity_id": row.owner_entity_id,
        "is_private": row.is_private,
        "uploaded_by": str(row.uploaded_by) if row.uploaded_by else None,
        "has_thumbnail": row.thumbnail_key is not None,
        "row_version": row.row_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _detail(row: StoredFile, storage: Storage, ttl: int) -> dict[str, Any]:
    view = _view(row)
    view["url"] = storage.signed_url(row.object_key, expires_in=ttl).url
    if row.thumbnail_key:
        view["thumbnail_url"] = storage.signed_url(row.thumbnail_key, expires_in=ttl).url
    else:
        view["thumbnail_url"] = None
    return view


def _check_owner(owner_type: str | None, owner_id: str | None) -> None:
    if bool(owner_type) != bool(owner_id):
        raise ValidationFailed(
            "Owner type and owner id must be supplied together",
            message_key="error.file.invalid_owner",
            details={"owner_entity_type": owner_type, "owner_entity_id": owner_id},
        )
    if owner_type is not None and not OWNER_TYPE.match(owner_type):
        raise ValidationFailed(
            "The owner entity type is not valid",
            message_key="error.file.invalid_owner",
            details={"owner_entity_type": owner_type},
        )
    if owner_id is not None and not OWNER_ID.match(owner_id):
        raise ValidationFailed(
            "The owner entity id is not valid",
            message_key="error.file.invalid_owner",
            details={"owner_entity_id": owner_id},
        )


def can_view(principal: Principal, row: StoredFile) -> bool:
    if row.uploaded_by is not None and str(row.uploaded_by) == principal.actor_id:
        return True
    if principal.can("files.view"):
        return True
    return not row.is_private


def can_manage(principal: Principal, row: StoredFile) -> bool:
    if row.uploaded_by is not None and str(row.uploaded_by) == principal.actor_id:
        return True
    return principal.can("files.manage")


async def upload_file(
    session: AsyncSession,
    principal: Principal,
    storage: Storage,
    settings: Settings,
    *,
    filename: str | None,
    content_type: str | None,
    data: bytes,
    owner_entity_type: str | None = None,
    owner_entity_id: str | None = None,
    is_private: bool = True,
    commit: bool = True,
    thumbnail: bool = True,
) -> dict[str, Any]:
    _check_owner(owner_entity_type, owner_entity_id)
    upload: ValidatedUpload = validate_upload(
        filename,
        content_type,
        data,
        max_bytes=settings.storage_max_upload_bytes,
    )
    key = new_object_key(upload.filename)
    await storage.put(key, upload.data, upload.mime)
    row = StoredFile(
        object_key=key,
        original_name=upload.filename,
        mime=upload.mime,
        size_bytes=len(upload.data),
        checksum_sha256=hashlib.sha256(upload.data).hexdigest(),
        owner_entity_type=owner_entity_type,
        owner_entity_id=owner_entity_id,
        is_private=is_private,
        uploaded_by=actor_uuid(principal),
    )
    row.created_by = actor_uuid(principal)
    row.updated_by = actor_uuid(principal)
    session.add(row)
    await session.flush()
    await record(
        session,
        action="file.upload",
        module="core",
        entity_type="file",
        entity_id=str(row.id),
        after=_view(row),
        actor=principal,
        via=principal.via,
    )
    await emit(
        session,
        "file.uploaded",
        {
            "file_id": str(row.id),
            "name": row.original_name,
            "mime": row.mime,
            "owner_entity_type": row.owner_entity_type,
            "owner_entity_id": row.owner_entity_id,
        },
        actor_id=principal.actor_id,
    )
    job_id: str | None = None
    if upload.is_image and thumbnail:
        job = await create_job(
            session,
            "files.thumbnail",
            {"file_id": str(row.id)},
            created_by=principal.actor_id,
        )
        job_id = str(job.id)
    if commit:
        await session.commit()
        await session.refresh(row)

        # Test runs execute jobs through the service directly; without a broker
        # the queue would otherwise block or target the production database.
        if job_id is not None and settings.app_env != "test":
            try:
                from core.events.celery_app import files_thumbnail_task

                await asyncio.to_thread(files_thumbnail_task.delay, job_id, str(row.id))
            except Exception as exc:  # pragma: no cover - broker outages are operational
                logger.warning("thumbnail enqueue failed: %s", exc)

    result = _detail(row, storage, settings.storage_signed_url_seconds)
    result["thumbnail_job_id"] = job_id
    return result


async def get_row(session: AsyncSession, file_id: str) -> StoredFile:
    try:
        identifier = uuid.UUID(file_id)
    except ValueError as exc:
        raise NotFound("No file with that id", message_key="error.file.not_found") from exc
    row = (await session.execute(select(StoredFile).where(StoredFile.id == identifier))).scalar_one_or_none()
    if row is None:
        raise NotFound("No file with that id", message_key="error.file.not_found")
    return row


async def get_file(
    session: AsyncSession,
    principal: Principal,
    storage: Storage,
    settings: Settings,
    file_id: str,
) -> dict[str, Any]:
    row = await get_row(session, file_id)
    if not can_view(principal, row):
        raise Forbidden(
            "You cannot view this file",
            message_key="error.permission_denied",
            details={"file_id": file_id},
        )
    return _detail(row, storage, settings.storage_signed_url_seconds)


async def list_files(
    session: AsyncSession,
    storage: Storage,
    settings: Settings,
    *,
    owner_entity_type: str | None = None,
    owner_entity_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    stmt = (
        select(StoredFile)
        .where(StoredFile.deleted_at.is_(None))
        .order_by(StoredFile.created_at.desc())
        .limit(max(1, min(limit, 200)))
    )
    if owner_entity_type:
        stmt = stmt.where(StoredFile.owner_entity_type == owner_entity_type)
    if owner_entity_id:
        stmt = stmt.where(StoredFile.owner_entity_id == owner_entity_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [_detail(row, storage, settings.storage_signed_url_seconds) for row in rows]


async def delete_file(
    session: AsyncSession,
    principal: Principal,
    file_id: str,
) -> dict[str, Any]:
    row = await get_row(session, file_id)
    if not can_manage(principal, row):
        raise Forbidden(
            "You cannot delete this file",
            message_key="error.permission_denied",
            details={"file_id": file_id},
        )
    deleted = await soft_delete(
        session,
        row,
        action="file.delete",
        module="core",
        actor=principal,
        via=principal.via,
        entity_type="file",
    )
    await session.commit()
    return {"id": file_id, "deleted": deleted}


async def signed_file_url(
    session: AsyncSession,
    principal: Principal,
    storage: Storage,
    settings: Settings,
    file_id: str,
    *,
    thumbnail: bool = False,
    expires_in: int | None = None,
) -> dict[str, Any]:
    row = await get_row(session, file_id)
    if not can_view(principal, row):
        raise Forbidden(
            "You cannot view this file",
            message_key="error.permission_denied",
            details={"file_id": file_id},
        )
    if thumbnail:
        if row.thumbnail_key is None:
            raise NotFound(
                "This file has no thumbnail yet",
                message_key="error.file.thumbnail_missing",
                details={"file_id": file_id},
            )
        key = row.thumbnail_key
    else:
        key = row.object_key
    ttl = min(expires_in or settings.storage_signed_url_seconds, 86_400)
    signed = storage.signed_url(key, expires_in=ttl)
    return {
        "url": signed.url,
        "expires_in": signed.expires_in,
        "thumbnail": thumbnail,
    }


def _thumbnail_bytes(data: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(THUMBNAIL_SIZE)
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=82, optimize=True)
            return buffer.getvalue()
    except (OSError, ValueError) as exc:
        raise ValidationFailed(
            "The thumbnail could not be generated",
            message_key="error.file.thumbnail_failed",
        ) from exc


async def generate_thumbnail(
    session: AsyncSession,
    storage: Storage,
    file_id: str,
) -> dict[str, Any]:
    """Create a small JPEG preview for an image and remember its key."""
    row = await get_row(session, file_id)
    if not row.mime.startswith("image/"):
        raise ValidationFailed(
            "Only images have thumbnails",
            message_key="error.file.thumbnail_failed",
            details={"mime": row.mime},
        )
    data = await storage.get(row.object_key)
    thumb = _thumbnail_bytes(data)
    key = f"thumbnails/{row.object_key.rsplit('.', 1)[0]}.jpg"
    await storage.put(key, thumb, "image/jpeg")
    row.thumbnail_key = key
    await session.commit()
    await session.refresh(row)
    return {
        "file_id": str(row.id),
        "thumbnail_key": key,
        "size_bytes": len(thumb),
        "thumbnail_url": storage.signed_url(key).url,
    }


__all__ = [
    "can_manage",
    "can_view",
    "delete_file",
    "generate_thumbnail",
    "get_file",
    "get_row",
    "list_files",
    "signed_file_url",
    "upload_file",
]
