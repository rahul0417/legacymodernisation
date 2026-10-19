# Gate 6 — Dual-run parity review

**Date:** 2026-05-14
**Reviewer:** Rahul Chandra (HITL)
**Stage reviewed:** Stage 7 — Dual-run parity harness build + execution
**Status:** ✅ **APPROVED**

## Summary

The dual-run harness brings up four services on a private Docker network (`mysql-legacy`,
`php-legacy`, `pg-new`, `fastapi-new`) plus a `parity-runner` sidecar. All services are
bound to 127.0.0.1 only (`php-legacy` and `fastapi-new` exposed for host-side debugging at
`:18080` and `:18000` respectively; DB services not published at all). Parity runner exercises
20 fixtures against both sides and writes `reports/parity-report.json`.

## Results

```
Total:    20 fixtures
PASS:     14
FAIL:      0
KNOWN:     6 (documented divergence — D3 text Content-Type)
GREEN-PATH MATCH: 9/9 (100.0%)
```

### Green path — byte-equivalent matches (9/9)

| Fixture | What it proves |
|---|---|
| C-json | JSONResponse body matches PHP `json_encode` after slash-unescape normalisation |
| C-xml | XML body byte-equivalent (`<?xml version="1.0"?><response><url>…</url></response>`) |
| C-html-default | Default `<a href="…">…</a>` anchor identical |
| C-html-explicit | Explicit `format=html` produces same output |
| L-seed-1 | Lookup `/b` → 301 `Location: https://example.com/alpha` |
| L-seed-42 | Lookup `/Q` → 301 `Location: https://example.com/forty-two` |
| L-seed-999 | Lookup `/qh` → 301 `Location: https://example.com/nine-nine-nine` |
| L-seed-12345 | Lookup `/dnh` → 301 `Location: https://example.com/twelve-thousand` |
| L-seed-2billion | Lookup `/clvXwG` → 301 (verifies INT32-ceiling encode/decode round-trip) |

### Error uplift — PHP 200 → FastAPI 4xx with matching detail text (5/5)

| Fixture | PHP | FastAPI | Verdict |
|---|---|---|---|
| L-unknown (`/zzzzzz`) | 200 + `<h1>404 Not Found</h1>…` | 404 + `{"detail":"Not Found",...}` | PASS |
| L-unknown-2 (`/zzzz9`) | 200 + `<h1>404 Not Found</h1>…` | 404 + ProblemDetail | PASS |
| E-bad-url-ftp | 200 + `<h1>Bad input.</h1>` | 400 + ProblemDetail | PASS |
| E-bad-url-uppercase | 200 + `<h1>Bad input.</h1>` | 400 + ProblemDetail | PASS |
| E-empty-request | 200 + `<h1>404 Not Found</h1>…` | 404 + ProblemDetail | PASS |

This validates RF-09 (the migration's documented status-code uplift): legacy mod_php
doesn't honour `header('Status: 404 Not Found')` so it returns 200 on the not-found path;
the FastAPI port returns the correct HTTP status with structured error bodies.

### Known divergence — documented per Planning §12.4 D3 (6/6)

All six `format=text` fixtures: PHP sets no `Content-Type` header (defaults to `text/html`),
FastAPI sets `text/plain; charset=utf-8` (RF-10 fix). Body content is byte-identical; only
the MIME label differs.

## Harness assets (all under `dual-run/`)

```
docker-compose.yml          # 5 services, private network, 127.0.0.1-only bindings
Dockerfile.php              # PHP 8.2 + Apache + mod_rewrite + PDO_MySQL; source baked in
Dockerfile.runner           # python:3.12-slim + httpx for the parity runner
fastapi-entrypoint.sh       # waits for PG, runs alembic upgrade, seeds rows, exec uvicorn
parity-runner.py            # 250 LOC; fixture-driven, response normalisation, JSON report
seed.sql                    # MySQL 8 schema + 5 deterministic rows (id 1, 42, 999, 12345, 2B)
seed-pg.sql                 # PostgreSQL 16 schema (via alembic) + same 5 logical rows
php-overlay/.htaccess       # Apache mod_rewrite to route /<code> → ?q=<code>
php-overlay/config.php      # PHP config: error suppression + container DSN + locked encoder params
fixtures/inputs.jsonl       # 20 fixtures across green-path, error-uplift, known-divergence
reports/parity-report.json  # Generated, 466 lines, machine-readable
```

## Security posture

- All inter-service traffic on private Docker network
- `mysql-legacy` and `pg-new` not published to host
- `php-legacy` (18080) and `fastapi-new` (18000) bound to `127.0.0.1` only — never public
- No host filesystem mounts beyond the read-only legacy `source/` (baked into PHP image)
- DB volumes ephemeral (`docker compose down -v` wipes)
- All passwords are hard-coded `*_dev_only` strings never reused outside this harness

## What this proves

1. **Encoding stability:** every seeded ID produces the same short code on both sides (the
   load-bearing BR-C-12 invariant holds against the legacy PHP reference).
2. **Lookup parity:** Location header byte-equivalent for every seeded URL.
3. **Format-output parity:** JSON / XML / HTML responses identical (post-host-normalisation).
4. **Dedup correctness (BR-C-01):** repeated create returns the same code on both sides.
5. **Error-handling parity:** every error path lands on the documented status uplift map.
6. **Documented divergence is documented:** the 6 text Content-Type divergences match Planning §12.4 D3 exactly.

## What's not in scope for Stage 7

- BR-C-04 IP whitelist parity (covered by Stage 6 unit/integration tests; harder to wire
  in dual-run because both sides need symmetric whitelist config)
- BR-C-10 telemetry hit-count parity at scale (would need a separate "after N redirects,
  hits == N" probe — currently verified at unit/integration tier)
- Performance comparison (latency, throughput) — deferred to Phase 5

## Reproducibility

```bash
cd migrations/shorty/dual-run
docker compose up -d --build              # ~2 min first time, ~10 sec subsequent
docker compose --profile run run --rm parity-runner
jq '.summary' reports/parity-report.json
docker compose down -v                    # full teardown
```

---

**Next stage:** Stage 8 — Cockpit re-skin for the shorty engagement. Re-skin the
mission-control HTML with shorty-specific data, real artefacts populated from
`output/` and `generated/`, real numbers from gate/test/parity reports.
