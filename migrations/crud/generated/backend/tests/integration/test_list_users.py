# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-01, BR-C-02
# LEGACY: source/index.php:6
# COMPONENT: tests/integration/test_list_users
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""GET /api/users — BR-C-01 (id DESC) + BR-C-02 (side-effect-free)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


class TestListUsers:
    async def test_empty_returns_200_empty_array(self, client):
        resp = await client.get("/api/users")
        assert resp.status_code == 200
        assert resp.json() == []
        assert resp.headers["content-type"].startswith("application/json")

    async def test_BR_C_01_orders_by_id_desc(self, client):
        # Seed three users via the API to get realistic insertion order.
        for payload in (
            {"name": "Alice",   "age": 30, "email": "alice@example.com"},
            {"name": "Bob",     "age": 45, "email": "bob@example.com"},
            {"name": "Charlie", "age": 22, "email": "charlie@example.com"},
        ):
            r = await client.post("/api/users", json=payload)
            assert r.status_code == 201

        resp = await client.get("/api/users")
        body = resp.json()
        ids = [row["id"] for row in body]
        assert ids == sorted(ids, reverse=True)
        assert body[0]["name"] == "Charlie"

    async def test_BR_C_02_no_side_effect(self, client):
        # Two consecutive GETs return identical results.
        await client.post(
            "/api/users",
            json={"name": "Dora", "age": 25, "email": "dora@example.com"},
        )
        a = (await client.get("/api/users")).json()
        b = (await client.get("/api/users")).json()
        assert a == b
