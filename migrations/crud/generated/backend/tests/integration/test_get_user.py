# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-07
# LEGACY: source/edit.php:9
# COMPONENT: tests/integration/test_get_user
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""GET /api/users/{id} — existing, missing, non-int path id."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


class TestGetUser:
    async def test_existing_returns_200(self, client):
        created = await client.post(
            "/api/users",
            json={"name": "Alice", "age": 30, "email": "alice@example.com"},
        )
        uid = created.json()["id"]

        resp = await client.get(f"/api/users/{uid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == uid
        assert body["email"] == "alice@example.com"

    async def test_BR_C_07_missing_returns_404(self, client):
        resp = await client.get("/api/users/99999")
        assert resp.status_code == 404
        body = resp.json()
        assert body["title"] == "User not found"
        assert body["status"] == 404
        assert "99999" in (body.get("detail") or "")

    async def test_non_int_path_returns_422(self, client):
        resp = await client.get("/api/users/not-an-int")
        assert resp.status_code == 422
