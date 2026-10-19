# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-07, BR-C-09, BR-C-11
# LEGACY: source/index.php, source/addAction.php, source/editAction.php, source/delete.php
# COMPONENT: main
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""
FastAPI app factory + lifespan + middleware + exception handlers.

Exception-handler contract (Planning §7.6):
  UserNotFound            → 404 ProblemDetail (title="User not found")
  EmailAlreadyExists      → 409 ProblemDetail (title="Email already exists")
  RequestValidationError  → 422 ProblemDetail with errors[] from exc.errors()
  Exception (fallback)    → 500 ProblemDetail (no stack-trace leakage)

CORS is permissive for the Vite dev origin by default and locked-down
in production via `CRUD_CORS_ORIGINS`. `allow_credentials=False` because
this MWU has no auth (Gate-1 OQ-005).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.engine import dispose_engine, init_engine

from app.modules.users.dependencies import (
    init_user_service,
    set_settings,
)
from app.modules.users.errors import (
    EmailAlreadyExists,
    UserNotFound,
    UsersError,
)
from app.modules.users.router import router as users_router
from app.modules.users.schemas import HealthResponse, ProblemDetail

logger = logging.getLogger("crud.main")

_PROBLEM_CONTENT_TYPE = "application/problem+json"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured FastAPI instance.

    Tests pass `settings` explicitly; production callers pass nothing
    and let `Settings()` read from the environment.
    """
    if settings is None:
        settings = Settings()

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        configure_logging(settings.log_level, settings.json_logs)
        logger.info(
            "startup",
            extra={
                "event": "startup",
                "cors_origins": settings.cors_origins,
                "api_prefix": settings.api_prefix,
                "version": settings.version,
            },
        )
        set_settings(settings)
        init_engine(settings)
        init_user_service()
        try:
            yield
        finally:
            await dispose_engine()
            logger.info("shutdown", extra={"event": "shutdown"})

    app = FastAPI(
        title="CRUD Users",
        version=settings.version,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )

    # ── CORS ───────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # OQ-005: no auth → no cookies
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )

    # ── Exception handlers ─────────────────────────────────────────────────

    def _problem_response(
        problem: ProblemDetail,
        request: Request | None = None,
    ) -> JSONResponse:
        body = problem.model_dump(mode="json")
        if request is not None and problem.instance is None:
            body["instance"] = str(request.url.path)
        return JSONResponse(
            content=body,
            status_code=problem.status,
            media_type=_PROBLEM_CONTENT_TYPE,
        )

    @app.exception_handler(UserNotFound)
    async def _h_not_found(request: Request, exc: UserNotFound) -> JSONResponse:
        problem = ProblemDetail(
            title=exc.title,
            status=exc.status,
            detail=exc.detail,
            instance=str(request.url.path),
        )
        return _problem_response(problem)

    @app.exception_handler(EmailAlreadyExists)
    async def _h_conflict(
        request: Request, exc: EmailAlreadyExists
    ) -> JSONResponse:
        problem = ProblemDetail(
            title=exc.title,
            status=exc.status,
            detail=exc.detail,
            instance=str(request.url.path),
        )
        return _problem_response(problem)

    @app.exception_handler(UsersError)
    async def _h_users_error(
        request: Request, exc: UsersError
    ) -> JSONResponse:
        # Catch-all for any future UsersError subclass — never leak stack.
        problem = ProblemDetail(
            title=exc.title or "Internal error",
            status=exc.status or 500,
            detail=exc.detail,
            instance=str(request.url.path),
        )
        return _problem_response(problem)

    @app.exception_handler(RequestValidationError)
    async def _h_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Per Planning §7.6 / Comprehension §4.4 — wrap 422 into the
        # ProblemDetail envelope with a per-field `errors[]`.
        errors = [
            {
                "loc": list(err.get("loc", ())),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        problem = ProblemDetail(
            title="Validation error",
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Request body failed validation.",
            instance=str(request.url.path),
            errors=errors,
        )
        return _problem_response(problem)

    @app.exception_handler(Exception)
    async def _h_unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Catch-all — log at ERROR (with traceback for ops) but DO NOT
        # leak stack trace to the client (RF-008-adjacent hygiene).
        logger.error(
            "unhandled_exception",
            extra={
                "event": "unhandled_exception",
                "path": str(request.url.path),
                "exc_type": type(exc).__name__,
            },
            exc_info=True,
        )
        problem = ProblemDetail(
            title="Internal server error",
            status=500,
            detail="An unexpected error occurred.",
            instance=str(request.url.path),
        )
        return _problem_response(problem)

    # ── Routers ────────────────────────────────────────────────────────────
    app.include_router(users_router)

    # ── Health probe (mounted on app, NOT on the users router) ─────────────
    @app.get(
        "/api/healthz",
        response_model=HealthResponse,
        tags=["health"],
        summary="Liveness probe.",
    )
    async def healthz_route() -> HealthResponse:
        return HealthResponse(version=settings.version)

    return app


# ASGI entrypoint — uvicorn loads `app.main:app`.
# Built once at import; all Settings fields have safe defaults.
app = create_app()
