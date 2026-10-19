# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-08, BR-C-09
# LEGACY: source/delete.php
# COMPONENT: tests/integration/test_delete_user
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""DELETE /api/users/{id} — happy (204), missing (404), GET-doesn't-mutate."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _create(client, name="Alice", age=30, email="alice@example.com"):
    resp = await client.post(
        "/api/users",
        json={"name": name, "age": age, "email": email},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestDeleteUser:
    async def test_BR_C_08_happy_returns_204_no_body(self, client):
        u = await _create(client)
        resp = await client.delete(f"/api/users/{u['id']}")
        assert resp.status_code == 204
        assert resp.content == b""

    async def test_BR_C_08_get_after_delete_returns_404(self, client):
        u = await _create(client)
        await client.delete(f"/api/users/{u['id']}")
        resp = await client.get(f"/api/users/{u['id']}")
        assert resp.status_code == 404

    async def test_BR_C_08_list_excludes_deleted(self, client):
        u = await _create(client)
        await client.delete(f"/api/users/{u['id']}")
        rows = (await client.get("/api/users")).json()
        assert all(row["id"] != u["id"] for row in rows)

    async def test_BR_C_08_delete_missing_returns_404(self, client):
        resp = await client.delete("/api/users/99999")
        assert resp.status_code == 404

    async def test_BR_C_09_get_does_not_mutate(self, client):
        u = await _create(client)
        before = (await client.get("/api/users")).json()
        # GET on the resource — should not delete.
        await client.get(f"/api/users/{u['id']}")
        after = (await client.get("/api/users")).json()
        assert before == after
