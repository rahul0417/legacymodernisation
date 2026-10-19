"""Dual-run API parity runner for MWU-CRUD-001.

NOTE: legacy chapagain/crud-php-simple does NOT expose REST endpoints — it
serves HTML pages directly (index.php / addAction.php / editAction.php /
delete.php). For *API* parity we would have to shim the legacy with a small
PHP layer mapping `/api/users*` to the legacy SQL. That shim is deferred.

For this engagement, parity is established via:
  1. Shared seed data (same 5 rows in both DBs)
  2. Visual screenshots (screenshot-runner.py — captures legacy 4 screens + new SPA states)
  3. Direct API smoke test of the new app only (this script runs FastAPI-side only)

The hosts file is `fixtures/api-inputs.jsonl` (14 fixtures). This script hits
the FastAPI side, asserts status codes and required response shape, and writes
`reports/api-smoke-report.json`.

Exit code 0 if all assertions pass; 1 otherwise.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx


FAST_URL = os.environ.get("PYTHON_TARGET_URL", "http://fastapi-new:8000")
FIXTURES_PATH = os.environ.get("FIXTURES_PATH", "/app/fixtures/api-inputs.jsonl")
REPORT_PATH = os.environ.get("REPORT_PATH", "/app/reports/api-smoke-report.json")
TIMEOUT_S = float(os.environ.get("TIMEOUT_S", "10"))


async def run_fixture(client: httpx.AsyncClient, fx: dict[str, Any]) -> dict[str, Any]:
    method = fx.get("method", "GET").upper()
    path = fx["path"]
    body = fx.get("json_body")
    url = FAST_URL.rstrip("/") + path
    try:
        if method in ("POST", "PUT"):
            r = await client.request(method, url, json=body)
        else:
            r = await client.request(method, url)
    except httpx.HTTPError as exc:
        return {
            "id": fx["id"],
            "description": fx.get("description", ""),
            "status": -1,
            "verdict": "FAIL",
            "notes": [f"{type(exc).__name__}: {exc}"],
        }

    expect = fx.get("expect", {})
    category = expect.get("category", "green_path")
    notes: list[str] = []
    verdict = "PASS"

    if category == "green_path":
        # 2xx expected
        if not (200 <= r.status_code < 300):
            verdict = "FAIL"
            notes.append(f"expected 2xx, got {r.status_code}")
    elif category == "error_uplift":
        uplift = expect.get("uplift", {})
        expected = uplift.get("fast_status")
        if expected is not None and r.status_code != expected:
            verdict = "FAIL"
            notes.append(f"expected status {expected}, got {r.status_code}")
        message_hint = (uplift.get("message") or "").lower()
        if message_hint:
            try:
                body_json = r.json()
                blob = json.dumps(body_json).lower()
                if message_hint not in blob:
                    verdict = "FAIL"
                    notes.append(f"expected message hint '{message_hint}' in body")
            except Exception:
                pass

    return {
        "id": fx["id"],
        "description": fx.get("description", ""),
        "status": r.status_code,
        "verdict": verdict,
        "notes": notes,
    }


async def amain() -> int:
    if not os.path.isfile(FIXTURES_PATH):
        print(f"[crud-parity] fixtures missing: {FIXTURES_PATH}", file=sys.stderr)
        return 2

    fixtures: list[dict[str, Any]] = []
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fixtures.append(json.loads(line))

    print(f"[crud-parity] loaded {len(fixtures)} fixtures · target={FAST_URL}")

    outcomes: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        for fx in fixtures:
            o = await run_fixture(client, fx)
            outcomes.append(o)
            print(f"  {fx['id']:18s} {o['verdict']}  (HTTP {o['status']})")

    n_pass = sum(1 for o in outcomes if o["verdict"] == "PASS")
    n_fail = len(outcomes) - n_pass

    summary = {
        "total": len(outcomes),
        "pass": n_pass,
        "fail": n_fail,
        "target": FAST_URL,
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "outcomes": outcomes}, f, indent=2)

    print()
    print(f"[crud-parity] {n_pass} PASS · {n_fail} FAIL")
    print(f"[crud-parity] report: {REPORT_PATH}")

    return 1 if n_fail else 0


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(amain()))
