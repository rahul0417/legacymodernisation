"""Dual-run parity runner for MWU-SHORTY-001.

Drives a deterministic input matrix against both the legacy PHP shorty
(PHP_REFERENCE_URL) and the new FastAPI port (PYTHON_TARGET_URL), normalises
responses (strip volatile headers, normalise hostname-difference, apply the
documented status-code uplift map), and writes a JSON parity report.

Fixtures format (newline-delimited JSON, one fixture per line):
  {
    "id": "<unique-id>",
    "description": "<human-readable>",
    "side": "create|lookup",
    "method": "GET|POST",
    "path": "/",
    "params": {"url": "...", "format": "text"},
    "json_body": {"url": "..."},
    "headers": {"X-Forwarded-For": "1.2.3.4"},
    "expect": {
       "category": "green_path|error_uplift|known_divergence",
       "uplift": {"php_status": 200, "fast_status": 400}   # for error_uplift only
    }
  }

Each fixture is exercised against both sides. The runner records:
  - `match`: bool — whether responses are byte-equivalent after normalisation
  - `php` + `fast`: side details (status, content-type, body-snippet, location)
  - `verdict`: "PASS" | "FAIL" | "INTENTIONAL_DIVERGENCE"

Exit code: 0 on full pass, 1 if any FAIL row.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from typing import Any, Optional

import httpx


# ── Config ───────────────────────────────────────────────────────────────────

PHP_URL = os.environ.get("PHP_REFERENCE_URL", "http://php-legacy")
FAST_URL = os.environ.get("PYTHON_TARGET_URL", "http://fastapi-new:8000")
FIXTURES_PATH = os.environ.get("FIXTURES_PATH", "/app/fixtures/inputs.jsonl")
REPORT_PATH = os.environ.get("REPORT_PATH", "/app/reports/parity-report.json")
TIMEOUT_S = float(os.environ.get("TIMEOUT_S", "10"))

# Hostnames differ between sides because each app composes short URLs from its
# own SHORTY_HOSTNAME. We strip the host prefix before comparing bodies.
PHP_HOST_PREFIX_RE = re.compile(r"http://php-legacy/?")
FAST_HOST_PREFIX_RE = re.compile(r"http://fastapi-new:8000/?")

# Volatile headers to strip from comparison.
VOLATILE_HEADERS = {
    "date", "server", "content-length", "x-powered-by",
    "keep-alive", "connection", "transfer-encoding",
    # Apache emits these on PHP; uvicorn does not.
    "x-frame-options", "x-content-type-options",
}


# ── Models ───────────────────────────────────────────────────────────────────

@dataclass
class SideResult:
    status: int
    content_type: str
    body_normalised: str
    location: Optional[str]
    error: Optional[str] = None


@dataclass
class FixtureOutcome:
    id: str
    description: str
    category: str
    verdict: str           # PASS | FAIL | INTENTIONAL_DIVERGENCE
    match: bool
    php: SideResult
    fast: SideResult
    notes: list[str]


# ── Helpers ──────────────────────────────────────────────────────────────────

def normalise_body(side: str, body: str, content_type: str) -> str:
    """Strip side-specific hostname prefix + JSON-escape divergence so the
    remaining short URL is comparable byte-for-byte."""
    # PHP `json_encode` defaults to escaping forward slashes (`http:\/\/...`)
    # while FastAPI's JSONResponse / orjson does not. Both encodings are
    # valid JSON and decode identically. Normalise the PHP form to match
    # before host-prefix stripping.
    if side == "php" and "json" in content_type:
        body = body.replace(r"\/", "/")
    if side == "php":
        body = PHP_HOST_PREFIX_RE.sub("@HOST@/", body)
    else:
        body = FAST_HOST_PREFIX_RE.sub("@HOST@/", body)
    # PHP's `not_found()` appends 512 trailing spaces for IE compat — strip.
    if content_type.startswith("text/html") and "404 Not Found" in body:
        body = body.rstrip()
    return body


def short_code_of(body_normalised: str, side: str) -> Optional[str]:
    """Extract the short code (last path segment) from a body that contains
    @HOST@/<code>. Returns None if not present."""
    m = re.search(r"@HOST@/([a-zA-Z0-9]+)", body_normalised)
    return m.group(1) if m else None


async def fire(
    client: httpx.AsyncClient,
    base: str,
    fixture: dict,
    side: str,
) -> SideResult:
    method = fixture.get("method", "GET").upper()
    path = fixture.get("path", "/")
    params = fixture.get("params") or {}
    headers = fixture.get("headers") or {}
    json_body = fixture.get("json_body")

    url = base.rstrip("/") + path
    try:
        if method == "GET":
            r = await client.get(
                url, params=params, headers=headers, follow_redirects=False
            )
        elif method == "POST":
            r = await client.post(
                url,
                params=params,
                headers=headers,
                json=json_body,
                follow_redirects=False,
            )
        else:
            raise ValueError(f"unsupported method: {method}")
    except httpx.HTTPError as exc:
        return SideResult(
            status=-1, content_type="", body_normalised="",
            location=None, error=f"{type(exc).__name__}: {exc}",
        )

    content_type = (r.headers.get("content-type") or "").lower()
    body = r.text or ""
    body_n = normalise_body(side, body, content_type)
    location = r.headers.get("location")
    if location:
        # Normalise the Location host prefix too (only present on redirects).
        if side == "php":
            location = PHP_HOST_PREFIX_RE.sub("@HOST@/", location)
        else:
            location = FAST_HOST_PREFIX_RE.sub("@HOST@/", location)
    return SideResult(
        status=r.status_code,
        content_type=content_type,
        body_normalised=body_n,
        location=location,
    )


def verdict_of(fixture: dict, php: SideResult, fast: SideResult) -> tuple[str, bool, list[str]]:
    """Return (verdict, match_bool, notes)."""
    expect = fixture.get("expect", {})
    category = expect.get("category", "green_path")
    notes: list[str] = []

    if category == "green_path":
        # Status, content-type, body, and location must match byte-for-byte
        # (after normalisation). Content-type comparison is SKIPPED on 3xx
        # redirects — the body is empty and content-type is irrelevant
        # (PHP emits text/html default, FastAPI emits nothing).
        is_redirect = 300 <= php.status < 400 or 300 <= fast.status < 400
        ct_match = is_redirect or (php.content_type == fast.content_type)
        match = (
            php.status == fast.status
            and ct_match
            and php.body_normalised == fast.body_normalised
            and (php.location or "") == (fast.location or "")
        )
        if not match:
            if php.status != fast.status:
                notes.append(f"status: {php.status} vs {fast.status}")
            if not ct_match:
                notes.append(f"content-type: {php.content_type!r} vs {fast.content_type!r}")
            if php.body_normalised != fast.body_normalised:
                notes.append(
                    f"body: {php.body_normalised[:80]!r} vs {fast.body_normalised[:80]!r}"
                )
            if (php.location or "") != (fast.location or ""):
                notes.append(f"location: {php.location!r} vs {fast.location!r}")
        return ("PASS" if match else "FAIL"), match, notes

    if category == "error_uplift":
        # PHP returns 200 with `<h1>…</h1>` body; FastAPI returns the uplifted
        # status (400/403/404) with ProblemDetail JSON. Match if both:
        #   1. the status uplift matches `expect.uplift.{php_status,fast_status}`
        #   2. the human message text is present in both bodies
        uplift = expect.get("uplift", {})
        expected_php = uplift.get("php_status", 200)
        expected_fast = uplift.get("fast_status")
        message = (uplift.get("message") or "").strip()
        php_status_ok = php.status == expected_php
        fast_status_ok = fast.status == expected_fast
        message_ok = (
            (not message)
            or (message in php.body_normalised and message in fast.body_normalised)
        )
        match = php_status_ok and fast_status_ok and message_ok
        if not match:
            if not php_status_ok:
                notes.append(f"php status: got {php.status}, expected {expected_php}")
            if not fast_status_ok:
                notes.append(f"fast status: got {fast.status}, expected {expected_fast}")
            if not message_ok:
                notes.append(f"message {message!r} not found in both bodies")
        return ("PASS" if match else "FAIL"), match, notes

    if category == "known_divergence":
        # Documented divergence — record but don't fail the run.
        return "INTENTIONAL_DIVERGENCE", False, ["documented divergence — not a defect"]

    return "FAIL", False, [f"unknown category: {category}"]


# ── Main ─────────────────────────────────────────────────────────────────────

async def amain() -> int:
    if not os.path.isfile(FIXTURES_PATH):
        print(f"[parity] fixtures file missing: {FIXTURES_PATH}", file=sys.stderr)
        return 2

    fixtures: list[dict] = []
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fixtures.append(json.loads(line))

    print(f"[parity] loaded {len(fixtures)} fixtures")
    print(f"[parity] PHP reference: {PHP_URL}")
    print(f"[parity] FastAPI target: {FAST_URL}")

    outcomes: list[FixtureOutcome] = []
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        for fx in fixtures:
            php_res = await fire(client, PHP_URL, fx, "php")
            fast_res = await fire(client, FAST_URL, fx, "fast")
            verdict, match, notes = verdict_of(fx, php_res, fast_res)
            outcomes.append(FixtureOutcome(
                id=fx["id"],
                description=fx.get("description", ""),
                category=fx.get("expect", {}).get("category", "green_path"),
                verdict=verdict,
                match=match,
                php=php_res,
                fast=fast_res,
                notes=notes,
            ))

    # ── Summary ─────────────────────────────────────────────────────────────
    n_pass = sum(1 for o in outcomes if o.verdict == "PASS")
    n_fail = sum(1 for o in outcomes if o.verdict == "FAIL")
    n_div = sum(1 for o in outcomes if o.verdict == "INTENTIONAL_DIVERGENCE")
    n_green = sum(1 for o in outcomes if o.category == "green_path")
    n_green_match = sum(
        1 for o in outcomes if o.category == "green_path" and o.match
    )

    summary = {
        "total": len(outcomes),
        "pass": n_pass,
        "fail": n_fail,
        "intentional_divergence": n_div,
        "green_path_total": n_green,
        "green_path_pass": n_green_match,
        "green_path_match": (n_green_match / n_green) if n_green else 1.0,
        "php_reference_url": PHP_URL,
        "python_target_url": FAST_URL,
    }

    report = {
        "summary": summary,
        "outcomes": [
            {
                **{k: v for k, v in asdict(o).items() if k != "php" and k != "fast"},
                "php": asdict(o.php),
                "fast": asdict(o.fast),
            }
            for o in outcomes
        ],
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Console summary.
    print()
    print(f"[parity] {n_pass} PASS · {n_fail} FAIL · {n_div} known-divergence")
    print(f"[parity] green-path match: {n_green_match}/{n_green} "
          f"({summary['green_path_match']*100:.1f}%)")
    print(f"[parity] report: {REPORT_PATH}")

    if n_fail:
        print("[parity] FAIL rows:", file=sys.stderr)
        for o in outcomes:
            if o.verdict == "FAIL":
                print(f"  - {o.id} ({o.description}): {'; '.join(o.notes)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(amain()))
