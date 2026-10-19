# Gate 5 — TestGen (PNS-CRUD-001)

**Date:** 2026-05-14
**Reviewer:** Rahul Chandra (HITL)
**Stage:** TestGen (`output/testgen/testgen-001.md`)
**Status:** ✅ **APPROVED**

## Summary

Both test suites run green end-to-end.

| Suite | Before Stage 6 | After Stage 6 | Result |
|---|---|---|---|
| Backend pytest | 57/58 collected | **72 / 72 passed** | 0 failed · 1 warning |
| Frontend vitest | 19/21 collected | **35 / 35 passed** | 0 failed |
| **Total** | 76 / 79 | **107 / 107** | 0 failed |

11 / 11 BR-Cs have ≥1 backend test and (where UI applies) ≥1 frontend test.

## Gate-4 carried items — all resolved

| ID | File | Status |
|---|---|---|
| R-1 | `frontend/src/pages/UsersPage.tsx:204` — `key={editingUser?.id ?? "add"}` verbatim per Gate-3 lock #2. | ✅ Done |
| R-2 | `frontend/tests/parse-problem-detail.test.ts` — 9 new unit tests covering loc[last] extraction, multiple errors, no-errors fallback, non-object body, deeply-nested loc, numeric loc, empty loc, missing msg, safe defaults. | ✅ Done |
| R-3 | `backend/app/db/engine.py:46-60` — guards `pool_size` / `max_overflow` so they're only passed when URL is not `sqlite+aiosqlite://`. | ✅ Done |

## Additional enhancements applied by TestGen

- Backend AC-11c retry path: PUT same email 3× → 200 each time (separate from the existing 409 case).
- Backend SQL-injection regression parametrised from 2 → **15 cases** (5 payloads × GET / PUT / DELETE) — all return 422 (none 500).
- Frontend AddEditDialog: empty name, age=-1, age=151, invalid email, 409 prop acceptance, 422 prop acceptance, submitting disables both buttons.
- Frontend a11y: explicit row-actions `aria-label` coverage on UsersDataTable (WCAG 4.1.2).

## Defect carried + immediately fixed at this gate

**CR-3 — UserForm.tsx 409 short-circuit**
- File: `frontend/src/components/UserForm.tsx:65-83`
- Issue: early-return on `error.errors.length === 0` ran before the `error.status === 409` branch, so 409 email-conflict detail never reached the inline `<FormMessage>`. Functionally still surfaced via the dialog-stays-open path, but BR-C-11 inline projection was bypassed.
- Fix applied in-place: moved the 409 branch above the early-return. Behaviour restored. Frontend vitest re-run after the fix: **35 / 35 still pass**.

## Environment notes

- Backend `.venv` created with `python3.12 -m venv` + `pip install -e ".[test]"`. pytest-asyncio session-scoped `event_loop` fixture emits one deprecation warning (pre-existing, recorded for Phase 5).
- Vitest config uses `environment: "jsdom"` (locked Planning §11.2; brief mentioned happy-dom but we kept the locked choice).
- Stray Radix `act(...)` warnings under jsdom + Dialog portals are harmless and deterministic.

---

**Next stage:** Stage 7 dual-run + visual transformation capture. Brings up 5 services on a private docker network, runs the API smoke suite (14 fixtures), captures 16 Playwright screenshots (8 legacy + 8 new). Subagent: none — driven directly through `docker compose` from this session.
