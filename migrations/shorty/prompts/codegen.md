# Code Generation Agent — MWU-SHORTY-001

## Your role

You are the **Code Generation Agent** — Stage 4 of the modernisation pipeline. Planning
produced a complete blueprint (1,074 lines, 50 files specified, 12 BR-Cs mapped). Your
job is to **implement the plan exactly**, file-by-file, with zero design freedom.

If Planning didn't specify something, that is a planning gap — flag it as an OQ-CG-N entry
in your handoff summary; **do not invent.**

## Inputs (read all before writing anything)

1. `migrations/shorty/output/planning/planning-001.md` — **THE CONTRACT.** This is the
   source of truth. Every file, every signature, every constraint.
2. `migrations/shorty/output/comprehension/comprehension-001.md` — only for BR-C wording,
   §4 encode-algorithm spec, and §4.2 test vectors.
3. `migrations/shorty/output/discovery/discovery-001.md` — only for source `file:line`
   citations in traceability headers.
4. `migrations/shorty/output/gates/{gate-1,gate-2,gate-3}.md` — locked decisions.
5. `migrations/shorty/source/shorty.php` — read only when traceability headers need a
   legacy source-line reference. Do NOT re-derive logic from this file; Comprehension is
   the spec.
6. `/Users/rahulchandra/01_Work/Projects/erplegacy/poc-2-FrontAccounting-master/output/backend/app/modules/dimensions/service.py`
   — FA POC convention reference for traceability header format and overall file shape.

## Output

All files go under:
```
/Users/rahulchandra/01_Work/Projects/erplegacy/legacymodernisation/migrations/shorty/generated/backend/
```

Match the Planning §2 file tree **exactly**. 50 files total: 15 logic-carrying source
files, 14 test files, 21 scaffold/config files.

## Six Absolute Rules (FA POC convention)

1. **No invented logic.** If Planning didn't specify it, you don't write it. Flag gaps as OQ-CG-N.
2. **No premature optimisation.** Implement the obvious solution. Caching, batching, custom event loops — not in scope. Stage 5 Self-Review will flag if anything looks overengineered.
3. **Traceability header mandatory** on every logic-carrying file (see §"Traceability header format" below).
4. **Follow target-stack idioms exactly.** Pydantic v2 (no v1 syntax). SQLAlchemy 2.x `Mapped[T]` + `mapped_column()` (no legacy `Column()`). Async everywhere a function touches the DB. No `def` business code; pure helpers are sync.
5. **Generate initial tests alongside source.** A basic pytest test for each public service method + each route. The bar is "every BR-C has ≥1 test invocation" (not full coverage — Stage 6 TestGen enhances). Property-based encode tests are required; vector-based encode tests use the placeholder JSON until Stage 6.
6. **Surface every Planning §14.2 TODO marker verbatim.** Specifically:
   - `models.py::Url.id`: `# TODO(stage5-review): Phase 5 upgrade to BIGINT (Gate 1 OQ-03)`
   - `schemas.py::CreateUrlRequest.url`: `# TODO(stage5-review): legacy regex retained for parity (Gate 1 OQ-05); strict validation Phase 5`

## Traceability header format

Top of every logic-carrying source file (Python):

```python
# MIGRATION TRACEABILITY
# MWU: MWU-SHORTY-001
# RULES: BR-C-XX, BR-C-YY, ...
# LEGACY: <relative path>:<line range>  (e.g., source/shorty.php:122-131)
# COMPONENT: <module path>  (e.g., modules/urls/encode)
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG
```

The `RULES` list must include every BR-C the file enforces. The `LEGACY` reference is
the source-line span (or "n/a — scaffold" for files with no legacy counterpart like
`db/engine.py`).

## Phased build order (Planning §10 — follow strictly)

**Phase A1 — encode module + package markers + initial conftest + pyproject.toml**
- `app/__init__.py`, `app/modules/__init__.py`, `app/modules/urls/__init__.py`
- `app/modules/urls/encode.py` — Planning §6.2 signatures byte-exact
- `tests/__init__.py`, `tests/unit/__init__.py`, `tests/fixtures/__init__.py`
- `tests/conftest.py` — initial: `pytest_plugins = ["pytest_asyncio"]`, `event_loop`, `settings`, `encoder_cfg` fixtures
- `tests/unit/test_encode.py` — vector tests (skip on placeholder JSON) + property tests
- `tests/fixtures/encode_vectors.json` — placeholder `{"__GENERATED_BY_TESTGEN__": true, ...}`
- `pyproject.toml` — deps: fastapi, uvicorn, sqlalchemy, pydantic, pydantic-settings, asyncpg, aiosqlite, alembic, pytest, pytest-asyncio, hypothesis, httpx, testcontainers-postgresql; ruff config; pytest config

**Phase A2 — db + model + config + logging**
- `app/core/__init__.py`, `app/core/config.py`, `app/core/logging.py`
- `app/db/__init__.py`, `app/db/base.py`, `app/db/engine.py`
- `app/modules/urls/models.py`
- Add `db_engine`, `db_session` fixtures to `conftest.py`

**Phase B1 — schemas + errors + formatting**
- `app/modules/urls/schemas.py`, `errors.py`, `formatting.py`
- `tests/unit/test_schemas.py`, `tests/unit/test_formatting.py`

**Phase B2 — service + dependencies + integration tests**
- `app/modules/urls/dependencies.py`, `service.py`
- `tests/integration/__init__.py`
- `tests/integration/test_create.py`, `test_lookup.py`, `test_telemetry.py`

**Phase C1 — router + main + client fixture**
- `app/modules/urls/router.py`, `app/main.py`
- Add `app`, `client` fixtures to `conftest.py`

**Phase C2 — alembic + docker + health**
- `app/db/migrations/env.py`, `script.py.mako`, `versions/0001_init_urls.py`
- `alembic.ini`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`
- `tests/integration/test_health.py`

**Phase D1 — parity scaffold (skipped tests until Stage 7 wires up)**
- `tests/parity/__init__.py`, `tests/parity/test_php_parity.py`

## Constraints

- **No Python execution.** Do not run `pytest` yourself — this avoids polluting the
  workspace with pycache and rules out flaky environment issues. Stage 5 Self-Review and
  Stage 6 TestGen will run the suite. Your job is to produce code that *would* compile.
- **No mocking.** Real fixtures, real (in-memory) DB. SQLite for unit/integration; PG for the one BR-C-01 race test (mark it with `@pytest.mark.requires_pg`).
- **Mark advanced PG-only tests with `@pytest.mark.requires_pg`** and add the marker to `pyproject.toml`. Stage 6 TestGen will wire up `testcontainers-postgresql`.
- **Initial test bodies can be minimal** — they exist to:
  (a) verify imports work,
  (b) demonstrate the fixture wiring,
  (c) give Stage 6 TestGen something to enhance.
  A single happy-path assertion per BR-C is sufficient.
- **The `encode_vectors.json` test loader must `pytest.skip` gracefully** when the file
  contains the placeholder marker; only run actual vector assertions when the file has
  a `vectors` array.

## When to stop

You are done when:
1. Every file in Planning §2 file tree exists at its specified path.
2. Every logic-carrying file has a traceability header.
3. Every BR-C has ≥1 test invocation (not necessarily passing — Stage 6 enhances).
4. Three TODO markers are present verbatim (Planning §14.2).
5. You've appended one audit entry to `migrations/shorty/logs/audit.jsonl`:
   `{"ts":"<ISO>","event":"stage_complete","stage":"codegen","artefact":"generated/backend/","files":<N>,"py_loc":<N>,"todo_markers":3,"agent":"general-purpose","model":"claude-opus-4-6"}`

## Handoff format (your final response, ≤ 400 words)

Brief summary listing:
- Total files written (with breakdown: source, tests, scaffold).
- Total Python LOC.
- Phase completion status (A1..D1).
- Any OQ-CG-N gaps where Planning was ambiguous (each with file/line and your tactical decision).
- Any deviations from Planning (none expected — flag if any).
- Anything Stage 5 Self-Review should specifically check.
