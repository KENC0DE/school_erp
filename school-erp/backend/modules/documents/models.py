"""Document templates and their numbered versions (P5-04).

A template is the stable identity a document is requested by (a report card
design, an ID card design). Its layout lives in a version: a draft can be edited
freely, a published version never changes again, and generation records the
version it used so a reprint is reproducible even after the design moves on.

Only one draft may exist per template at a time. ``uq_doc_template_versions_draft``
enforces that in the database, so two editors cannot create competing drafts
even if they race.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from core.db.base import BusinessModel, JSONType
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid, text
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


__all__ = ["DOC_TYPES", "VERSION_STATUSES", "DocTemplate", "DocTemplateVersion"]
