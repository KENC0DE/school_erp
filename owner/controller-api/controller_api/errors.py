from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ControllerError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def unauthorized(message: str) -> ControllerError:
    return ControllerError(401, "UNAUTHORIZED", message)


def forbidden(message: str) -> ControllerError:
    return ControllerError(403, "FORBIDDEN", message)


def not_found(message: str = "Not found") -> ControllerError:
    return ControllerError(404, "NOT_FOUND", message)


def conflict(message: str) -> ControllerError:
    return ControllerError(409, "CONFLICT", message)


def rate_limited(message: str = "Too many requests") -> ControllerError:
    return ControllerError(429, "RATE_LIMITED", message)


def error_body(code: str, message: str, request_id: str, details: Any = None) -> dict:
    return {
        "error": {
            "code": code,
            "message_key": f"error.{code.lower()}",
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }


async def controller_error_handler(request: Request, exc: ControllerError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content=error_body(exc.code, exc.message, getattr(request.state, "request_id", "")),
    )
