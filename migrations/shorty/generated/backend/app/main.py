# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-02, BR-C-04, BR-C-06
# LEGACY: source/index.php, source/shorty.php:311-394
# COMPONENT: main
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
FastAPI app factory + lifespan + middleware + exception handlers.

Middleware order (mandatory per Planning §9.2):
  1. ProxyHeadersMiddleware  — must be first (RF-05 fix; honours XFF only
                               from trusted_proxies).
  2. (CORS — deferred to Phase 5)
  3. (LoggingMiddleware — optional; deferred to Phase 5)

Exception handlers map domain errors to HTTP status codes (RF-09 uplift).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.engine import dispose_engine, init_engine
from app.modules.urls.dependencies import (
    init_url_service,
    set_settings,
)
from app.modules.urls.errors import (
    BadUrl,
    EncodeOverflow,
    IpNotAllowed,
    ShortyError,
    StoredUrlCorrupt,
    UrlNotFound,
)
from app.modules.urls.router import router as urls_router

logger = logging.getLogger("shorty.main")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured FastAPI instance.

    Pass `settings` explicitly for tests; production callers pass nothing
    and let `Settings()` read from the environment.
    """
    if settings is None:
        settings = Settings()

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        configure_logging(settings.log_level, settings.json_logs)
        logger.info(
            "startup",
            extra={
                "event": "startup",
                "chars_len": len(settings.chars),
                "padding": settings.padding,
                "salt_empty": settings.salt_value == "",
            },
        )
        set_settings(settings)
        init_engine(settings)
        init_url_service(settings)
        try:
            yield
        finally:
            await dispose_engine()
            logger.info("shutdown", extra={"event": "shutdown"})

    app = FastAPI(
        title="Shorty",
        version="0.1.0",
        lifespan=_lifespan,
    )

    # Trusted-proxy honouring — RF-05 fix.
    trusted = ",".join(sorted(settings.trusted_proxies)) or "127.0.0.1"
    app.add_middleware(
        ProxyHeadersMiddleware,
        trusted_hosts=trusted,
    )

    # Exception handlers (RF-09 status-code uplift).
    @app.exception_handler(BadUrl)
    async def _h_bad_url(_req: Request, exc: BadUrl) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": exc.detail, "type": exc.type_code},
        )

    @app.exception_handler(IpNotAllowed)
    async def _h_ip_not_allowed(_req: Request, exc: IpNotAllowed) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"detail": exc.detail, "type": exc.type_code},
        )

    @app.exception_handler(UrlNotFound)
    async def _h_not_found(_req: Request, exc: UrlNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": exc.detail, "type": exc.type_code},
        )

    @app.exception_handler(EncodeOverflow)
    async def _h_overflow(_req: Request, exc: EncodeOverflow) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": exc.detail, "type": exc.type_code},
        )

    @app.exception_handler(StoredUrlCorrupt)
    async def _h_stored_corrupt(
        _req: Request, exc: StoredUrlCorrupt
    ) -> JSONResponse:
        # OQ-C-02: stored-URL re-validation failure → 500 (data corruption,
        # not client error). The ERROR log is emitted at the raise site.
        return JSONResponse(
            status_code=500,
            content={"detail": exc.detail, "type": exc.type_code},
        )

    @app.exception_handler(ShortyError)
    async def _h_domain(_req: Request, exc: ShortyError) -> JSONResponse:
        # Catch-all for any new ShortyError subclass.
        return JSONResponse(
            status_code=500,
            content={"detail": exc.detail, "type": exc.type_code},
        )

    @app.exception_handler(RequestValidationError)
    async def _h_validation(
        _req: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        # Path-regex failures on `/{code}` → 404 (RF-08).
        # Query / body validation failures → 400.
        path = _req.url.path
        if path != "/" and not path.startswith("/shorten") and path != "/healthz":
            return JSONResponse(
                status_code=404,
                content={"detail": "Not Found", "type": "shorty/not-found"},
            )
        return JSONResponse(
            status_code=400,
            content={"detail": "Bad input.", "type": "shorty/bad-input"},
        )

    app.include_router(urls_router, tags=["urls"])
    return app


# ASGI entrypoint — uvicorn loads `app.main:app`.
# Built once at import; all Settings fields have safe defaults, so this is
# safe to evaluate in test collection too. Tests build their own app via
# create_app(test_settings) and rely on dependency_overrides.
app = create_app()
