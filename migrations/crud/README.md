# Engagement: chapagain/crud-php-simple migration POC

**Engagement ID:** PNS-CRUD-001
**Started:** 2026-05-14
**Source app:** [chapagain/crud-php-simple](https://github.com/chapagain/crud-php-simple) — 222 PHP LOC, classic CRUD over `users` table with bare HTML UI
**Source stack:** PHP 8 · MySQL 8 · mysqli (procedural) · no framework · table-based HTML
**Target stack:** Python 3.12 · FastAPI 0.110 · SQLAlchemy 2.x async · PostgreSQL 16 · pytest **+ React 18 (TS) · shadcn/ui · Tailwind · Vite · Vitest**
**Scope:** Full pipeline + dual-run + **visual UI transformation** (this is the first engagement with a frontend)
**Orchestrator:** Claude Code (this session)
**HITL:** Rahul Chandra

## Why this engagement exists

shorty (PNS-SHORTY-001) proved the pipeline works on a backend-only app. This engagement
proves it works on an app **with an actual UI** — the visible "old vs new" transformation
that customer prospects most readily understand. The legacy app is the canonical
"1999-era `<table border=0 bgcolor='#DDDDDD'>` PHP CRUD" that every enterprise has
50 of in their estate.

## Pipeline stages and gates

Identical 7-stage pipeline + cockpit playback as the prior 2 engagements:

| # | Stage | Agent | Output | Gate |
|---|---|---|---|---|
| 1 | Discovery | code-explorer (Sonnet) | `output/discovery/discovery-001.md` | Gate 1 |
| 2 | Comprehension | general-purpose (Opus) | `output/comprehension/comprehension-001.md` | Gate 2 |
| 3 | Planning | code-architect (Opus) | `output/planning/planning-001.md` | Gate 3 |
| 4 | Code Generation | general-purpose (Opus) | `generated/backend/` + `generated/frontend/` | (rolls) |
| 5 | Self-Review | code-reviewer (Sonnet) | `output/self-review/self-review-001.md` | Gate 4 |
| 6 | TestGen | general-purpose (Sonnet) | `generated/tests/` + frontend tests | Gate 5 |
| 7 | Dual-run | docker-compose + parity-runner | `dual-run/reports/parity-report.json` | Gate 6 |
| 8 | Cockpit re-skin | manual edits | `demo/crud/index.html` | — |

## What's different from shorty

- **Frontend codegen is new.** Stage 4 produces BOTH backend (FastAPI) AND frontend (React/Vite/shadcn). Planning must lock the component tree, route table, and API contract.
- **Visual parity matters.** Stage 7 dual-run captures screenshots of both sides so the cockpit can show "old vs new" side-by-side.
- **Multiple UI screens.** legacy has 4 (list / add / edit / delete-confirm); the modernised version uses a single SPA with modals.

## Workspace layout

```
migrations/crud/
├── README.md
├── source/                      ← chapagain/crud-php-simple (chmod a-w)
├── prompts/                     ← per-stage prompts (adapted from shorty)
├── output/                      ← agent artefacts
├── generated/
│   ├── backend/                 ← FastAPI app
│   └── frontend/                ← React + Vite + shadcn SPA
├── dual-run/                    ← Docker stack + parity-runner + screenshot capture
├── screenshots/                 ← old.png · new.png · side-by-side composite
└── logs/audit.jsonl
```

## Visual transformation goals (forward to Stage 4 + Stage 8)

- Replace `<table width='80%' border=0 bgcolor='#DDDDDD'>` with shadcn DataTable
- Replace inline `confirm()` delete with shadcn Dialog
- Replace separate add.php/edit.php pages with modal-driven SPA
- Keep the 1 entity (`users`) and the 4 fields (name, age, email + id) intact

## Progress snapshot (2026-05-14)

| Stage | Status | Headline |
|---|---|---|
| 1 Discovery | ✅ Gate 1 APPROVED | 7 source files · 222 PHP LOC · 12 BRs · 8 risk flags (2 CRITICAL SQLi) · 5 OQs resolved |
| 2 Comprehension | ✅ Gate 2 APPROVED | 11 BR-Cs · 4 bounded contexts · API contract + React component tree locked |
| 3 Planning | ✅ Gate 3 APPROVED | 91 files planned (38 backend + 53 frontend) · 37/37 self-check PASS · 7 locks |
| 4 CodeGen | ✅ Complete | 93 files materialized (40 backend + 53 frontend) · 2,131 Py LOC · 2,850 TS LOC |
| 5 Self-Review | ✅ Gate 4 APPROVED | 84 checks · 78 PASS / 4 WARN / 2 FAIL / 2 CRITICAL — both criticals fixed in-place |
| 6 TestGen | ⏳ In flight | backend pytest + frontend vitest + 3 carried items (R-1, R-2, R-3) |
| 7 Dual-run | ⏸ Pending Gate 5 | docker compose · API smoke (14 fixtures) · 16 visual-parity screenshots |
| 8 Cockpit | ⏳ In place | `demo/crud/index.html` re-skinned end-to-end; awaits final TestGen + dual-run numbers |
