from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from controller_api.db import Database
from controller_api.directory import SlidingWindowLimiter
from controller_api.errors import ControllerError, controller_error_handler
from controller_api.keys import ensure_signing_keys
from controller_api.routers import auth, directory, link, schools, vault
from controller_api.settings import ControllerSettings, get_controller_settings

logger = logging.getLogger("controller")
ROUTERS = [auth.router, schools.router, link.router, vault.router, directory.router]


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:20]}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def create_controller_app(settings: ControllerSettings | None = None) -> FastAPI:
    settings = settings or get_controller_settings()
    logging.basicConfig(level=logging.INFO)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.auto_create_schema:
            await app.state.db.create_all()
        async with app.state.db.session() as session:
            await ensure_signing_keys(session, settings)
            await session.commit()
        yield
        await app.state.db.dispose()

    app = FastAPI(
        title="School ERP Control Plane",
        version=settings.app_version,
        openapi_url="/controller/v1/openapi.json",
        docs_url="/controller/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = Database(settings.controller_database_url)
    app.state.directory_limiter = SlidingWindowLimiter(settings.directory_rate_limit_per_minute)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(ControllerError, controller_error_handler)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message_key": "error.internal_error",
                    "message": "An unexpected error occurred",
                    "details": None,
                    "request_id": getattr(request.state, "request_id", ""),
                }
            },
        )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "controller-api"}

    @app.get("/ready")
    async def ready() -> dict:
        return {"status": "ok", "service": "controller-api"}

    for router in ROUTERS:
        app.include_router(router)
    return app
