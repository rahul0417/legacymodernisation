#!/usr/bin/env python3
"""Synthesize the three fallback recordings from v1 reference data + the captions schedule.

Output: pipeline/shapes/crud/recordings/{1-extract,2-generate,3-verify}.tokens.jsonl

Each file is a JSONL stream of bus events with `t` = ms-from-stage-start. The
fallback-player.js replays each at its original offset; the cockpit re-renders
captions + tokens identically to a live run.

Run-time: ~1 sec. Idempotent — overwrites existing files.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHAPE_DIR = REPO / "shapes" / "crud"
RECORDINGS_DIR = SHAPE_DIR / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


def ts_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def event(t_ms: int, etype: str, **payload) -> dict:
    """Build one bus-style event (matches what server.js recording mode writes)."""
    return {
        "t": t_ms,
        "type": etype,
        "ts": ts_now_iso(),
        **payload,
    }


def cap(t_ms: int, stage: str, text: str, source: str = "scripted") -> dict:
    return event(t_ms, "stage:caption", stage=stage, text=text, at_ms=t_ms, source=source)


def token_text(t_ms: int, stage: str, text: str) -> dict:
    return event(t_ms, "stage:token", stage=stage, kind="text", text=text)


def token_thinking(t_ms: int, stage: str, text: str) -> dict:
    return event(t_ms, "stage:token", stage=stage, kind="thinking", text=text)


def token_tool_use(t_ms: int, stage: str, tool: str, args_brief: str = "") -> dict:
    return event(t_ms, "stage:token", stage=stage, kind="tool_use", tool=tool, args_brief=args_brief)


def token_tool_result(t_ms: int, stage: str, text: str, is_error: bool = False) -> dict:
    return event(t_ms, "stage:token", stage=stage, kind="tool_result", text=text, is_error=is_error)


def settle(t_ms: int, stage: str, tokens: int, tool_uses: int) -> dict:
    return event(t_ms, "stage:settle", stage=stage, ok=True, tokens=tokens, tool_uses=tool_uses)


def write_jsonl(path: Path, events: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"  ✓ {path.relative_to(REPO)}  ({len(events)} events · {path.stat().st_size:,} bytes)")


# ── Stage 1 — Extract (90s · ~30 events) ─────────────────────────────────────

def stage_1_extract() -> list[dict]:
    s = "1-extract"
    e: list[dict] = []
    e.append(cap(100, s, "Reading 7 PHP files from chapagain/crud-php-simple…"))
    e.append(token_tool_use(1500, s, "Glob", "pattern=*.php"))
    e.append(token_tool_result(2000, s, "/migrations/crud/source/index.php\n/migrations/crud/source/add.php\n/migrations/crud/source/addAction.php\n/migrations/crud/source/edit.php\n/migrations/crud/source/editAction.php\n/migrations/crud/source/delete.php"))
    e.append(token_text(3500, s, "I'll read all 7 source files in parallel to understand the shape."))
    e.append(token_tool_use(4000, s, "Read", "file_path=…/source/index.php"))
    e.append(token_tool_use(4100, s, "Read", "file_path=…/source/add.php"))
    e.append(token_tool_use(4200, s, "Read", "file_path=…/source/addAction.php"))
    e.append(token_tool_use(4300, s, "Read", "file_path=…/source/edit.php"))
    e.append(token_tool_use(4400, s, "Read", "file_path=…/source/editAction.php"))
    e.append(token_tool_use(4500, s, "Read", "file_path=…/source/delete.php"))
    e.append(token_tool_use(4600, s, "Read", "file_path=…/source/database.sql"))
    e.append(token_tool_result(5200, s, "55 lines · list users + bare HTML table"))
    e.append(token_tool_result(5300, s, "40 lines · add form"))
    e.append(token_tool_result(5400, s, "24 lines · POST → mysqli_query INSERT"))
    e.append(token_tool_result(5500, s, "55 lines · edit form · SQLi sink at L9"))
    e.append(token_tool_result(5600, s, "28 lines · POST → mysqli_query UPDATE"))
    e.append(token_tool_result(5700, s, "20 lines · DELETE via GET · SQLi at L6,9"))
    e.append(token_tool_result(5800, s, "12 lines · users DDL · id PK · name VARCHAR(100) · age INT · email VARCHAR(100)"))
    e.append(cap(8000, s, "Found `users` entity — 4 fields, single table, mysqli backend."))
    e.append(token_text(11000, s, "Entity is `users` (singular: user, pascal: User). Four columns: id (PK, auto-increment), name, age (int), email (max 100). Single table, no joins."))
    e.append(token_thinking(14000, s, "Need to enumerate the 5 REST endpoints from the page handlers, plus add GET /api/users/{id} for the read-one route which legacy doesn't expose but the new contract requires…"))
    e.append(cap(18000, s, "Extracting business rules from CRUD handlers…"))
    e.append(token_tool_use(21000, s, "Grep", "pattern=ORDER BY"))
    e.append(token_tool_result(21500, s, "1 match · index.php:6 · ORDER BY id DESC — list is newest-first"))
    e.append(token_tool_use(24000, s, "Grep", "pattern=validation|required"))
    e.append(token_tool_result(24500, s, "no server-side validation in legacy · all input trusted"))
    e.append(token_text(27000, s, "AC-1: list newest-first. AC-2: all fields required. AC-3: email UNIQUE → 409. AC-4: type coercion on path-id. AC-5: 404 on missing. AC-6: age range 0-150…"))
    e.append(cap(32000, s, "11 acceptance criteria identified — including the AC self-collision branch (often missed)."))
    e.append(token_text(35000, s, "AC-7 (self-collision): PUT same email back to same user MUST return 200, not 409. Legacy doesn't model this — it would just silently re-write the same row. The new contract makes it explicit."))
    e.append(token_tool_use(38000, s, "Grep", "pattern=mysqli_query"))
    e.append(token_tool_result(38500, s, "6 matches · 2 with unescaped interpolation: edit.php:9 and delete.php:6,9"))
    e.append(cap(45000, s, "2 critical SQL injection sites flagged: edit.php:9 and delete.php:6,9."))
    e.append(token_text(48000, s, 'edit.php:9 — "SELECT * FROM users WHERE id=$id" — $_GET[\'id\'] interpolated raw'))
    e.append(token_text(51000, s, 'delete.php:6 — "DELETE FROM users WHERE id=$id" — same pattern'))
    e.append(token_thinking(54000, s, "Both auto-resolve in the new contract via FastAPI Path(..., gt=0). Non-int path → 422 before any SQL runs. Documenting as RF-001/002 with auto_resolved_by note…"))
    e.append(cap(60000, s, "Auto-mitigation: Path(gt=0) coercion in FastAPI converts both into 422 Unprocessable Entity."))
    e.append(token_text(63000, s, "Compiling contract.json with 4 fields, 5 endpoints, 11 ACs, 2 risk flags, 5 seed rows…"))
    e.append(token_tool_use(67000, s, "Write", "file_path=…/runs/<ts>/contract.json"))
    e.append(token_tool_result(71000, s, "187 lines written · schema_version: 1 · entity.name_plural: users · 5 endpoints · ✓"))
    e.append(cap(75000, s, "Contract written to runs/<ts>/contract.json. Stage 1 complete."))
    e.append(token_text(82000, s, "Stage 1 complete. Contract ready for Stage 2 — Generate."))
    e.append(settle(87000, s, tokens=len(e) + 1, tool_uses=11))
    return e


# ── Stage 2 — Generate (420s · ~80 events) ───────────────────────────────────

def stage_2_generate() -> list[dict]:
    s = "2-generate"
    e: list[dict] = []
    e.append(cap(100, s, "Copying 73 stack-stable template files into the generated tree…"))
    e.append(token_tool_use(1500, s, "Bash", "mkdir -p {target}/{backend,frontend,dual-run}"))
    e.append(token_tool_result(2200, s, "ok"))
    e.append(token_tool_use(3000, s, "Bash", "cp -R pipeline/templates/backend-skeleton/. …/backend/"))
    e.append(token_tool_result(3800, s, "23 files copied"))
    e.append(token_tool_use(4500, s, "Bash", "cp -R pipeline/templates/frontend-skeleton/. …/frontend/"))
    e.append(token_tool_result(5800, s, "38 files copied"))
    e.append(token_tool_use(6500, s, "Bash", "cp -R pipeline/templates/dual-run-template/. …/dual-run/"))
    e.append(token_tool_result(7400, s, "12 files copied"))
    e.append(cap(8000, s, "Templates copied — shadcn primitives, configs, conftest, exception handlers all pre-vendored."))
    e.append(token_tool_use(11000, s, "Read", "file_path=…/runs/<ts>/contract.json"))
    e.append(token_tool_result(12000, s, "187 lines · entity.users · 4 fields · 5 endpoints · 11 ACs · 2 RFs"))
    e.append(token_text(14000, s, "Contract loaded. Now writing the 28 entity-specific files. Starting with the SQLAlchemy model."))
    e.append(cap(20000, s, "Writing backend: SQLAlchemy User model with UNIQUE(email) and CHECK(age 0–150)…"))
    e.append(token_tool_use(22000, s, "Write", "file_path=…/backend/app/modules/users/models.py"))
    e.append(token_tool_result(28000, s, "70 lines · Mapped[int] PK · UniqueConstraint email · CheckConstraint age 0-150"))
    e.append(token_tool_use(31000, s, "Write", "file_path=…/backend/app/modules/users/schemas.py"))
    e.append(token_tool_result(38000, s, "120 lines · UserBase/Create/Update/Read · ProblemDetail · HealthResponse · EmailStr · strict=True age"))
    e.append(cap(45000, s, "Pydantic schemas with EmailStr and strict=True on age (rejects float coercion)."))
    e.append(token_tool_use(48000, s, "Write", "file_path=…/backend/app/modules/users/errors.py"))
    e.append(token_tool_result(52000, s, "35 lines · UserNotFound · EmailAlreadyExists · UsersError base"))
    e.append(token_thinking(55000, s, "Service layer is the most subtle file — AC-7 (self-collision) requires the re-fetch + id-compare pattern after IntegrityError. Easy to miss…"))
    e.append(token_tool_use(60000, s, "Write", "file_path=…/backend/app/modules/users/service.py"))
    e.append(token_tool_result(68000, s, "195 lines · async CRUD · self-collision branch wired"))
    e.append(cap(70000, s, "UserService.update_user implements the self-collision branch: same email back to same row returns 200."))
    e.append(token_tool_use(74000, s, "Write", "file_path=…/backend/app/modules/users/dependencies.py"))
    e.append(token_tool_result(78000, s, "45 lines · init_user_service · get_user_service · set_settings"))
    e.append(token_tool_use(82000, s, "Write", "file_path=…/backend/app/modules/users/router.py"))
    e.append(token_tool_result(92000, s, "164 lines · 5 endpoints · @router.delete only · Path(gt=0) on id params"))
    e.append(cap(100000, s, "FastAPI router: 5 endpoints, all path params coerced via Path(gt=0)."))
    e.append(token_tool_use(105000, s, "Write", "file_path=…/backend/app/main.py"))
    e.append(token_tool_result(110000, s, "215 lines · CORS · ProblemDetail handlers · /api/healthz · /api/openapi.json"))
    e.append(token_tool_use(114000, s, "Write", "file_path=…/backend/app/db/migrations/versions/0001_init_users.py"))
    e.append(token_tool_result(120000, s, "50 lines · op.create_table users · UNIQUE(email) · CHECK(age 0-150)"))
    e.append(cap(130000, s, "Alembic migration scaffolded — Identity PK, unique index, range check."))
    e.append(token_text(135000, s, "Backend done. Now the frontend: types, Zod schemas, API client, hooks, page, components, tests…"))
    e.append(token_tool_use(140000, s, "Write", "file_path=…/frontend/src/types/user.ts"))
    e.append(token_tool_result(143000, s, "18 lines · User interface"))
    e.append(token_tool_use(147000, s, "Write", "file_path=…/frontend/src/lib/schemas.ts"))
    e.append(token_tool_result(155000, s, "35 lines · userFormSchema · z.coerce.number().int() · message parity with Pydantic"))
    e.append(cap(165000, s, "Frontend: building UsersPage with shadcn DataTable + AddEditDialog + DeleteAlertDialog…"))
    e.append(token_tool_use(170000, s, "Write", "file_path=…/frontend/src/api/users.ts"))
    e.append(token_tool_result(175000, s, "60 lines · listUsers / getUser / createUser / updateUser / deleteUser"))
    e.append(token_tool_use(180000, s, "Write", "file_path=…/frontend/src/hooks/useUsers.ts"))
    e.append(token_tool_result(190000, s, "95 lines · useUsersQuery + 3 mutation hooks · (...args) rest forwarding"))
    e.append(cap(210000, s, "Zod schemas mirror Pydantic — message parity locked verbatim."))
    e.append(token_tool_use(215000, s, "Write", "file_path=…/frontend/src/pages/UsersPage.tsx"))
    e.append(token_tool_result(228000, s, '231 lines · state cluster · key={editingUser?.id ?? "add"} verbatim on AddEditDialog'))
    e.append(token_tool_use(232000, s, "Write", "file_path=…/frontend/src/components/UsersDataTable.tsx"))
    e.append(token_tool_result(238000, s, "88 lines · shadcn Table · aria-label on row actions"))
    e.append(token_tool_use(242000, s, "Write", "file_path=…/frontend/src/components/UserForm.tsx"))
    e.append(token_tool_result(252000, s, "188 lines · useForm + zodResolver · 409 projection BEFORE empty-errors early-return"))
    e.append(cap(255000, s, "TanStack Query hooks wired with v5 rest-args pattern."))
    e.append(token_tool_use(260000, s, "Write", "file_path=…/frontend/src/components/AddEditDialog.tsx"))
    e.append(token_tool_result(265000, s, "90 lines · Radix Dialog · UserForm child · mode switches title"))
    e.append(token_tool_use(270000, s, "Write", "file_path=…/frontend/src/components/DeleteAlertDialog.tsx"))
    e.append(token_tool_result(275000, s, "91 lines · Radix AlertDialog · destructive variant · e.preventDefault on action click"))
    e.append(token_tool_use(280000, s, "Write", "file_path=…/frontend/src/components/{EmptyState,ErrorState,LoadingSkeleton,PageHeader}.tsx"))
    e.append(token_tool_result(287000, s, "4 files · 35-50 lines each · entity-named copy"))
    e.append(cap(290000, s, "UserForm.tsx: 409 projection runs BEFORE empty-errors early-return (CR-3 fix)."))
    e.append(token_tool_use(294000, s, "Write", "file_path=…/frontend/src/App.tsx (overwrite)"))
    e.append(token_tool_result(297000, s, "12 lines · <UsersPage /> mounted on /"))
    e.append(token_text(300000, s, "Writing tests now: unit, integration, regression, plus 5 frontend component tests…"))
    e.append(token_tool_use(305000, s, "Write", "file_path=…/backend/tests/integration/test_list_users.py"))
    e.append(token_tool_result(310000, s, "5 tests · happy path + 404 + ordering"))
    e.append(token_tool_use(312000, s, "Write", "file_path=…/backend/tests/integration/test_create_user.py"))
    e.append(token_tool_result(317000, s, "8 tests · valid + 4 validation errors + 409 duplicate"))
    e.append(token_tool_use(319000, s, "Write", "file_path=…/backend/tests/integration/test_update_user.py"))
    e.append(token_tool_result(325000, s, "7 tests · including AC-7 self-collision (PUT same email → 200)"))
    e.append(token_tool_use(327000, s, "Write", "file_path=…/backend/tests/regression/test_security_regressions.py"))
    e.append(token_tool_result(333000, s, "93 lines · parametrised SQLi: 5 payloads × {GET,PUT,DELETE} = 15 cases"))
    e.append(cap(330000, s, "MSW handlers + vitest specs written per endpoint."))
    e.append(token_tool_use(338000, s, "Write", "file_path=…/frontend/tests/UsersPage.test.tsx"))
    e.append(token_tool_result(346000, s, "9 tests · render, empty, error, loading, retry"))
    e.append(token_tool_use(348000, s, "Write", "file_path=…/frontend/tests/AddEditDialog.test.tsx"))
    e.append(token_tool_result(360000, s, "11 tests · validation per field + 409/422 prop acceptance"))
    e.append(token_tool_use(363000, s, "Write", "file_path=…/dual-run/seed-pg.sql + seed.sql + fixtures/api-inputs.jsonl"))
    e.append(token_tool_result(370000, s, "3 files · 5 seed rows per DB · 14 API fixtures"))
    e.append(cap(370000, s, "Dual-run scaffolding: seed-pg.sql, seed.sql, 6 API smoke fixtures."))
    e.append(token_text(385000, s, "All 28 entity-specific files written. Traceability headers on every file. Locks honored."))
    e.append(cap(410000, s, "28 entity-specific files written. Stage 2 complete."))
    e.append(settle(415000, s, tokens=len(e) + 1, tool_uses=33))
    return e


# ── Stage 3 — Verify (300s · ~50 events) ────────────────────────────────────

def stage_3_verify() -> list[dict]:
    s = "3-verify"
    e: list[dict] = []
    e.append(cap(100, s, "Running 12 deterministic static checks — layer firewall, no innerHTML, AC-self-collision, DELETE purity…"))
    e.append(token_tool_use(1500, s, "Bash", "bash pipeline/scripts/self-review.sh {generated_dir}"))
    e.append(token_tool_result(7000, s, "1. Layer firewall ✓\n2. No dangerouslySetInnerHTML ✓\n3. Key remount ✓\n4. Self-collision branch ✓\n5. ProblemDetail shape ✓\n6. Zod parity ✓\n7. Traceability headers ✓\n8. No SQL concat ✓\n9. DELETE purity ✓\n10. TS strict ✓\n11. Ruff configured ✓\n12. Test scaffold ✓\nSUMMARY: 12 PASS · 0 FAIL"))
    e.append(cap(12000, s, "All 12 checks PASS."))
    e.append(token_tool_use(15000, s, "Bash", "python3.12 -m venv .venv && .venv/bin/pip install -e .[test]"))
    e.append(token_tool_result(45000, s, "Successfully installed fastapi-0.110 sqlalchemy-2.0 pydantic-2.7 pytest-8.4 …"))
    e.append(cap(18000, s, "Creating .venv, installing test dependencies for pytest…"))
    e.append(token_tool_use(48000, s, "Bash", ".venv/bin/pytest tests/ -q --tb=short"))
    e.append(token_thinking(50000, s, "pytest running across unit/integration/regression dirs. Watching for AC-7 self-collision test in particular…"))
    e.append(token_tool_result(75000, s, "72 passed, 1 warning in 8.42s\nBreakdown: unit:18 · integration:39 · regression:15"))
    e.append(cap(55000, s, "Running pytest: unit + integration + regression…"))
    e.append(token_text(78000, s, "72 backend tests pass, 0 failed. Including AC-7 self-collision (PUT same email → 200)."))
    e.append(cap(78000, s, "72 pytest tests pass, 0 failed."))
    e.append(token_tool_use(82000, s, "Bash", "npm install --no-audit --no-fund"))
    e.append(token_tool_result(110000, s, "added 312 packages in 24s"))
    e.append(cap(85000, s, "Installing npm deps + running vitest…"))
    e.append(token_tool_use(115000, s, "Bash", "npx vitest run --reporter=basic"))
    e.append(token_tool_result(135000, s, "Test Files  6 passed (6)\nTests  35 passed (35)\nDuration  9.12s"))
    e.append(token_text(140000, s, "35 frontend tests pass. Total: 107 / 107 green across both suites."))
    e.append(cap(130000, s, "35 vitest tests pass. Total: 107/107 green across both suites."))
    e.append(token_tool_use(150000, s, "Bash", "cd dual-run && docker compose build"))
    e.append(token_tool_result(165000, s, "Image dual-run-php-legacy Built\nImage dual-run-react-new Built\nImage dual-run-fastapi-new Built"))
    e.append(cap(145000, s, "Bringing up 5-service docker stack on private network…"))
    e.append(token_tool_use(168000, s, "Bash", "docker compose up -d"))
    e.append(token_tool_result(190000, s, "Container dual-run-mysql-legacy-1 Healthy\nContainer dual-run-pg-new-1 Healthy\nContainer dual-run-fastapi-new-1 Healthy\nContainer dual-run-php-legacy-1 Healthy\nContainer dual-run-react-new-1 Running"))
    e.append(token_text(195000, s, "Stack up. Both apps responding: PHP at :21080, React at :21173, FastAPI at :21800."))
    e.append(cap(175000, s, "MySQL + Postgres + PHP-Apache + FastAPI + React/nginx — all healthcheck-green."))
    e.append(token_tool_use(205000, s, "Bash", "docker compose --profile run run --rm parity-runner"))
    e.append(token_tool_result(225000, s, "[crud-parity] loaded 14 fixtures · target=http://fastapi-new:8000\n  LIST-1             PASS  (HTTP 200)\n  GET-1              PASS  (HTTP 200)\n  GET-42             PASS  (HTTP 404)\n  CREATE-OK          PASS  (HTTP 201)\n  CREATE-DUP         PASS  (HTTP 409)\n  CREATE-BAD-EMAIL   PASS  (HTTP 422)\n  CREATE-AGE-LOW     PASS  (HTTP 422)\n  CREATE-AGE-HIGH    PASS  (HTTP 422)\n  CREATE-EMPTY-NAME  PASS  (HTTP 422)\n  UPDATE-OK          PASS  (HTTP 200)\n  UPDATE-404         PASS  (HTTP 404)\n  DELETE-OK          PASS  (HTTP 204)\n  DELETE-404         PASS  (HTTP 404)\n  LIST-AFTER         PASS  (HTTP 200)\n\n[crud-parity] 14 PASS · 0 FAIL"))
    e.append(cap(200000, s, "Running 14 API smoke fixtures against the new FastAPI…"))
    e.append(token_text(230000, s, "14/14 API fixtures pass. ProblemDetail bodies match Comprehension §4.4 shape on every error case."))
    e.append(cap(225000, s, "14/14 API fixtures PASS. Visual capture next."))
    e.append(token_tool_use(238000, s, "Bash", "docker compose --profile screenshot run --rm screenshot-runner"))
    e.append(token_thinking(245000, s, "Playwright capturing 16 scenarios across both apps. The 'old vs new' mosaic is the load-bearing demo asset…"))
    e.append(token_tool_result(265000, s, "[screenshot] /app/screenshots/old-01-list.png\n[screenshot] /app/screenshots/old-02-add-form.png\n[screenshot] /app/screenshots/old-03-edit-form-id1.png\n... \n[screenshot] /app/screenshots/new-08-empty-state.png\n[screenshot] all 16 captured"))
    e.append(cap(235000, s, "Playwright capturing 16 screenshots — 8 legacy bare-HTML states + 8 new SPA states."))
    e.append(token_tool_use(270000, s, "Bash", "python3 compose-mosaic.py"))
    e.append(token_tool_result(278000, s, "[mosaic] wrote …/screenshots/mosaic.png (1188×3320, 8 pairs)"))
    e.append(cap(275000, s, "All screenshots captured. Composing side-by-side mosaic…"))
    e.append(token_tool_use(282000, s, "Bash", "docker compose down -v --remove-orphans"))
    e.append(token_tool_result(290000, s, "Stack torn down cleanly."))
    e.append(token_tool_use(292000, s, "Write", "file_path=…/runs/<ts>/verify-report.md"))
    e.append(token_tool_result(295000, s, "76 lines · all green · ready for cockpit celebration"))
    e.append(cap(295000, s, "Mosaic ready. Visual transformation complete."))
    e.append(settle(298000, s, tokens=len(e) + 1, tool_uses=12))
    return e


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"Synthesizing fallback recordings into {RECORDINGS_DIR.relative_to(REPO.parent)}")
    print()
    write_jsonl(RECORDINGS_DIR / "1-extract.tokens.jsonl", stage_1_extract())
    write_jsonl(RECORDINGS_DIR / "2-generate.tokens.jsonl", stage_2_generate())
    write_jsonl(RECORDINGS_DIR / "3-verify.tokens.jsonl", stage_3_verify())
    print()
    print(f"Done. Re-run anytime to regenerate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
