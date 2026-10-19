# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-09
# LEGACY: source/shorty.php:347-366
# COMPONENT: modules/urls/formatting
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Render the create-response in one of four formats (BR-C-09).

Pure functions — no I/O, no DB. Stdlib only (html for escape).
The byte content is part of the dual-run parity contract; do not alter
spacing/newlines in the XML or HTML output.

RF-10 fix: `text` response sets `Content-Type: text/plain; charset=utf-8`
explicitly (legacy PHP did not).
"""

from __future__ import annotations

import html
import json as _json

from fastapi.responses import HTMLResponse, JSONResponse, Response

from .schemas import OutputFormat


def render(short_url: str, fmt: OutputFormat) -> Response:
    """Dispatch on OutputFormat and return the appropriate FastAPI Response."""
    if fmt is OutputFormat.TEXT:
        return render_text(short_url)
    if fmt is OutputFormat.JSON:
        return render_json(short_url)
    if fmt is OutputFormat.XML:
        return render_xml(short_url)
    # HTML (default + unknown — already coerced by OutputFormat.parse).
    return render_html(short_url)


def render_text(short_url: str) -> Response:
    """Plain text — single line, no trailing newline (matches PHP `exit($url)`).

    RF-10 fix: set media_type explicitly so clients see text/plain.
    """
    return Response(
        content=short_url,
        media_type="text/plain; charset=utf-8",
    )


def render_json(short_url: str) -> JSONResponse:
    """`{"url": "<short_url>"}` — JSONResponse handles content-type."""
    return JSONResponse(content={"url": short_url})


def render_xml(short_url: str) -> Response:
    """XML body, byte-identical to PHP shorty.php:355-362.

    Format:
        <?xml version="1.0"?>
        <response>
          <url>{html-escaped}</url>
        </response>
    """
    body = (
        '<?xml version="1.0"?>'
        "\n<response>"
        f"\n  <url>{html.escape(short_url)}</url>"
        "\n</response>"
    )
    return Response(content=body, media_type="application/xml")


def render_html(short_url: str) -> HTMLResponse:
    """Default anchor: `<a href="...">...</a>` — both attribute and text
    HTML-escaped to defuse stored XSS (BR-C-09 + RF-04 mitigation)."""
    escaped = html.escape(short_url, quote=True)
    return HTMLResponse(content=f'<a href="{escaped}">{escaped}</a>')


# ── Re-exports for documentation/testing convenience ───────────────────────

__all__ = [
    "render",
    "render_text",
    "render_json",
    "render_xml",
    "render_html",
]

# json is re-exported only so test code can compare bodies without importing
# stdlib json separately; keep the underscore to avoid accidental use.
del _json
