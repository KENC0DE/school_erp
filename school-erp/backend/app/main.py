from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from core.ai.router import router as ai_router
from core.api.idempotency import IdempotencyMiddleware
from core.audit.router import router as audit_router
from core.auth.rate_limit import reset_all as reset_auth_limits
from core.auth.recovery import router as recovery_router
from core.auth.router import router as auth_router
from core.auth.sessions import router as sessions_router
from core.auth.twofa import router as twofa_router
from core.auth.web import router as web_auth_router
from core.bootstrap import bootstrap
from core.custom_fields.router import router as custom_fields_router
from core.db.session import Database
from core.i18n.router import router as i18n_router
from core.jobs.router import router as jobs_router
from core.modules.gating import module_gate
from core.modules.registry import ModuleRegistry
from core.modules.router import router as modules_router
from core.notifications.adapters import build_adapters
from core.people.router import router as people_router
from core.rbac.router import router as rbac_router
from core.settings.router import router as settings_router
from core.themes.router import router as themes_router
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import (
    AppError,
    app_error_handler,
    error_body,
    unhandled_error_handler,
)
from app.health import router as health_router
from app.logging import configure_logging
from app.middleware import RequestContextMiddleware
from app.settings import Settings, get_settings

logger = logging.getLogger("erp.app")

CORE_ROUTERS = [
    auth_router,
    web_auth_router,
    sessions_router,
    twofa_router,
    recovery_router,
    rbac_router,
    audit_router,
    modules_router,
    custom_fields_router,
    people_router,
    i18n_router,
    themes_router,
    settings_router,
    ai_router,
    jobs_router,
]


def create_app(settings: Settings | None = None, registry: ModuleRegistry | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging("INFO" if not settings.dev_mode else "DEBUG")
    registry = registry or ModuleRegistry.load()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        reset_auth_limits()
        if settings.auto_create_schema:
            await app.state.db.create_all()
        await bootstrap(app)
        logger.info("instance started", extra={"event": "startup"})
        yield
        await app.state.db.dispose()

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.registry = registry
    app.state.db = Database(settings.database_url)
    app.state.mailer, app.state.sms = build_adapters(settings)

    # Innermost: it buffers the request body once and records the completed JSON
    # response. CORS and request-id stay outermost so replays still get both.
    app.add_middleware(
        IdempotencyMiddleware,
        database=app.state.db,
        ttl_seconds=settings.idempotency_ttl_seconds,
        enabled=settings.idempotency_enabled,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "ETag"],
    )
    app.add_middleware(RequestContextMiddleware)

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body(
                code="VALIDATION_ERROR",
                message_key="error.validation",
                message="The request is invalid",
                details=exc.errors(),
                request_id=getattr(request.state, "request_id", ""),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "UNAUTHORIZED", 403: "PERMISSION_DENIED", 404: "NOT_FOUND"}.get(
            exc.status_code, "HTTP_ERROR"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                code=code,
                message_key=f"error.{code.lower()}",
                message=str(exc.detail),
                details=None,
                request_id=getattr(request.state, "request_id", ""),
            ),
        )

    app.include_router(health_router)
    for router in CORE_ROUTERS:
        app.include_router(router, prefix="/api/v1")

    for manifest in registry.all():
        if manifest.router is None:
            continue
        app.include_router(
            manifest.router,
            prefix=f"/api/v1/{manifest.key}",
            dependencies=[Depends(module_gate(manifest.key))],
        )

    return app
