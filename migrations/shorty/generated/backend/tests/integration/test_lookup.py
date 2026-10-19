# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-05, BR-C-06, BR-C-07, BR-C-08
# LEGACY: source/shorty.php:272, 281-284, 373-393
# COMPONENT: tests/integration/test_lookup
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Integration tests for R2 (GET /?q=) and R3 (GET /{code}).

BR-C-05: single-row read by decoded id.
BR-C-06: unknown / malformed code → 404.
BR-C-07: 301 redirect with Location header.
BR-C-08: empty url falls through to lookup.
"""

from __future__ import annotations

import pytest

from app.modules.urls.encode import EncoderConfig, encode


pytestmark = pytest.mark.asyncio


DEFAULT_CHARS = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
)


class TestLookupRoute:
    async def test_BR_C_05_valid_code_redirects(self, client):
        # Seed: create a URL, then look up its short code via path-style R3.
        created = await client.get(
            "/?url=http://lookup.test/a&format=text"
        )
        assert created.status_code == 200
        short = created.text
        code = short.rsplit("/", 1)[-1]

        resp = await client.get(f"/{code}", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers["location"] == "http://lookup.test/a"

    async def test_BR_C_05_seeded_url_resolves(self, client, seeded_urls):
        """Use the canonical `seeded_urls` fixture (Planning §11.3) — row
        id=42 has a stable encode(); verify path lookup resolves it."""
        cfg = EncoderConfig(chars=DEFAULT_CHARS, salt="", padding=3)
        code = encode(42, cfg)  # PHP-verified: encode(42)="Q"
        assert code == "Q"

        resp = await client.get(f"/{code}", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers["location"] == "https://example.com/forty-two"

    async def test_BR_C_05_slash_strip(self, client, seeded_urls):
        """Legacy `q=Q/` (with slash) → strip → 'Q' → seeded id=42 row."""
        resp = await client.get("/?q=Q/", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers["location"] == "https://example.com/forty-two"

    async def test_BR_C_07_redirect_status_301(self, client):
        created = await client.get(
            "/?url=http://redirect.test/&format=text"
        )
        code = created.text.rsplit("/", 1)[-1]
        resp = await client.get(f"/{code}", follow_redirects=False)
        assert resp.status_code == 301

    async def test_BR_C_07_location_header(self, client):
        """Location header MUST equal the stored URL byte-for-byte."""
        stored = "https://redirect.test/path?x=1&y=2"
        # Pass `url` via httpx params= so the `&` inside the stored URL is
        # properly percent-encoded instead of parsed as a query-param boundary.
        created = await client.get(
            "/",
            params={"url": stored, "format": "text"},
            follow_redirects=False,
        )
        assert created.status_code == 200
        code = created.text.rsplit("/", 1)[-1]

        resp = await client.get(f"/{code}", follow_redirects=False)
        assert resp.status_code == 301
        assert resp.headers["location"] == stored


class TestLookupEdgeCases:
    async def test_BR_C_06_unknown_code_404(self, client):
        # `zzzzzz` decodes to a number with no matching row.
        resp = await client.get("/zzzzzz", follow_redirects=False)
        assert resp.status_code == 404

    async def test_BR_C_06_malformed_code_404(self, client):
        # Path regex `^[a-zA-Z0-9]+$` rejects '-' → router returns 404.
        resp = await client.get("/abc-def", follow_redirects=False)
        assert resp.status_code == 404

    async def test_BR_C_05_overflow_returns_404(self, client):
        # Very long code → decodes to integer > INT32_MAX → 404 (OQ-C-03).
        resp = await client.get(
            "/aaaaaaaaaaaaaaaaaaaaaaaa", follow_redirects=False
        )
        assert resp.status_code == 404

    async def test_BR_C_08_q_param_with_slash_stripped(self, client):
        # Legacy `q=abc/def` → strips `/` then decodes `abcdef`.
        # If `abcdef` doesn't exist → 404; we only assert the route shape.
        resp = await client.get(
            "/?q=abc/def", follow_redirects=False
        )
        # Either 301 (unlikely without seed) or 404 — what we want is "not 500".
        assert resp.status_code in (301, 404)

    async def test_BR_C_08_empty_url_falls_through_to_lookup(self, client):
        # url empty + q absent → 404.
        resp = await client.get("/?url=", follow_redirects=False)
        assert resp.status_code == 404


class TestStoredUrlCorrupt:
    """BR-C-07 / RF-06 / OQ-C-02 — stored-URL re-validation failure → HTTP 500.

    A row whose `url` no longer matches the legacy regex (data corruption /
    tamper) must abort the redirect and yield HTTP 500 with the
    `shorty/internal` problem type. This is the StoredUrlCorrupt path
    introduced in revision-001.
    """

    async def test_BR_C_07_tampered_url_500(
        self, client, app_instance, db_session_factory
    ):
        """Insert a row with an invalid URL (bypassing schema validation),
        then look it up — the service's re-validation MUST raise
        StoredUrlCorrupt → 500."""
        from sqlalchemy import insert as _insert

        from app.modules.urls.models import Url

        bad_url = "javascript:alert(1)"  # fails ^http[s]?://\w+

        async with db_session_factory() as db:
            await db.execute(_insert(Url).values(id=7777, url=bad_url))
            await db.commit()

        cfg = EncoderConfig(chars=DEFAULT_CHARS, salt="", padding=3)
        code = encode(7777, cfg)

        resp = await client.get(f"/{code}", follow_redirects=False)
        assert resp.status_code == 500, (
            f"Tampered/corrupt stored URL must yield 500, got {resp.status_code}"
        )
        body = resp.json()
        assert body.get("type") == "shorty/internal"
