# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-09
# LEGACY: source/shorty.php:347-366
# COMPONENT: tests/unit/test_formatting
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Byte-level tests for formatting.render() — BR-C-09.

The dual-run harness compares these bytes against the legacy PHP output;
the spacing, newlines, and escape semantics here are the parity contract.
"""

from __future__ import annotations

import json

from app.modules.urls.formatting import (
    render,
    render_html,
    render_json,
    render_text,
    render_xml,
)
from app.modules.urls.schemas import OutputFormat


SHORT = "http://test/b"


class TestFormatNegotiation:
    def test_BR_C_09_text_body_and_type(self):
        resp = render_text(SHORT)
        assert resp.body == SHORT.encode("utf-8")
        assert resp.media_type == "text/plain; charset=utf-8"

    def test_BR_C_09_json_body_shape(self):
        resp = render_json(SHORT)
        # JSONResponse renders an inner dict — decode and compare structurally.
        assert json.loads(resp.body.decode("utf-8")) == {"url": SHORT}
        assert resp.media_type == "application/json"

    def test_BR_C_09_xml_body_byte_for_byte(self):
        resp = render_xml(SHORT)
        expected = (
            '<?xml version="1.0"?>'
            "\n<response>"
            f"\n  <url>{SHORT}</url>"
            "\n</response>"
        )
        assert resp.body.decode("utf-8") == expected
        assert resp.media_type == "application/xml"

    def test_BR_C_09_xml_escapes_amp(self):
        resp = render_xml("http://a&b")
        assert b"&amp;" in resp.body
        assert b"<url>http://a&amp;b</url>" in resp.body

    def test_BR_C_09_html_anchor_default_branch(self):
        resp = render_html(SHORT)
        # html.escape with quote=True replaces &, <, >, " and '.
        assert resp.body == f'<a href="{SHORT}">{SHORT}</a>'.encode("utf-8")

    def test_BR_C_09_html_escapes_attribute(self):
        # The legacy PHP did NOT escape — RF-04 mitigation adds escaping.
        resp = render_html('http://a"><script>')
        body = resp.body.decode("utf-8")
        assert "&quot;" in body
        assert "<script>" not in body  # raw script must not appear

    def test_BR_C_09_render_dispatch_text(self):
        assert render(SHORT, OutputFormat.TEXT).media_type.startswith("text/plain")

    def test_BR_C_09_render_dispatch_json(self):
        assert render(SHORT, OutputFormat.JSON).media_type == "application/json"

    def test_BR_C_09_render_dispatch_xml(self):
        assert render(SHORT, OutputFormat.XML).media_type == "application/xml"

    def test_BR_C_09_render_dispatch_html_default(self):
        resp = render(SHORT, OutputFormat.HTML)
        # HTMLResponse media_type defaults to text/html; charset=utf-8.
        assert resp.media_type.startswith("text/html")
