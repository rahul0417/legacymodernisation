# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-04
# LEGACY: source/shorty.php:328-330
# COMPONENT: modules/urls/dependencies
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
FastAPI Depends() providers for the urls module.

`get_settings` — module-level singleton (built at startup, never reloads in
                 Phase 1; no lru_cache needed).
`get_client_ip` — resolves the real client IP after uvicorn's
                  ProxyHeadersMiddleware has rewritten request.client.host
                  from the X-Forwarded-For chain (BR-C-04, RF-05 fix).
`require_ip_allowed` — gate dependency that raises IpNotAllowed if the
                       resolved IP is not in the (non-empty) whitelist.
`get_url_service` — module-level singleton service instance.
"""

from __future__ import annotations

import logging

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings
from app.db.engine import get_session_factory

from .errors import IpNotAllowed
from .service import UrlService

_settings_singleton: Settings | None = None
_service_singleton: UrlService | None = None


def set_settings(settings: Settings) -> None:
    """Install the application Settings (called from create_app lifespan)."""
    global _settings_singleton
    _settings_singleton = settings


def get_settings() -> Settings:
    """Return the live Settings singleton."""
    if _settings_singleton is None:
        raise RuntimeError("Settings not initialised — call set_settings first.")
    return _settings_singleton


def get_client_ip(request: Request) -> str:
    """Resolve the real client IP.

    Relies on uvicorn's ProxyHeadersMiddleware having already rewritten
    `request.client.host` based on `X-Forwarded-For`. When deployed without
    a trusted proxy, this falls back to the direct socket IP.
    """
    client = request.client
    if client is None:
        return "0.0.0.0"
    return client.host


def require_ip_allowed(
    settings: Annotated[Settings, Depends(get_settings)],
    client_ip: Annotated[str, Depends(get_client_ip)],
) -> None:
    """Raise IpNotAllowed if whitelist is non-empty and resolved IP not in it.

    Empty whitelist = open mode (every IP allowed).

    Both inputs flow through `Depends(...)` so `dependency_overrides` for
    `get_settings` and `get_client_ip` are honoured under test, AND so the
    inline call from `root_handler` can pass already-resolved values.
    """
    whitelist = settings.ip_whitelist
    if not whitelist:
        return  # open
    if client_ip not in whitelist:
        raise IpNotAllowed()


def init_url_service(settings: Settings) -> UrlService:
    """Build and install the singleton UrlService (called from lifespan)."""
    global _service_singleton
    logger = logging.getLogger("shorty.urls.service")
    _service_singleton = UrlService(
        cfg=settings.encoder_config,
        hostname=settings.hostname,
        logger=logger,
        session_factory=get_session_factory(),
    )
    return _service_singleton


def get_url_service() -> UrlService:
    """Return the singleton UrlService."""
    if _service_singleton is None:
        raise RuntimeError(
            "UrlService not initialised — call init_url_service first."
        )
    return _service_singleton
