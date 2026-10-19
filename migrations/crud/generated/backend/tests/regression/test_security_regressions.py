# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-09 (RF-001, RF-002, RF-003, RF-007 regression coverage)
# LEGACY: source/edit.php, source/delete.php, source/index.php
# COMPONENT: tests/regression/test_security_regressions
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""Security regressions — keep the legacy RFs from re-emerging.

RF-001 SQL injection in edit (auto-resolved by typed path param).
RF-002 SQL injection in delete (auto-resolved by typed path param).
RF-003 Stored XSS via raw echo (auto-resolved by React text-node escaping;
       backend test asserts payload stored literally).
RF-007 Delete via HTTP GET (auto-resolved by router only registering
       @router.delete).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


class TestSqlInjectionDefence:
    """Self-Review §6 D — extend coverage so each mutating verb plus GET on
    a path id rejects injection payloads with 422 (never 500). Stage-6
    expansion of the original two-case smoke layer.
    """

    # Canonical injection payloads — drawn from OWASP cheat sheet. Path
    # traversal payloads (`../../etc/passwd`) are excluded because httpx
    # client normalises them at the URL layer (returning 404 from FastAPI's
    # routing layer rather than 422 from parsed-int validation); the
    # parsed-int boundary is what we're testing here.
    INJECT_PAYLOADS = (
        "1;DROP%20TABLE%20users",
        "1'%20OR%20'1'='1",
        "1%20UNION%20SELECT%20*%20FROM%20users",
        "%00",
        "abc",
    )

    @pytest.mark.parametrize("payload", INJECT_PAYLOADS)
    async def test_RF_001_inject_via_GET_path_returns_422(self, client, payload):
        resp = await client.get(f"/api/users/{payload}")
        assert resp.status_code == 422, (
            f"GET /api/users/{payload!r} returned {resp.status_code} "
            f"— expected 422 (parsed-int boundary)."
        )
        assert resp.status_code != 500

    @pytest.mark.parametrize("payload", INJECT_PAYLOADS)
    async def test_RF_001_inject_via_PUT_path_returns_422(self, client, payload):
        resp = await client.put(
            f"/api/users/{payload}",
            json={"name": "X", "age": 1, "email": "x@y.co"},
        )
        assert resp.status_code == 422
        assert resp.status_code != 500

    @pytest.mark.parametrize("payload", INJECT_PAYLOADS)
    async def test_RF_002_inject_via_DELETE_path_returns_422(self, client, payload):
        resp = await client.delete(f"/api/users/{payload}")
        assert resp.status_code == 422
        assert resp.status_code != 500

    async def test_RF_007_get_on_users_does_not_delete(self, client):
        create = await client.post(
            "/api/users",
            json={"name": "Alice", "age": 30, "email": "alice@example.com"},
        )
        uid = create.json()["id"]
        # GET the user — should not mutate. Then list still includes the row.
        await client.get(f"/api/users/{uid}")
        rows = (await client.get("/api/users")).json()
        assert any(r["id"] == uid for r in rows)


class TestXssPayloadStoredLiterally:
    async def test_RF_003_script_tag_stored_verbatim(self, client):
        payload = {
            "name": "<script>alert(1)</script>",
            "age": 30,
            "email": "x@y.co",
        }
        resp = await client.post("/api/users", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        # Payload stored literally (no PHP-style escape/sanitise on the way in;
        # React text-node escaping handles output safety).
        assert body["name"] == "<script>alert(1)</script>"
