"""API models for the document module (P5-04 templates)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from core.documents.fields import FieldKind
from pydantic import BaseModel, ConfigDict, Field, model_validator

DocType = Literal[
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
]
VersionStatus = Literal["draft", "published"]

KEY_PATTERN = r"^[a-z0-9][a-z0-9-]{2,79}$"


class DocumentFieldOut(BaseModel):
    """One bindable value, attributed to the module that offers it."""

    key: str
    label_key: str
    kind: FieldKind
    formats: list[str] = Field(default_factory=list)
    sample: Any = None
    module: str


class DocumentFormatOptions(BaseModel):
    """The formatting dimensions the renderer and the editor both understand."""

    calendar: list[str]
    script: list[str]
    money: list[str]


class DocumentFieldsOut(BaseModel):
    items: list[DocumentFieldOut] = Field(default_factory=list)
    format_options: DocumentFormatOptions


# --- starter library --------------------------------------------------------


class StarterOut(BaseModel):
    """A library entry; its name and description are translation keys."""

    key: str
    doc_type: DocType
    name_key: str
    description_key: str
    layout: dict[str, Any]


class StarterList(BaseModel):
    items: list[StarterOut] = Field(default_factory=list)


# --- template and version views --------------------------------------------


class VersionSummary(BaseModel):
    id: uuid.UUID
    version_number: int
    status: VersionStatus
    change_note: str | None = None
    published_at: datetime | None = None
    row_version: int
    created_at: datetime
    updated_at: datetime


class VersionDetail(VersionSummary):
    template_id: uuid.UUID
    layout: dict[str, Any]


class TemplateSummary(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: str | None = None
    doc_type: DocType
    row_version: int
    current_version_id: uuid.UUID | None = None
    current_version_number: int | None = None
    draft_version_id: uuid.UUID | None = None
    draft_version_number: int | None = None
    version_count: int = 0
    updated_at: datetime


class TemplateDetail(TemplateSummary):
    versions: list[VersionSummary] = Field(default_factory=list)


class TemplateList(BaseModel):
    items: list[TemplateSummary] = Field(default_factory=list)
    total: int


class VersionList(BaseModel):
    items: list[VersionSummary] = Field(default_factory=list)
    total: int


class TemplateDeleted(BaseModel):
    id: uuid.UUID
    key: str
    deleted: bool
    versions_deleted: int


# --- requests ---------------------------------------------------------------


class TemplateCreate(BaseModel):
    """Create from a starter, an explicit layout, or an empty A4 page."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    doc_type: DocType | None = None
    starter: str | None = Field(default=None, max_length=80)
    layout: dict[str, Any] | None = None
    key: str | None = Field(default=None, pattern=KEY_PATTERN)
    change_note: str | None = Field(default=None, max_length=500)


class TemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    doc_type: DocType | None = None
    row_version: int = Field(ge=1)


class TemplateDuplicate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    key: str | None = Field(default=None, pattern=KEY_PATTERN)


class VersionCreate(BaseModel):
    """Start a draft from the current published layout, or from a layout."""

    model_config = ConfigDict(extra="forbid")

    layout: dict[str, Any] | None = None
    change_note: str | None = Field(default=None, max_length=500)


class VersionSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layout: dict[str, Any]
    change_note: str | None = Field(default=None, max_length=500)
    row_version: int = Field(ge=1)


class DocumentPreviewRequest(BaseModel):
    """Preview an unsaved layout with sample data or one real student."""

    model_config = ConfigDict(extra="forbid")

    layout: dict[str, Any]
    mode: Literal["sample", "student"] = "sample"
    student_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _student_only_in_student_mode(self) -> DocumentPreviewRequest:
        if self.mode == "student" and self.student_id is None:
            raise ValueError("student_id is required when previewing a student")
        if self.mode == "sample" and self.student_id is not None:
            raise ValueError("student_id is only allowed in student mode")
        return self


class DocumentPreviewOut(BaseModel):
    mode: Literal["sample", "student"]
    html: str
    page_mm: list[float]
    media_mm: list[float]
    student_id: uuid.UUID | None = None
    student_name: str | None = None


class GenerationTarget(BaseModel):
    """Who a batch is for: one student, one section or a whole grade."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["student", "section", "level"]
    student_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    level_id: uuid.UUID | None = None
    year_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one_target(self) -> GenerationTarget:
        chosen = {
            "student": self.student_id,
            "section": self.section_id,
            "level": self.level_id,
        }[self.type]
        if chosen is None:
            raise ValueError(f"{self.type}_id is required for a {self.type} target")
        extras = [
            field
            for field, value in (
                ("student_id", self.student_id),
                ("section_id", self.section_id),
                ("level_id", self.level_id),
            )
            if value is not None and field != f"{self.type}_id"
        ]
        if extras:
            raise ValueError(f"{', '.join(extras)} is not allowed for a {self.type} target")
        return self


class DocumentGenerationRequest(BaseModel):
    """Generate from a published version; defaults to the latest one."""

    model_config = ConfigDict(extra="forbid")

    template_id: uuid.UUID
    version_id: uuid.UUID | None = None
    target: GenerationTarget
    combine: bool = False


class DocumentGenerationOut(BaseModel):
    job_id: uuid.UUID
    batch_id: uuid.UUID
    count: int
    status: str


class GenerationYearOut(BaseModel):
    id: str
    code: str
    name: str
    is_current: bool


class GenerationLevelOut(BaseModel):
    id: str
    code: str
    name: str
    name_am: str | None = None


class GenerationSectionOut(BaseModel):
    id: str
    year_id: str
    level_id: str
    code: str
    name: str | None = None


class GenerationTargetsOut(BaseModel):
    year: GenerationYearOut | None = None
    levels: list[GenerationLevelOut] = Field(default_factory=list)
    sections: list[GenerationSectionOut] = Field(default_factory=list)


class GenerationStudentOut(BaseModel):
    id: str
    student_number: str
    full_name: str
    level_name: str | None = None
    section_code: str | None = None


class GenerationStudentList(BaseModel):
    items: list[GenerationStudentOut] = Field(default_factory=list)


class GenerationBatchOut(BaseModel):
    id: str
    template_id: str
    template_name: str
    template_version_id: str
    template_version_number: int
    mode: str
    combine: bool
    count: int
    issued_count: int
    failed_count: int
    progress: int
    status: str
    approval_required: bool = False
    requested_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    file_id: str | None = None
    download_url: str | None = None
    failure_summary: str | None = None
    created_at: datetime
    issued_at: datetime | None = None


class BatchDecision(BaseModel):
    """An approver's note, or the reason a certificate batch was rejected."""

    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(None, max_length=500)


class BatchRejection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class GenerationBatchList(BaseModel):
    items: list[GenerationBatchOut] = Field(default_factory=list)


class IssuedDocumentSummary(BaseModel):
    id: str
    number: str
    verification_code: str
    template_id: str
    template_name: str
    doc_type: str
    template_version_number: int
    recipient_type: str
    recipient_id: str | None = None
    recipient_name: str
    batch_id: str | None = None
    file_id: str | None = None
    download_url: str | None = None
    issued_at: datetime


class IssuedDocumentDetail(IssuedDocumentSummary):
    layout: dict[str, Any]
    data_snapshot: dict[str, Any]


class IssuedDocumentList(BaseModel):
    items: list[IssuedDocumentSummary] = Field(default_factory=list)
    next_cursor: str | None = None
    total: int | None = None


class ReprintOut(BaseModel):
    """The stored artifact behind a reprint, with a short-lived download URL."""

    id: str
    number: str
    file_id: str | None = None
    url: str | None = None
    checksum_sha256: str | None = None


class FileLinkOut(BaseModel):
    """A short-lived link to a stored artifact (a batch's combined PDF)."""

    file_id: str | None = None
    filename: str | None = None
    url: str | None = None
    checksum_sha256: str | None = None


class DocumentVerificationOut(BaseModel):
    """The deliberately small public view of an issued document.

    This is what a QR code reveals: enough to confirm the paper is genuine,
    never the snapshot, marks, guardian or address behind it.
    """

    valid: bool
    number: str
    doc_type: DocType
    recipient_name: str
    issued_at: datetime
    school_name: str | None = None


class TemplateFileTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    doc_type: DocType


class TemplateFileVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_number: int = Field(ge=1)
    status: VersionStatus
    change_note: str | None = Field(default=None, max_length=500)
    published_at: datetime | None = None
    layout: dict[str, Any]


class TemplateFile(BaseModel):
    """The deterministic export format; import accepts exactly this shape."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["school-erp.doc-template"]
    format_version: Literal[1]
    exported_at: datetime | None = None
    template: TemplateFileTemplate
    versions: list[TemplateFileVersion] = Field(min_length=1)


__all__ = [
    "BatchDecision",
    "BatchRejection",
    "DocType",
    "DocumentFieldOut",
    "DocumentFieldsOut",
    "DocumentFormatOptions",
    "DocumentGenerationOut",
    "DocumentGenerationRequest",
    "DocumentVerificationOut",
    "FileLinkOut",
    "GenerationBatchList",
    "GenerationBatchOut",
    "GenerationLevelOut",
    "GenerationSectionOut",
    "GenerationStudentList",
    "GenerationStudentOut",
    "GenerationTarget",
    "GenerationTargetsOut",
    "GenerationYearOut",
    "IssuedDocumentDetail",
    "IssuedDocumentList",
    "IssuedDocumentSummary",
    "ReprintOut",
    "StarterList",
    "StarterOut",
    "TemplateCreate",
    "TemplateDeleted",
    "TemplateDetail",
    "TemplateDuplicate",
    "TemplateFile",
    "TemplateFileTemplate",
    "TemplateFileVersion",
    "TemplateList",
    "TemplateSummary",
    "TemplateUpdate",
    "VersionCreate",
    "VersionDetail",
    "VersionList",
    "VersionSave",
    "VersionStatus",
    "VersionSummary",
]
