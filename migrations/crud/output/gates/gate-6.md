# Gate 6 — Dual-run (PNS-CRUD-001)

**Date:** 2026-05-14
**Reviewer:** Rahul Chandra (HITL)
**Stage:** Dual-run (`dual-run/`)
**Status:** ✅ **APPROVED**

## Summary

5-service docker stack live on a private 127.0.0.1-bound network. Identical 5-row seed on both sides. Two parity layers captured.

| Layer | Result |
|---|---|
| **API smoke** (FastAPI side) | **14 / 14 fixtures PASS** — list / get / 404 / create 201 / duplicate 409 / 4 validation 422s / update 200 / update-404 / delete 204 / delete-404 / list-after |
| **Visual transformation** | **16 / 16 screenshots captured** (8 legacy + 8 new) — `migrations/crud/screenshots/old-*.png` and `new-*.png` |
| **Live URLs verified** | Legacy 1999-era table at `http://127.0.0.1:21080/`; shadcn SPA at `http://127.0.0.1:21173/`; OpenAPI at `http://127.0.0.1:21800/docs` |

## API smoke detail

```
LIST-1             PASS  (HTTP 200)
GET-1              PASS  (HTTP 200)
GET-42             PASS  (HTTP 404)
CREATE-OK          PASS  (HTTP 201)
CREATE-DUP         PASS  (HTTP 409)
CREATE-BAD-EMAIL   PASS  (HTTP 422)
CREATE-AGE-LOW     PASS  (HTTP 422)
CREATE-AGE-HIGH    PASS  (HTTP 422)
CREATE-EMPTY-NAME  PASS  (HTTP 422)
UPDATE-OK          PASS  (HTTP 200)
UPDATE-404         PASS  (HTTP 404)
DELETE-OK          PASS  (HTTP 204)
DELETE-404         PASS  (HTTP 404)
LIST-AFTER         PASS  (HTTP 200)
```

Report on disk at `dual-run/reports/api-smoke-report.json`.

## Visual transformation — 8 + 8 screenshots

| # | Legacy (chapagain bare HTML) | New (React + shadcn) |
|---|---|---|
| 1 | `old-01-list.png` — table border=0 list | `new-01-list.png` — shadcn DataTable |
| 2 | `old-02-add-form.png` — raw `<form>` | `new-02-add-modal.png` — Radix Dialog |
| 3 | `old-03-edit-form-id1.png` — Bob populated | `new-03-add-validation-error.png` — RHF + Zod live errors |
| 4 | `old-04-edit-missing-id.png` — empty form on id=999 | `new-04-edit-modal.png` — Carol pre-populated |
| 5 | `old-05-delete-hover.png` — Delete link hovered | `new-05-edit-email-conflict.png` — 409 server error projected to email field |
| 6 | `old-06-add-action-success.png` — list after Frank insert | `new-06-delete-alert.png` — Radix AlertDialog with destructive button |
| 7 | `old-07-list-narrow.png` — 420px viewport (no responsiveness) | `new-07-loading-skeleton.png` — accessible status skeleton |
| 8 | `old-08-edit-form-id2.png` — Bob, id=2 | `new-08-empty-state.png` — EmptyState onboarding |

## Issues found + fixed during dual-run

| # | File | Issue | Fix |
|---|---|---|---|
| DR-1 | `dual-run/seed-pg.sql` + `seed.sql` + `fixtures/api-inputs.jsonl` | Seed emails used `@example.test` / `@parity.test`. Pydantic EmailStr rejects `.test` TLD (reserved, per RFC 2606). | Replaced with `@example.com` / `@parity.io`. |
| DR-2 | `dual-run/php-overlay/dbConnection.php` | Hardcoded host `crud-mysql` instead of compose service name `mysql-legacy`. | Renamed. |
| DR-3 | `dual-run/docker-compose.yml` (CORS env) | pydantic-settings JSON-decodes complex list[str] fields from env BEFORE the `@field_validator(mode="before")` runs. CSV string failed parse. | Pass CRUD_CORS_ORIGINS as JSON array literal. |
| DR-4 | `frontend/src/hooks/useUsers.ts` (3 hooks) | TanStack Query v5.20 changed mutation `onSuccess` from 3-arg to 4-arg signature; build failed `error TS2554`. | Switched to `(...args)` rest forwarding. Tests re-run 35/35 PASS. |
| DR-5 | `dual-run/Dockerfile.runner` | Playwright base image ships browsers but not the `playwright` Python package. | Added `playwright==1.47.0` to the pip install. |
| DR-6 | `dual-run/docker-compose.yml` healthcheck | Pinged `/healthz`; backend mounts under `/api`. | Changed to `/api/healthz`. |
| DR-7 | `dual-run/docker-compose.yml` env name | Passed `CRUD_DB_URL`; Settings reads `CRUD_DATABASE_URL`. | Renamed. |
| DR-8 | `frontend/Dockerfile` nginx upstream | Pointed at `http://api:8000` (wrong); real service is `fastapi-new`. | Renamed. |

All fixes committed in-place; full stack now stands up cleanly from `docker compose up -d --build` with zero manual intervention.

## What's next (Stage 8)

- Polish `demo/crud/index.html` final pipeline-complete message with real numbers (107 tests · 14/14 API smoke · 16 screenshots).
- Optionally compose a side-by-side mosaic (old-01 ↔ new-01, etc.) for the cockpit gallery.
- Update top-level `demo/README.md` to list the 3 case studies.
- Append final `engagement_complete` audit entry.

---

**Pipeline status: ✅ All 6 gates PASSED.** MWU-CRUD-001 FULLY_VALIDATED — backend + frontend generated, reviewed, tested, dual-run verified, visually captured. Ready for customer demo playback.
