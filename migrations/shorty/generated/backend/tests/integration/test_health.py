# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: n/a — operational route (R5)
# LEGACY: n/a — scaffold (PHP had no health endpoint)
# COMPONENT: tests/integration/test_health
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG

"""Tests for R5 — GET /healthz."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


class TestHealth:
    async def test_healthz_returns_200(self, client):
        resp = await client.get("/healthz")
        assert resp.status_code == 200

    async def test_healthz_body_shape(self, client):
        resp = await client.get("/healthz")
        body = resp.json()
        assert body["status"] == "ok"
        assert body["db"] in ("ok", "down")
