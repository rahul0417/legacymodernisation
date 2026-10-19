# Dual-run harness — crud engagement

5 services on a private docker network:
- `mysql-legacy` (MySQL 8, utf8mb3, seeded)
- `php-legacy` (PHP 8 + Apache + mysqli, chapagain source baked in)
- `pg-new` (PostgreSQL 16)
- `fastapi-new` (the generated FastAPI app)
- `react-new` (the generated React Vite build, served by nginx)

All bound to `127.0.0.1` only. Identical 5-row seed on both DBs so lookup parity is deterministic.

## Hosts to visit

| Service | URL | Purpose |
|---|---|---|
| Legacy CRUD (PHP) | http://127.0.0.1:21080/ | The 1999-era table-layout app |
| New SPA (React) | http://127.0.0.1:21173/ | The shadcn DataTable + modals |
| New API direct | http://127.0.0.1:21800/api/users | What the SPA calls |
| Swagger / OpenAPI | http://127.0.0.1:21800/docs | Auto-generated API docs |

## Run

```bash
cd migrations/crud/dual-run
docker compose up -d --build
# ... wait for healthchecks ...
docker compose ps
# Open the URLs above in your browser
```

## Parity testing

Beyond live URLs, two automated parity layers:

1. **API smoke** (`parity-runner.py`): legacy chapagain has no REST API, so we
   API-test the FastAPI side only against 14 fixtures (CRUD happy path + 404 +
   409 duplicate + SQLi-via-path → 422). Writes `reports/api-smoke-report.json`.

2. **Visual parity** (`screenshot-runner.py`): Playwright headless Chromium
   captures 8 legacy screens (list / add form / edit form id=1, id=2, id=999 /
   delete-hover / post-submit list / narrow viewport) and 8 new SPA states
   (list / add modal / add validation error / edit modal / edit 409 conflict /
   delete alert / loading skeleton / empty state). Output: `screenshots/old-*.png`
   and `screenshots/new-*.png` — 16 PNGs, composited side-by-side in the cockpit.

## Teardown

```bash
docker compose down -v   # full reset
```
