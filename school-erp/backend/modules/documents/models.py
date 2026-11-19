"""Document templates, their versions, generation batches and issued documents.

A template is the stable identity a document is requested by (a report card
design, an ID card design). Its layout lives in a version: a draft can be edited
freely, a published version never changes again, and generation records the
version it used so a reprint is reproducible even after the design moves on.

Issuance stores both the exact layout and the data snapshot beside the PDF. A
reprint therefore never depends on today's student record, today's marks or a
template that has since moved on: it serves the artifact that was issued.

Only one draft may exist per template at a time. ``uq_doc_template_versions_draft``
enforces that in the database, so two editors cannot create competing drafts
even if they race.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from core.db.base import Base, BusinessModel, JSONType, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

DOC_TYPES: tuple[str, ...] = (
    "report_card",
    "transcript",
    "certificate_completion",
    "certificate_appreciation",
    "id_card",
    "admission_letter",
    "receipt",
    "invoice",
    "experience_letter",
    "custom",
)

VERSION_STATUSES: tuple[str, ...] = ("draft", "published")

LIVE = text("deleted_at IS NULL")


class DocTemplate(BusinessModel):
    """The design a school generates documents from."""

    __tablename__ = "doc_templates"
    __table_args__ = (
        # The key is the stable machine reference kept by exports and by any
        # future API that names a template instead of an id.
        Index(
            "uq_doc_templates_key_live",
            "key",
            unique=True,
            sqlite_where=LIVE,
            postgresql_where=LIVE,
        ),
        Index("ix_doc_templates_type", "doc_type"),
    )

    key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    doc_type: Mapped[str] = mapped_column(String(40), nullable=False)


class DocTemplateVersion(BusinessModel):
    """One immutable-once-published layout of a template."""

    __tablename__ = "doc_template_versions"
    __table_args__ = (
        Index(
            "uq_doc_template_versions_number",
            "template_id",
            "version_number",
            unique=True,
        ),
        Index(
            "uq_doc_template_versions_draft",
            "template_id",
            unique=True,
            sqlite_where=text("status = 'draft' AND deleted_at IS NULL"),
            postgresql_where=text("status = 'draft' AND deleted_at IS NULL"),
        ),
        Index("ix_doc_template_versions_template", "template_id", "status"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("doc_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    layout: Mapped[dict] = mapped_column(JSONType, nullable=False)
    change_note: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))


class DocumentNumberSequence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The last document number issued for one numbering scope.

    Like the student and admission sequences this is a counter, not a business
    record. It is never soft-deleted and allocation is atomic, so a rollback may
    leave a gap but can never reuse a number that appeared on paper.
    """

    __tablename__ = "doc_number_sequences"
    __table_args__ = (UniqueConstraint("scope", name="uq_doc_number_sequences_scope"),)

    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)


class DocumentBatch(BusinessModel):
    """One generation request: a template, a target and its progress.

    The batch is the durable record behind a background job. It keeps the
    requester's actor and locale so a worker can rebuild the data snapshot with
    the same labels the caller would have seen, and it owns the combined PDF
    when the caller asked for one file.
    """

    __tablename__ = "doc_generation_batches"
    __table_args__ = (
        Index("ix_doc_generation_batches_template", "template_id"),
        Index("ix_doc_generation_batches_status", "status"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("doc_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("doc_template_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    year_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    level_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    section_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    student_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    combine: Mapped[bool] = mapped_column(default=False, nullable=False)
    # Certificates may need a second pair of eyes before anything is numbered.
    # The flag is copied at request time so changing the school policy later
    # cannot strand or silently release an already requested batch.
    approval_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issued_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    failure_summary: Mapped[str | None] = mapped_column(Text)
    # Actor identity and locale, never permissions: see docs/DECISIONS.md.
    context: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IssuedDocument(BusinessModel):
    """One numbered, verifiable document produced from a template version.

    ``layout`` and ``data_snapshot`` are copies, not foreign keys, so a reprint
    years later reproduces the document even after the student, the marks or the
    template have changed. ``verification_code`` is the public, unguessable
    handle the QR code points at; the public page (P5-09) decides what of the
    snapshot it may reveal.
    """

    __tablename__ = "issued_documents"
    __table_args__ = (
        Index("uq_issued_documents_number", "number", unique=True),
        Index("uq_issued_documents_verification", "verification_code", unique=True),
        Index("ix_issued_documents_template", "template_id"),
        Index("ix_issued_documents_batch", "batch_id"),
        Index("ix_issued_documents_recipient", "recipient_type", "recipient_id"),
        Index("ix_issued_documents_issued_at", "issued_at"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("doc_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("doc_template_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    template_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_type: Mapped[str] = mapped_column(String(40), nullable=False)
    layout: Mapped[dict] = mapped_column(JSONType, nullable=False)
    data_snapshot: Mapped[dict] = mapped_column(JSONType, nullable=False)
    number: Mapped[str] = mapped_column(String(60), nullable=False)
    verification_code: Mapped[str] = mapped_column(String(64), nullable=False)
    issuer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    batch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    recipient_type: Mapped[str] = mapped_column(String(30), nullable=False)
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False)


__all__ = [
    "DOC_TYPES",
    "VERSION_STATUSES",
    "DocTemplate",
    "DocTemplateVersion",
    "DocumentBatch",
    "DocumentNumberSequence",
    "IssuedDocument",
]
