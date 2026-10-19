# Shape: crud — file manifest

Per-file split between **templates/** (stack-stable, copied as-is per engagement)
and **codegen** (Stage 2 writes these per entity from the contract).

This is the contract Stage 2 honours: anything in "codegen" is the agent's
responsibility; anything in "templates" the agent must NOT regenerate.

## Backend (`templates/backend-skeleton/` → `runs/<ts>/generated/backend/`)

| File | Lifecycle | Notes |
|---|---|---|
| `app/__init__.py` | template | empty marker |
| `app/core/config.py` | template | Settings with `env_prefix="CRUD_"`, CORS validator, async-driver guard |
| `app/core/logging.py` | template | structured JSON / text logging setup |
| `app/db/base.py` | template | `class Base(DeclarativeBase)` |
| `app/db/engine.py` | template | async engine + session factory, SQLite pool-size guard included |
| `app/db/migrations/env.py` | template | Alembic env wired to Base.metadata |
| `app/db/migrations/script.py.mako` | template | migration template |
| `app/db/migrations/versions/0001_init_<entity>.py` | **codegen** | one migration per entity |
| `app/main.py` | template *with* one templated line | `from app.modules.{entity}.router import router as {entity}_router` — codegen patches this line |
| `app/modules/__init__.py` | template | empty marker |
| `app/modules/{entity}/__init__.py` | **codegen** | marker |
| `app/modules/{entity}/models.py` | **codegen** | SQLAlchemy model from contract.fields |
| `app/modules/{entity}/schemas.py` | **codegen** | Pydantic v2 schemas (Base/Create/Update/Read + ProblemDetail) |
| `app/modules/{entity}/service.py` | **codegen** | CRUD + AC-11c self-collision logic if email-unique field present |
| `app/modules/{entity}/router.py` | **codegen** | 5 endpoints per contract |
| `app/modules/{entity}/errors.py` | **codegen** | typed exceptions (NotFound, Conflict) |
| `app/modules/{entity}/dependencies.py` | **codegen** | DI factories for the service |
| `tests/conftest.py` | template | event loop, settings, db_engine, session_factory, app, client, seeded_<entity> |
| `tests/integration/test_health.py` | template | `/api/healthz` smoke |
| `tests/integration/test_{list,create,get,update,delete}_<entity>.py` | **codegen** | one per endpoint |
| `tests/unit/test_schemas.py` | **codegen** | Pydantic edge cases per field |
| `tests/unit/test_service.py` | **codegen** | AC-11c + CRUD logic |
| `tests/regression/test_security_regressions.py` | **codegen** | parametrised SQLi-via-path-param |
| `alembic.ini` | template | `script_location = app/db/migrations` · `sqlalchemy.url = ${CRUD_DATABASE_URL}` |
| `pyproject.toml`, `requirements.txt` | template | fastapi 0.110, sqlalchemy 2.x async, pydantic 2, pytest-asyncio |
| `Dockerfile`, `.env.example`, `docker-compose.yml` | template | unchanged from v1 |
| `README.md` | template | "this is the generated backend" |

## Frontend (`templates/frontend-skeleton/` → `runs/<ts>/generated/frontend/`)

| File | Lifecycle | Notes |
|---|---|---|
| `index.html`, `package.json`, `package-lock.json` | template | locked Vite 5 + React 18 + TanStack v5 + shadcn deps |
| All root configs (tsconfig, vite.config, vitest.config, tailwind.config, postcss.config, eslintrc, prettierrc, components.json) | template | unchanged |
| `Dockerfile`, `.env.example`, `README.md` | template | nginx upstream points at `fastapi-new` |
| `src/main.tsx`, `src/index.css`, `src/vite-env.d.ts` | template | bootstrap + Tailwind layers + Vite types |
| `src/App.tsx` | template *with* one templated line | `import {Entity}Page from "@/pages/{Entity}Page"` — codegen patches |
| `src/components/ui/*.tsx` (11 primitives) | template | canonical shadcn templates |
| `src/lib/utils.ts` | template | `cn()` helper |
| `src/lib/problem.ts` | template | `parseProblemDetail` (RFC-9457 generic) |
| `src/api/client.ts` | template | `request()` wrapper + `ApiError` class |
| `src/lib/schemas.ts` | **codegen** | Zod schemas per field — mirrors Pydantic per §9.5 |
| `src/api/{entity}.ts` | **codegen** | typed `list/get/create/update/delete` calls |
| `src/hooks/use{Entity}.ts` | **codegen** | TanStack Query hooks per endpoint |
| `src/types/{entity}.ts` | **codegen** | TS types matching Pydantic schemas |
| `src/pages/{Entity}Page.tsx` | **codegen** | composite page with state cluster |
| `src/components/{Entity}DataTable.tsx` | **codegen** | shadcn `<Table>` per field set |
| `src/components/{Entity}Form.tsx` | **codegen** | RHF + zodResolver per fields |
| `src/components/AddEditDialog.tsx` | **codegen** | Radix `<Dialog>` + key remount |
| `src/components/DeleteAlertDialog.tsx` | **codegen** | Radix `<AlertDialog>` two-step gate |
| `src/components/{EmptyState,ErrorState,LoadingSkeleton,PageHeader}.tsx` | **codegen** | thin wrappers with entity-name copy |
| `tests/setup.ts`, `tests/msw/server.ts` | template | MSW server bootstrap |
| `tests/msw/handlers.ts` | **codegen** | route handlers per endpoint |
| `tests/api-client.test.ts` | template | generic ApiError tests |
| `tests/parse-problem-detail.test.ts` | template | generic |
| `tests/{Entity}{DataTable,Form,AddEditDialog,DeleteAlertDialog,Page}.test.tsx` | **codegen** | one per entity component |

## Dual-run (`templates/dual-run-template/` → `runs/<ts>/dual-run/`)

| File | Lifecycle | Notes |
|---|---|---|
| `docker-compose.yml` | template | 5-service stack, all 8 v1 fixes baked in (CORS as JSON, CRUD_DATABASE_URL, healthcheck `/api/healthz`, fastapi-new upstream, mysql-legacy host) |
| `Dockerfile.php`, `Dockerfile.runner` | template | runner has `playwright==1.47.0` |
| `fastapi-entrypoint.sh` | template | wait-for-PG → alembic upgrade → seed → uvicorn |
| `php-overlay/dbConnection.php` | template | `mysql-legacy` host |
| `parity-runner.py` | template | reads any `fixtures/api-inputs.jsonl` |
| `screenshot-runner.py` | template | reads any 8+8 scenario list (`shape.yaml` provides scenarios) |
| `compose-mosaic.py` | template | builds side-by-side from 8 pairs |
| `seed-pg.sql.example` | example | codegen writes `seed-pg.sql` from contract.seed_rows |
| `seed.sql.example` | example | same for MySQL side |
| `fixtures/api-inputs.jsonl.example` | example | codegen writes a 6-fixture file per shape |

## Counts

- **Stack-stable (templates):** 23 backend + 38 frontend + 12 dual-run = **73 files**
- **Codegen (per entity):** ~9 backend + ~16 frontend + 3 dual-run = **~28 files**
- **Total per engagement:** ~101 files (down from v1's 93 generated + ~10 dual-run = 103)

The win isn't fewer files; it's that **28 files of LLM-written code** vs **101 files of LLM-written code** is what changes — 70%+ reduction in CodeGen agent surface area, and zero risk of LLM drift on stack-stable pieces.

## Templating mechanism (Phase 2 will formalise)

Two patterns the codegen agent must use:

1. **Whole-file generation** for entity-specific files (`models.py`, `service.py`, `{Entity}Page.tsx`, etc.)
2. **One-line patch into templates** for files that mostly belong to the template but need one entity-name reference:
   - `app/main.py` — patch `# CODEGEN_INSERT_ROUTER_IMPORT` and `# CODEGEN_INSERT_ROUTER_MOUNT`
   - `src/App.tsx` — patch `// CODEGEN_INSERT_PAGE_IMPORT` and `// CODEGEN_INSERT_PAGE_ROUTE`

Phase 2 (writing the prompts) will define the exact insertion markers and bake them into the template files.
