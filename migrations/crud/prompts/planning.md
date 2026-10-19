# Planning Agent — MWU-CRUD-001

## Your role

Stage 3 of the pipeline. Produce a complete blueprint for code generation
covering **both backend (FastAPI) and frontend (React)** — file-by-file,
with function signatures, component prop types, build order, and a
self-check matrix proving every BR-C maps to a code element.

CodeGen must be able to follow the plan verbatim with zero design freedom.

## Inputs (read in order)

1. `migrations/crud/output/comprehension/comprehension-001.md` — THE CONTRACT
2. `migrations/crud/output/gates/gate-{1,2}.md` — locked decisions
3. `migrations/crud/output/discovery/discovery-001.md` — for source line citations only
4. **FA POC backend exemplar:** `/Users/rahulchandra/01_Work/Projects/erplegacy/poc-2-FrontAccounting-master/output/backend/app/modules/dimensions/` — convention reference for service layer
5. **shorty backend exemplar:** `/Users/rahulchandra/01_Work/Projects/erplegacy/legacymodernisation/migrations/shorty/generated/backend/` — proven 7-phase build order, traceability headers, async patterns

## Output

Write to:
```
migrations/crud/output/planning/planning-001.md
```

Aim for 1200–1800 lines. Required heading structure:

```
# MWU-CRUD-001 — Planning Report
**Classification:** APPROVED-CANDIDATE (awaits Gate 3)
**Generated:** <ISO>
**Agent:** planner_agent (Opus · code-architect)
**Upstream:** comprehension-001.md

## 1. Architecture overview
### 1.1 Backend layers (models / schemas / service / router)
### 1.2 Frontend layers (pages / components / hooks / api client / types)
### 1.3 Layer firewall (service ≠ fastapi · router ≠ direct sqlalchemy · frontend ≠ direct DB)
### 1.4 Async + Pydantic v2 + SQLAlchemy 2.x conventions
### 1.5 Frontend toolchain (Vite + TS + shadcn/ui + Tailwind + React Query + react-hook-form + zod)

## 2. File tree (final — both sides)
Show every file CodeGen must produce. Backend ~12–15 files; frontend ~15–20 files; tests ~10 files; config ~10 files.

## 3. PostgreSQL schema + Alembic migration
DDL + alembic env.py + 0001_init_users.py spec

## 4. SQLAlchemy User model
Full Mapped[T] declarations + constraints

## 5. Pydantic schemas
UserBase / UserCreate / UserUpdate / UserRead + ProblemDetail + HealthResponse

## 6. UserService (business-logic layer)
For each method: async signature, pre/post conditions, error contract, BR-C mapping

## 7. FastAPI router
For each of 5 routes: full signature, status codes, ProblemDetail errors, BR-C mapping

## 8. Configuration + bootstrap
Settings (Pydantic) · main.py · CORS for frontend dev server · lifespan

## 9. React frontend
### 9.1 src/ file tree
### 9.2 Component specs (UsersPage / UsersDataTable / AddEditDialog / DeleteAlertDialog / Toaster)
For each: prop types, state-management decisions, event handlers
### 9.3 API client (api/users.ts) — typed fetch wrappers for the 5 endpoints
### 9.4 React Query setup (queryKey conventions, mutation invalidation)
### 9.5 Form schemas (zod) mirroring Pydantic
### 9.6 Type generation (Pydantic → TypeScript) — manual hand-written types this round; auto-gen via openapi-typescript deferred
### 9.7 Tailwind theme + shadcn component install list

## 10. Build order
Backend phases A1..C2 mirror shorty's pipeline.
Frontend phases F1..F4 layered atop.

## 11. Test plan (forward to Stage 6 TestGen)
### 11.1 Backend: pytest + httpx async client (one test class per endpoint)
### 11.2 Frontend: vitest unit tests for components; Playwright (optional/deferred)
### 11.3 BR-C coverage matrix (every BR-C → ≥1 backend test + relevant frontend test)

## 12. Dual-run harness contract (forward to Stage 7)
- Input matrix: same 5 endpoints, parametric over 4 happy + 4 edge cases
- Screenshot capture: legacy 4 screens (index/add/edit/delete-confirm) + new SPA states (list/add-modal/edit-modal/delete-dialog/empty/error)
- Visual diff disposition: legacy = baseline, new = transformation (NOT byte-equivalent)

## 13. Cockpit playback contract (forward to Stage 8)
Per-stage doneMeta, artefacts, screenshot pairs for the before/after panel

## 14. Self-check matrix
| BR-C | Backend location | Frontend location | Test | PASS/FAIL |
plus risk flags (8 from Discovery + any new), Gate-1 decisions (5), residual OQs

## 15. Open Questions (residual)

## 16. Handoff to CodeGen
2–3 sentences — start with Phase A1 (encode module is N/A for this engagement; start with config + db + model).
```

## Constraints

- **No code.** Function signatures, type annotations, component prop interfaces only.
- **Every BR-C mapped** to a `backend_file:method` AND a `frontend_file:component`.
- **Self-check matrix mandatory** — 12+ BR-C rows × backend × frontend × test, every cell PASS or N/A with justification.
- **Honour Gate-1 locks** (email UNIQUE, age 0–150, no pagination, no auth).
- **Frontend toolchain locked:** Vite 5 + TypeScript + React 18 + shadcn/ui + Tailwind + React Query (TanStack Query v5) + react-hook-form + zod. Do NOT introduce Redux, Next.js, or other state managers.

Append audit when done:
```json
{"ts":"<ISO>","event":"stage_complete","stage":"planning","artefact":"output/planning/planning-001.md","loc":<N>,"backend_files":<N>,"frontend_files":<N>,"br_mapped":<N>,"self_check":"<PASS|FAIL>","agent":"feature-dev:code-architect","model":"claude-opus-4-6"}
```

Return ≤ 400-word summary.
