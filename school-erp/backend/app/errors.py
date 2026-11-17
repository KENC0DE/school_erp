from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base error carrying the stable API error contract (ARCH §5.1)."""

    status_code = 400
    code = "BAD_REQUEST"

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
        self.message_key = message_key or f"error.{self.code.lower()}"
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


class ValidationFailed(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class RateLimited(AppError):
    status_code = 429
    code = "RATE_LIMITED"


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
