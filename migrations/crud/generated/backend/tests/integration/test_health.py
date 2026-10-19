# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: n/a — operational route
# LEGACY: n/a — scaffold (PHP had no health endpoint)
# COMPONENT: tests/integration/test_health
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""Tests for GET /api/healthz."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


class TestHealth:
    async def test_healthz_returns_200(self, client):
        resp = await client.get("/api/healthz")
        assert resp.status_code == 200

    async def test_healthz_body_shape(self, client):
        resp = await client.get("/api/healthz")
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "crud"
        assert isinstance(body["version"], str)
