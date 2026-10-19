# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-03, BR-C-04, BR-C-05, BR-C-06, BR-C-11
# LEGACY: source/addAction.php
# COMPONENT: tests/integration/test_create_user
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""POST /api/users — happy + validation + conflict.

Stage 6 TestGen will expand to the full Planning §11.2 table.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


class TestCreateHappy:
    async def test_happy_returns_201_and_location(self, client):
        resp = await client.post(
            "/api/users",
            json={"name": "Alice", "age": 30, "email": "alice@example.com"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert resp.headers.get("location") == f"/api/users/{body['id']}"


class TestCreateValidation:
    async def test_BR_C_03_empty_body_returns_422(self, client):
        resp = await client.post("/api/users", json={})
        assert resp.status_code == 422
        body = resp.json()
        assert body["status"] == 422
        # Expect at least three field errors (name, age, email)
        assert isinstance(body.get("errors"), list)
        assert len(body["errors"]) >= 3

    async def test_BR_C_03_whitespace_name_rejected(self, client):
        resp = await client.post(
            "/api/users",
            json={"name": "   ", "age": 30, "email": "a@b.co"},
        )
        assert resp.status_code == 422

    async def test_BR_C_04_age_negative_rejected(self, client):
        resp = await client.post(
            "/api/users",
            json={"name": "Alice", "age": -1, "email": "a@b.co"},
        )
        assert resp.status_code == 422

    async def test_BR_C_04_age_151_rejected(self, client):
        resp = await client.post(
            "/api/users",
            json={"name": "Alice", "age": 151, "email": "a@b.co"},
        )
        assert resp.status_code == 422

    async def test_BR_C_04_age_zero_accepted(self, client):
        resp = await client.post(
            "/api/users",
            json={"name": "Newborn", "age": 0, "email": "n@b.co"},
        )
        assert resp.status_code == 201

    async def test_BR_C_05_invalid_email_rejected(self, client):
        resp = await client.post(
            "/api/users",
            json={"name": "Alice", "age": 30, "email": "not-an-email"},
        )
        assert resp.status_code == 422

    async def test_BR_C_06_long_name_rejected(self, client):
        resp = await client.post(
            "/api/users",
            json={"name": "x" * 101, "age": 30, "email": "a@b.co"},
        )
        assert resp.status_code == 422


class TestCreateConflict:
    async def test_BR_C_11_duplicate_email_returns_409(self, client):
        first = await client.post(
            "/api/users",
            json={"name": "Alice", "age": 30, "email": "dup@example.com"},
        )
        assert first.status_code == 201

        second = await client.post(
            "/api/users",
            json={"name": "Imposter", "age": 40, "email": "dup@example.com"},
        )
        assert second.status_code == 409
        body = second.json()
        assert body["title"] == "Email already exists"
        assert body["status"] == 409
        assert "dup@example.com" in (body.get("detail") or "")
