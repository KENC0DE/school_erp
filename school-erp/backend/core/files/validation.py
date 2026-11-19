"""Upload validation: type, size and content sniffing (P1-22).

The browser-declared MIME type is never trusted on its own. Every upload must
have an allowed extension, a matching declared type (or octet-stream) and a
body whose magic bytes agree. SVG is deliberately excluded because it can
carry scripts, and private student documents must not become an XSS vector.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.errors import ValidationFailed
from PIL import Image, UnidentifiedImageError

# extension -> (canonical mime, kind)
ALLOWED_TYPES: dict[str, tuple[str, str]] = {
    ".png": ("image/png", "image"),
    ".jpg": ("image/jpeg", "image"),
    ".jpeg": ("image/jpeg", "image"),
    ".webp": ("image/webp", "image"),
    ".pdf": ("application/pdf", "pdf"),
    ".csv": ("text/csv", "text"),
    ".txt": ("text/plain", "text"),
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx",
    ),
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsx",
    ),
}

IMAGE_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
MAX_IMAGE_PIXELS = 40_000_000


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    extension: str
    mime: str
    kind: str
    data: bytes

    @property
    def is_image(self) -> bool:
        return self.kind == "image"


def safe_filename(name: str | None) -> str:
    candidate = Path((name or "").replace("\\", "/")).name
    candidate = candidate.replace("\x00", "").strip()
    if not candidate or candidate in {".", ".."}:
        candidate = "upload"
    return candidate[:255]


def _unsupported(name: str, declared: str | None) -> ValidationFailed:
    return ValidationFailed(
        "This file type is not allowed",
        message_key="error.file.unsupported_type",
        details={
            "filename": name,
            "content_type": declared,
            "allowed": sorted(ALLOWED_TYPES),
        },
        status_code=415,
    )


def _check_declared(name: str, declared: str | None, expected: str) -> None:
    if not declared:
        return
    normalized = declared.split(";", 1)[0].strip().lower()
    if normalized in {"application/octet-stream", "binary/octet-stream", ""}:
        return
    if normalized != expected:
        raise ValidationFailed(
            "The declared file type does not match its extension",
            message_key="error.file.content_mismatch",
            details={"filename": name, "content_type": normalized, "expected": expected},
            status_code=415,
        )


def _check_image(name: str, data: bytes, expected: str) -> None:
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValidationFailed(
                    "The image is too large to process",
                    message_key="error.file.image_too_large",
                    details={"width": image.width, "height": image.height},
                    status_code=413,
                )
            actual = image.format
            image.verify()
    except ValidationFailed:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationFailed(
            "The file is not a readable image",
            message_key="error.file.content_mismatch",
            details={"filename": name},
            status_code=415,
        ) from exc
    if actual != IMAGE_FORMATS[expected]:
        raise ValidationFailed(
            "The file contents do not match its extension",
            message_key="error.file.content_mismatch",
            details={"filename": name, "detected": actual, "expected": IMAGE_FORMATS[expected]},
            status_code=415,
        )


def _check_zip(name: str, data: bytes, marker: str) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValidationFailed(
            "The office document is not a valid archive",
            message_key="error.file.content_mismatch",
            details={"filename": name},
            status_code=415,
        ) from exc
    if marker not in names:
        raise ValidationFailed(
            "The office document contents do not match its extension",
            message_key="error.file.content_mismatch",
            details={"filename": name, "missing": marker},
            status_code=415,
        )


def _check_text(name: str, data: bytes) -> None:
    if b"\x00" in data:
        raise ValidationFailed(
            "The file is not plain text",
            message_key="error.file.content_mismatch",
            details={"filename": name},
            status_code=415,
        )
    try:
        data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationFailed(
            "The text file must be UTF-8",
            message_key="error.file.content_mismatch",
            details={"filename": name, "offset": exc.start},
            status_code=415,
        ) from exc


def validate_upload(
    filename: str | None,
    declared: str | None,
    data: bytes,
    *,
    max_bytes: int,
) -> ValidatedUpload:
    name = safe_filename(filename)
    if not data:
        raise ValidationFailed(
            "The file is empty",
            message_key="error.file.empty",
            status_code=422,
        )
    if len(data) > max_bytes:
        raise ValidationFailed(
            "The file is larger than the upload limit",
            message_key="error.file.too_large",
            details={"size": len(data), "max_bytes": max_bytes},
            status_code=413,
        )
    extension = Path(name).suffix.lower()
    entry = ALLOWED_TYPES.get(extension)
    if entry is None:
        raise _unsupported(name, declared)
    expected, kind = entry
    _check_declared(name, declared, expected)
    if kind == "image":
        _check_image(name, data, expected)
    elif kind == "pdf":
        if not data.startswith(b"%PDF-"):
            raise ValidationFailed(
                "The file is not a PDF",
                message_key="error.file.content_mismatch",
                details={"filename": name},
                status_code=415,
            )
    elif kind == "docx":
        _check_zip(name, data, "word/document.xml")
    elif kind == "xlsx":
        _check_zip(name, data, "xl/workbook.xml")
    else:
        _check_text(name, data)
    return ValidatedUpload(
        filename=name,
        extension=extension,
        mime=expected,
        kind=kind,
        data=data,
    )


__all__ = ["ALLOWED_TYPES", "ValidatedUpload", "safe_filename", "validate_upload"]
