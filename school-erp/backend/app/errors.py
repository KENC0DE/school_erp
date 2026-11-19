from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base error carrying the stable API error contract (ARCH §5.1)."""

    status_code = 400
    code = "BAD_REQUEST"
    default_message_key: str | None = None

    def __init__(
        self,
        message: str | None = None,
        *,
        message_key: str | None = None,
        details: Any = None,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        self.message = message or self.code.replace("_", " ").title()
        self.message_key = message_key or self.default_message_key or f"error.{self.code.lower()}"
        self.details = details
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        super().__init__(self.message)


class NotFound(AppError):
    status_code = 404
    code = "NOT_FOUND"


class Unauthorized(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class Forbidden(AppError):
    status_code = 403
    code = "PERMISSION_DENIED"


class ModuleDisabled(AppError):
    status_code = 403
    code = "MODULE_DISABLED"


class Conflict(AppError):
    status_code = 409
    code = "CONFLICT"


class VersionConflict(Conflict):
    """A stale ``row_version`` was sent; ``details`` carries the current state."""

    default_message_key = "error.version_conflict"


class IdempotencyKeyReused(Conflict):
    """The same Idempotency-Key was sent with a different request body."""

    code = "IDEMPOTENCY_KEY_REUSED"


class IdempotencyInProgress(Conflict):
    """Another request with the same Idempotency-Key is still running."""

    code = "IDEMPOTENCY_IN_PROGRESS"


class ValidationFailed(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class InvalidCursor(ValidationFailed):
    code = "INVALID_CURSOR"


class InvalidSort(ValidationFailed):
    code = "INVALID_SORT"


class InvalidFilter(ValidationFailed):
    code = "INVALID_FILTER"


class VersionRequired(ValidationFailed):
    code = "VERSION_REQUIRED"


class RateLimited(AppError):
    status_code = 429
    code = "RATE_LIMITED"


class AccountLocked(AppError):
    status_code = 423
    code = "ACCOUNT_LOCKED"


class TOTPRequired(Unauthorized):
    code = "TOTP_REQUIRED"


class TOTPInvalid(Unauthorized):
    code = "TOTP_INVALID"


class TOTPEnrollmentRequired(Forbidden):
    code = "TOTP_ENROLLMENT_REQUIRED"


class TOTPRequiredByRole(Forbidden):
    code = "TOTP_REQUIRED_BY_ROLE"


class CSRFFailed(Forbidden):
    code = "CSRF_FAILED"


def error_body(*, code: str, message_key: str, message: str, details: Any, request_id: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message_key": message_key,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(
            code=exc.code,
            message_key=exc.message_key,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        ),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=500,
        content=error_body(
            code="INTERNAL_ERROR",
            message_key="error.internal_error",
            message="An unexpected error occurred",
            details=None,
            request_id=request_id,
        ),
    )
