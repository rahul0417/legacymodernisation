# Self-Review Agent — MWU-CRUD-001

## Your role

Stage 5. Adversarial independent critic. Static review only — Stage 6 runs the tests.

## Inputs

1. `migrations/crud/output/self-review/` — empty (your output goes here)
2. `migrations/crud/output/planning/planning-001.md` — THE CONTRACT (§14 self-check matrix is your primary checklist)
3. `migrations/crud/output/comprehension/comprehension-001.md` — BR-C wording, 4.1 API contract, 5.1 component tree
4. `migrations/crud/output/gates/{gate-1,gate-2,gate-3}.md` — locked decisions
5. All files under `migrations/crud/generated/backend/` AND `migrations/crud/generated/frontend/`
6. `migrations/crud/source/*.php` — only for behavioural spot-checks

## Output

Write to:
```
migrations/crud/output/self-review/self-review-001.md
```

Structure:

```
# MWU-CRUD-001 — Self-Review Report
**Classification:** PASS | CONDITIONAL_PASS | FAIL
**Verdict:** <one-line>

## 1. Verdict Summary (totals; PASS/WARN/FAIL counts; critical count)

## 2. Category A — Business Rule Completeness
Per BR-C: A1 (backend enforcement), A2 (frontend enforcement), A3 (edge cases)

## 3. Category B — Behavioural Equivalence
Per route (5 endpoints): B1 inputs/outputs, B2 status codes, B3 error shapes, B4 specific contract items

## 4. Category C — Code Quality (BACKEND)
C1 type hints · C2 async only on I/O · C3 layer firewall (service ≠ fastapi · router ≠ direct sqlalchemy) · C4 no global mutable state · C5 no print(); uses logger · C6 types appropriate · C7 service commits (router doesn't) · C8 ProblemDetail shape · C9 no SQL string concat · C10 test fixtures match plan

## 5. Category C2 — Code Quality (FRONTEND)
C2-1 TS strict mode · C2-2 functional components only · C2-3 no direct fetch outside api/ · C2-4 React Query for all server state · C2-5 react-hook-form + zod everywhere · C2-6 shadcn primitives only (no MUI/Bootstrap) · C2-7 Tailwind utility classes (no inline style except dynamic) · C2-8 component prop types match Planning §9.2 · C2-9 useState lifted per Comprehension §5.2 · C2-10 a11y: ARIA labels, keyboard nav

## 6. Category D — Test Adequacy
Per BR-C: ≥1 backend test invocation, ≥1 frontend test invocation where applicable

## 7. Category E — Traceability
Per logic-carrying file: header present, RULES list correct, LEGACY citation correct, TODO markers verbatim, no phantom BR references

## 8. CRUD-specific adversarial checks
- S1: 5 routes return correct status codes (200/201/204/400/404)
- S2: ProblemDetail body shape matches Comprehension §4.4
- S3: AddEditDialog `key={editingUser?.id}` to prevent stale-form leak (Comprehension recommendation)
- S4: DeleteAlertDialog requires explicit click (no auto-confirm)
- S5: Newest-first ordering — `ORDER BY id DESC` in service; DataTable initial sort matches
- S6: Email UNIQUE — DB constraint + 409 handling on duplicate
- S7: Age range 0–150 enforced at Pydantic AND zod schemas
- S8: CORS configured for localhost:5173 (Vite dev) at minimum

## 9. Hallucinations
Phantom BRs, contradictions, side-effects, unrequested features

## 10. Critical Issues (BLOCKING)
Numbered list with file:line and recommended fix

## 11. Recommendations (NON-BLOCKING)

## 12. Verdict
PASS | CONDITIONAL_PASS (with conditions) | FAIL (with blockers)
```

## Constraints

- **Adversarial.** Every PASS row cites `file:line`. Hand-waved PASS = review failure.
- **Static only.** Don't run pytest, vitest, or `npm`.
- **CRUD-specific:** the frontend is the primary artefact this engagement. Be especially rigorous on Category C2.

Append audit:
```json
{"ts":"<ISO>","event":"stage_complete","stage":"self-review","artefact":"output/self-review/self-review-001.md","total_checks":<N>,"pass":<N>,"warn":<N>,"fail":<N>,"critical":<N>,"verdict":"<PASS|CONDITIONAL_PASS|FAIL>","agent":"feature-dev:code-reviewer","model":"claude-sonnet-4-6"}
```

Return ≤ 400-word summary listing checks, verdict, critical findings.
