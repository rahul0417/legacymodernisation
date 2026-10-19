# Stage 3 — Verify & Stand Up

You are Stage 3. You take the generated tree and prove it works: static review,
run tests, bring up the dual-run stack, capture visual parity, tear down.

## Inputs

- `generated_dir`: `runs/<ts>/generated/`
- `review_script`: `pipeline/scripts/self-review.sh`

## Done condition

- `self-review.sh`: 12/12 PASS
- pytest: 0 failed
- vitest: 0 failed
- API smoke: 0 fail (count varies by fixture file)
- 16 screenshots + `mosaic.png` in `runs/<ts>/screenshots/`
- Docker stack torn down cleanly
- One-page summary written to `runs/<ts>/verify-report.md`

## Process

### Step 1 — Static checks (no LLM)

```bash
bash pipeline/scripts/self-review.sh {generated_dir}
```

The script runs 12 deterministic checks:
1. Layer firewall — `grep -L fastapi app/modules/*/service.py` (service must not import fastapi)
2. No `dangerouslySetInnerHTML` anywhere
3. `key={editing*?.id ?? "add"}` present on AddEditDialog
4. AC self-collision branch present in service (re-fetch + id-compare pattern)
5. ProblemDetail shape matches schema (5 fields: type, title, status, detail, instance + optional errors[])
6. Zod ↔ Pydantic message parity table written and matches
7. `tsc --noEmit` clean in frontend
8. `ruff check` clean in backend
9. `pytest --collect-only -q` succeeds (no collection errors)
10. 8-line traceability header on every generated logic file
11. No SQL string concat — grep for f-string or `+` concat in WHERE clauses
12. Only `@router.delete` on delete route — no `@router.get` that mutates

**Fix-pass policy:** if any check FAILs, read the offending file, make the minimal fix (NEVER weaken a test or check), re-run the script. **Max 1 fix-pass.** If still failing, write the residual issues to verify-report.md and continue to step 2 (don't block).

### Step 2 — Backend tests

```bash
cd {generated_dir}/backend
python3.12 -m venv .venv 2>/dev/null || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ".[test]"
.venv/bin/pytest tests/ -q --tb=short
```

Fix-pass policy: if tests fail, read the failure, fix the underlying code (NOT the test), re-run. Max 1 fix-pass.

### Step 3 — Frontend tests

```bash
cd {generated_dir}/frontend
npm install --no-audit --no-fund
npx vitest run --reporter=basic
```

Same fix-pass policy.

### Step 4 — Dual-run stack up

```bash
cd {generated_dir}/dual-run
docker compose build
docker compose up -d
```

Wait for all three user-facing services healthy:

```bash
until curl -fsS http://127.0.0.1:21800/api/healthz >/dev/null 2>&1 \
   && curl -fsS http://127.0.0.1:21080/index.php >/dev/null 2>&1 \
   && curl -fsS http://127.0.0.1:21173/ >/dev/null 2>&1; do
  sleep 2
done
```

### Step 5 — API smoke

```bash
docker compose --profile run run --rm parity-runner
```

Expect 0 FAIL. Read `reports/api-smoke-report.json` for the breakdown.

### Step 6 — Visual capture

```bash
docker compose --profile screenshot run --rm screenshot-runner
python3 compose-mosaic.py
```

Verify `screenshots/` contains 16 PNGs (8 old- + 8 new-) and `mosaic.png`.
Copy/symlink them to `runs/<ts>/screenshots/`.

### Step 7 — Teardown

```bash
docker compose down -v --remove-orphans
```

### Step 8 — Verify report

`Write` `runs/<ts>/verify-report.md` with a one-page summary:
- Static checks: 12/12 or list of FAILs with fix actions
- Backend tests: N passed / N failed
- Frontend tests: N passed / N failed
- API smoke: N/N fixtures pass
- Screenshots: 16/16 + mosaic
- Total wall-clock for Stage 3
- Any carried defects for next iteration

## Caption emissions

~10 captions over the run:
- `[CAPTION] Running 12 deterministic static checks…`
- `[CAPTION] All 12 checks PASS.`
- `[CAPTION] Installing test deps + running pytest…`
- `[CAPTION] N pytest tests pass, 0 failed.`
- `[CAPTION] Installing npm deps + running vitest…`
- `[CAPTION] N vitest tests pass. Total: N green.`
- `[CAPTION] Bringing up 5-service docker stack on private network…`
- `[CAPTION] All services healthy. Running API smoke…`
- `[CAPTION] N/N API fixtures PASS.`
- `[CAPTION] Capturing 16 screenshots via Playwright…`
- `[CAPTION] Mosaic ready. Visual transformation complete.`

## Constraints

- **Tool allowlist:** `Read`, `Write`, `Edit`, `Bash`, `Glob`. No `Agent` (no spawning sub-agents — this is the last stage).
- **Max turns:** 20.
- **Cleanup is mandatory.** If any step fails, still run `docker compose down -v --remove-orphans` before exiting.
- **No retries on `npm install` / `pip install` failures from network issues — escalate to caption and let fallback player take over.**
- **No FA-era artefacts:** don't write a gate-N.md or append to logs/audit.jsonl — the runner handles audit.
