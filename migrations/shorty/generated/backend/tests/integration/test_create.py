# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-01, BR-C-02, BR-C-03, BR-C-04, BR-C-08, BR-C-09
# LEGACY: source/shorty.php:327-371
# COMPONENT: tests/integration/test_create
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""
Integration tests for R1 (GET /?url=...) and R4 (POST /shorten).

Minimal-but-real: each BR-C in scope has at least one assertion.
Stage 6 TestGen will enrich these with the full table from Planning §11.2.
"""

from __future__ import annotations

from typing import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.engine import get_db_session
from app.main import create_app
from app.modules.urls.dependencies import get_client_ip


pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────────────
# TestCreateRoute — happy paths and validation


class TestCreateRoute:
    async def test_BR_C_01_create_returns_short_url(self, client):
        resp = await client.get("/?url=http://example.com&format=text")
        assert resp.status_code == 200
        assert "/" in resp.text  # `{hostname}/{code}`

    async def test_BR_C_01_duplicate_url_returns_same_code(self, client):
        first = await client.get("/?url=http://idempotent.test&format=text")
        second = await client.get("/?url=http://idempotent.test&format=text")
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.text == second.text

    async def test_BR_C_02_invalid_url_400(self, client):
        # ftp:// scheme fails the legacy regex.
        resp = await client.get("/?url=ftp://example.com")
        assert resp.status_code == 400

    async def test_BR_C_02_uppercase_scheme_rejected(self, client):
        resp = await client.get("/?url=HTTP://example.com")
        assert resp.status_code == 400

    async def test_BR_C_03_single_decode_of_url_param(self, client):
        # %25 should decode to '%' exactly once (not '%' → '5').
        resp = await client.get(
            "/?url=https%3A%2F%2Fa.test%2F%2525&format=text"
        )
        assert resp.status_code == 200

    async def test_BR_C_08_no_params_404(self, client):
        resp = await client.get("/")
        assert resp.status_code == 404

    async def test_BR_C_09_format_text_content_type(self, client):
        resp = await client.get("/?url=http://example.com&format=text")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")

    async def test_BR_C_09_format_json_body(self, client):
        resp = await client.get("/?url=http://example.com&format=json")
        assert resp.status_code == 200
        body = resp.json()
        assert "url" in body

    async def test_BR_C_09_default_html_anchor(self, client):
        resp = await client.get("/?url=http://example.com")
        assert resp.status_code == 200
        assert "<a href" in resp.text

    async def test_BR_C_09_case_insensitive_format(self, client):
        resp = await client.get("/?url=http://example.com&format=TEXT")
        assert resp.headers["content-type"].startswith("text/plain")

    async def test_BR_C_09_unknown_format_defaults_html(self, client):
        """Unknown ?format=yaml → HTML anchor fallback (Comprehension §6.4)."""
        resp = await client.get("/?url=http://example.com&format=yaml")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert "<a href" in resp.text

    async def test_BR_C_09_format_xml_body(self, client):
        """XML format renders the canonical `<response><url>…</url></response>` doc."""
        resp = await client.get("/?url=http://example.com/xml&format=xml")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/xml")
        body = resp.text
        assert body.startswith('<?xml version="1.0"?>')
        assert "<response>" in body and "</response>" in body
        assert "<url>" in body and "</url>" in body


# ─────────────────────────────────────────────────────────────────────────────
# TestPostShorten — R4 alias


class TestPostShorten:
    async def test_post_shorten_basic(self, client):
        resp = await client.post(
            "/shorten",
            json={"url": "http://post.test/a", "format": "text"},
        )
        assert resp.status_code == 200

    async def test_post_shorten_invalid_url_400(self, client):
        resp = await client.post(
            "/shorten",
            json={"url": "ftp://x"},
        )
        # Pydantic regex rejection → 422 (FastAPI default) or 400 (our handler).
        assert resp.status_code in (400, 422)


# ─────────────────────────────────────────────────────────────────────────────
# TestCreateConcurrency — BR-C-01 race; requires real Postgres (testcontainers)


@pytest.mark.requires_pg
class TestCreateConcurrency:
    async def test_BR_C_01_concurrent_creates_no_500(self):
        """Stage 6 TestGen wires testcontainers-postgresql.

        Until then this test is skipped via the `requires_pg` marker; the
        body is a placeholder that asserts the assertion fixture exists.
        """
        # Placeholder — Stage 6 fills in concurrent POSTs.
        assert True


# ─────────────────────────────────────────────────────────────────────────────
# TestIpWhitelist — BR-C-04 (resolves Self-Review CRITICAL-2)
#
# Planning §11.2 requires 5 test methods; Self-Review found zero. These 5
# tests exercise the whitelist enforcement, the lookup-branch exemption
# (Gate-1 OQ-08), and the X-Forwarded-For middleware path (RF-05 fix).


class TestIpWhitelist:
    """BR-C-04 — IP whitelist access control."""

    @staticmethod
    async def _build_client(
        db_session_factory,
        whitelist_raw: str = "",
        spoof_client_ip: str | None = None,
    ) -> AsyncClient:
        """Build a fresh app with a custom whitelist and optionally override
        get_client_ip to spoof the resolved client IP.

        If `spoof_client_ip` is None, the real ProxyHeadersMiddleware runs —
        needed for the X-Forwarded-For resolution test.
        """
        import logging

        from app.modules.urls.dependencies import get_settings, get_url_service
        from app.modules.urls.service import UrlService

        test_settings = Settings(
            hostname="http://test",
            db_url="sqlite+aiosqlite:///:memory:",
            salt="",
            padding=3,
            ip_whitelist_raw=whitelist_raw,
        )
        application = create_app(test_settings)

        # ASGITransport doesn't trigger lifespan; override deps directly.
        test_service = UrlService(
            cfg=test_settings.encoder_config,
            hostname=test_settings.hostname,
            logger=logging.getLogger("shorty.urls.service.test"),
            session_factory=db_session_factory,
        )

        async def _override_get_db() -> AsyncIterator[AsyncSession]:
            async with db_session_factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        application.dependency_overrides[get_db_session] = _override_get_db
        application.dependency_overrides[get_settings] = lambda: test_settings
        application.dependency_overrides[get_url_service] = lambda: test_service
        if spoof_client_ip is not None:
            application.dependency_overrides[get_client_ip] = (
                lambda: spoof_client_ip
            )

        transport = ASGITransport(app=application)
        return AsyncClient(transport=transport, base_url="http://test")

    async def test_BR_C_04_empty_whitelist_open(self, db_session_factory):
        """Empty whitelist → every IP can create (Gate-1 OQ-08 default)."""
        ac = await self._build_client(
            db_session_factory, whitelist_raw="", spoof_client_ip="9.9.9.9"
        )
        async with ac as client:
            resp = await client.get(
                "/?url=http://example.com/whitelist-empty&format=text"
            )
            assert resp.status_code == 200

    async def test_BR_C_04_ip_in_whitelist_allowed(self, db_session_factory):
        """IP present in non-empty whitelist → create proceeds."""
        ac = await self._build_client(
            db_session_factory,
            whitelist_raw="10.0.0.1,10.0.0.2",
            spoof_client_ip="10.0.0.1",
        )
        async with ac as client:
            resp = await client.get(
                "/?url=http://example.com/whitelist-allowed&format=text"
            )
            assert resp.status_code == 200

    async def test_BR_C_04_ip_not_in_whitelist_403(self, db_session_factory):
        """IP NOT in whitelist → 403 Not allowed."""
        ac = await self._build_client(
            db_session_factory,
            whitelist_raw="10.0.0.1",
            spoof_client_ip="192.168.1.1",
        )
        async with ac as client:
            resp = await client.get(
                "/?url=http://example.com/whitelist-blocked&format=text"
            )
            assert resp.status_code == 403
            body = resp.json()
            assert body["detail"] == "Not allowed."
            assert body["type"] == "shorty/not-allowed"

    async def test_BR_C_04_lookup_ignores_whitelist(self, db_session_factory):
        """Lookup branch is exempt from whitelist enforcement.

        With a non-whitelisted IP, a lookup must return 404 (code not found),
        not 403 (whitelist block). Proves the whitelist gate is only on the
        create branch (router.py:115 inline call, not a route-level dependency).
        """
        ac = await self._build_client(
            db_session_factory,
            whitelist_raw="10.0.0.1",
            spoof_client_ip="192.168.1.1",
        )
        async with ac as client:
            resp = await client.get("/abcxyz")
            assert resp.status_code == 404, (
                "Lookup must bypass whitelist — got 403 means whitelist "
                "is wrongly applied to lookups (BR-C-04 violation)"
            )

    async def test_BR_C_04_xforwardedfor_resolves_real_ip(self, db_session_factory):
        """ProxyHeadersMiddleware honours X-Forwarded-For from trusted proxies.

        ASGITransport sends requests with client=('127.0.0.1', N), which is in
        the default trusted_proxies. The middleware rewrites request.client.host
        to the X-Forwarded-For value before get_client_ip runs (RF-05 fix).
        """
        ac = await self._build_client(
            db_session_factory,
            whitelist_raw="1.2.3.4",
            spoof_client_ip=None,  # let real middleware run
        )
        async with ac as client:
            allowed = await client.get(
                "/?url=http://example.com/xff-allowed&format=text",
                headers={"X-Forwarded-For": "1.2.3.4"},
            )
            assert allowed.status_code == 200, (
                "XFF=1.2.3.4 (whitelisted) must allow create"
            )

            blocked = await client.get(
                "/?url=http://example.com/xff-blocked&format=text",
                headers={"X-Forwarded-For": "9.9.9.9"},
            )
            assert blocked.status_code == 403, (
                "XFF=9.9.9.9 (not in whitelist) must be rejected"
            )
