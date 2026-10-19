# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-01, BR-C-02, BR-C-03, BR-C-04, BR-C-05, BR-C-06, BR-C-07, BR-C-08, BR-C-09
# LEGACY: source/shorty.php:311-394
# COMPONENT: modules/urls/router
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
FastAPI APIRouter for the urls module — R1..R5.

Routing precedence:
  R3 `GET /{code}`     — path-style lookup; alphanumeric path regex.
  R5 `GET /healthz`    — liveness probe.
  R4 `POST /shorten`   — REST alias for create.
  R1 `GET /`           — composite: create if url present, else lookup, else 404.

`/{code}` must be declared LAST among GETs so static paths like `/healthz`
take precedence. FastAPI evaluates routes in declaration order.

The router never imports `sqlalchemy` directly — it only depends on the
`AsyncSession` type alias from `sqlalchemy.ext.asyncio` (a typing surface,
not a query construction surface). All query logic lives in UrlService.
"""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession  # typing-only surface

from app.core.config import Settings
from app.db.engine import get_db_session

from .dependencies import (
    get_client_ip,
    get_settings,
    get_url_service,
    require_ip_allowed,
)
from .errors import BadUrl, UrlNotFound
from .formatting import render
from .schemas import (
    CreateUrlRequest,
    HealthResponse,
    LEGACY_URL_REGEX,
    OutputFormat,
)
from .service import UrlService

router = APIRouter()

_LEGACY_RE = re.compile(LEGACY_URL_REGEX)


# ─────────────────────────────────────────────────────────────────────────────
# R5 — Health probe (declared first so it never collides with `/{code}`)


@router.get("/healthz", response_model=HealthResponse)
async def healthz(
    service: Annotated[UrlService, Depends(get_url_service)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> HealthResponse:
    """Liveness probe — delegates DB check to UrlService.ping (OQ-P-02).

    Always returns 200; the response body indicates db health.
    """
    db_status = "ok" if await service.ping(db) else "down"
    return HealthResponse(status="ok", db=db_status)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# R4 — POST /shorten (REST alias)


@router.post("/shorten")
async def shorten(
    body: CreateUrlRequest,
    request: Request,
    service: Annotated[UrlService, Depends(get_url_service)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _ip_gate: Annotated[None, Depends(require_ip_allowed)] = None,
) -> Response:
    """REST alias for the create flow; identical semantics to R1 create branch."""
    result = await service.create_or_get(body.url, db)
    fmt = OutputFormat.parse(body.format)
    return render(result.short_url, fmt)


# ─────────────────────────────────────────────────────────────────────────────
# R1 + R2 — Composite GET / (create OR lookup OR 404)


@router.get("/")
async def root_handler(
    request: Request,
    service: Annotated[UrlService, Depends(get_url_service)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    client_ip: Annotated[str, Depends(get_client_ip)],
    url: Annotated[str | None, Query(max_length=2048)] = None,
    q: Annotated[str | None, Query(max_length=32)] = None,
    format: Annotated[str | None, Query(max_length=16)] = None,
) -> Response:
    """Composite endpoint matching legacy `index.php` dispatch (BR-C-08).

    Decision tree:
      url non-empty → create (whitelist enforced)
      url empty/absent + q non-empty → lookup (slash-stripped)
      neither → 404
    """
    if url:
        # Whitelist gate for create — replicates RF-05/BR-C-04. Done inline
        # rather than via Depends so the lookup branch is exempt (lookup is
        # always open per BR-C-04). `settings` and `client_ip` are already
        # resolved by FastAPI's Depends chain above so dependency_overrides
        # for both are honoured under test.
        require_ip_allowed(settings, client_ip)

        # BR-C-02: re-validate against the legacy regex even though the
        # query type doesn't run Pydantic's pattern check.
        if _LEGACY_RE.match(url) is None:
            raise BadUrl()

        result = await service.create_or_get(url, db)
        fmt = OutputFormat.parse(format)
        return render(result.short_url, fmt)

    if q:
        # Legacy slash-strip: str_replace('/', '', $_GET['q'])
        stripped = q.replace("/", "")
        if not stripped:
            raise UrlNotFound()
        # Path-style regex (alphanumeric only) enforced manually.
        if not re.match(r"^[a-zA-Z0-9]+$", stripped):
            raise UrlNotFound()
        url_row = await service.lookup_and_redirect(stripped, db)
        return RedirectResponse(url=url_row.url, status_code=301)

    # Neither url nor q → 404.
    raise UrlNotFound()


# ─────────────────────────────────────────────────────────────────────────────
# R3 — GET /{code} (path-style lookup; declared last so static GETs win)


@router.get("/{code}")
async def lookup_by_path(
    code: Annotated[
        str,
        Path(..., min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9]+$"),
    ],
    service: Annotated[UrlService, Depends(get_url_service)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Path-style lookup. Pydantic-Path regex enforces alphanumeric; the
    global RequestValidationError handler maps failures to 404 (RF-08)."""
    url_row = await service.lookup_and_redirect(code, db)
    return RedirectResponse(url=url_row.url, status_code=301)


# Helper used by JSONResponse error replies elsewhere (kept here for symmetry).
def _problem(detail: str, type_: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        content={"detail": detail, "type": type_}, status_code=status_code
    )
