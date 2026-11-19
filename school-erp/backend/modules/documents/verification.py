"""Public verification of an issued document (P5-09).

The QR code on a printed document points at ``/verify/{code}``. That page must
work without an account, so the API behind it is deliberately public and
returns only what a person needs to trust the paper: the number, its type, who
it was issued to and when. The layout, data snapshot, marks, guardians and file
are never exposed.

Unknown codes are indistinguishable from each other and every lookup is rate
limited per client address before the database is touched, so the endpoint
cannot be used to enumerate issued documents.
"""

from __future__ import annotations

from app.errors import NotFound
from app.settings import Settings
from core.auth.rate_limit import SlidingWindowLimiter
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.documents.models import IssuedDocument
from modules.documents.schemas import DocumentVerificationOut

# One limiter per process, like the public admissions endpoint. Production can
# move it behind the shared cache without changing this interface.
verify_limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client and request.client.host else "unknown"


async def verify_document(
    session: AsyncSession,
    settings: Settings,
    code: str,
    request: Request,
) -> DocumentVerificationOut:
    """Look up one verification code and return the minimal public view."""
    verify_limiter.hit(
        f"documents-verify:{client_ip(request)}",
        limit=settings.document_verify_rate_limit,
        window_seconds=settings.document_verify_rate_window_seconds,
    )
    row = (
        await session.execute(
            select(IssuedDocument).where(
                IssuedDocument.verification_code == code,
                IssuedDocument.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "This document could not be verified",
            message_key="error.documents.verification_not_found",
        )
    snapshot = row.data_snapshot if isinstance(row.data_snapshot, dict) else {}
    school = snapshot.get("school") if isinstance(snapshot.get("school"), dict) else {}
    return DocumentVerificationOut(
        valid=True,
        number=row.number,
        doc_type=row.doc_type,
        recipient_name=row.recipient_name,
        issued_at=row.issued_at,
        school_name=school.get("name") if school else None,
    )


__all__ = ["client_ip", "verify_document", "verify_limiter"]
