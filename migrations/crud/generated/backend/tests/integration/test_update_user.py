# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-03, BR-C-04, BR-C-05, BR-C-06, BR-C-07, BR-C-11
# LEGACY: source/editAction.php
# COMPONENT: tests/integration/test_update_user
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""PUT /api/users/{id} — happy + 404 + 409 (other) + 200 (self-collision)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _create(client, name, age, email):
    resp = await client.post(
        "/api/users",
        json={"name": name, "age": age, "email": email},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestUpdateUser:
    async def test_happy_returns_200(self, client):
        u = await _create(client, "Alice", 30, "alice@example.com")
        resp = await client.put(
            f"/api/users/{u['id']}",
            json={"name": "Alice Renamed", "age": 31, "email": "alice@example.com"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == u["id"]
        assert body["name"] == "Alice Renamed"
        assert body["age"] == 31

    async def test_BR_C_07_missing_returns_404(self, client):
        resp = await client.put(
            "/api/users/99999",
            json={"name": "Ghost", "age": 30, "email": "ghost@example.com"},
        )
        assert resp.status_code == 404

    async def test_BR_C_11_other_email_returns_409(self, client):
        a = await _create(client, "Alice", 30, "alice@example.com")
        _ = await _create(client, "Bob", 40, "bob@example.com")
        resp = await client.put(
            f"/api/users/{a['id']}",
            json={"name": "Squatter", "age": 33, "email": "bob@example.com"},
        )
        assert resp.status_code == 409

    async def test_AC_11c_self_email_returns_200(self, client):
        a = await _create(client, "Alice", 30, "alice@example.com")
        # Resubmit own email; only name+age differ.
        resp = await client.put(
            f"/api/users/{a['id']}",
            json={"name": "Alice 2", "age": 31, "email": "alice@example.com"},
        )
        assert resp.status_code == 200

    async def test_AC_11c_self_collision_retry_returns_200(self, client):
        """Self-Review-flagged edge case: PUT same email to same user multiple
        times in succession must return 200 every time (idempotent self-update),
        NOT a 409 on the second attempt — separate from the other-user 409 case.
        Locks behaviour for service.py:138-158 self-collision re-fetch branch.
        """
        a = await _create(client, "Alice", 30, "alice@example.com")
        for attempt in range(1, 4):
            resp = await client.put(
                f"/api/users/{a['id']}",
                json={
                    "name": f"Alice v{attempt}",
                    "age": 30 + attempt,
                    "email": "alice@example.com",
                },
            )
            assert resp.status_code == 200, (
                f"AC-11c retry attempt {attempt} regressed: "
                f"{resp.status_code} {resp.text}"
            )
            body = resp.json()
            assert body["id"] == a["id"]
            assert body["email"] == "alice@example.com"

    async def test_body_id_rejected_with_422(self, client):
        a = await _create(client, "Alice", 30, "alice@example.com")
        resp = await client.put(
            f"/api/users/{a['id']}",
            json={
                "id": 12345,  # forbidden by extra="forbid"
                "name": "Alice",
                "age": 30,
                "email": "alice@example.com",
            },
        )
        assert resp.status_code == 422
