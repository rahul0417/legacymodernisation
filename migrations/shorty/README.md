# Engagement: shorty migration POC

**Engagement ID:** PNS-SHORTY-001
**Started:** 2026-05-14
**Source app:** [mikecao/shorty](https://github.com/mikecao/shorty) — single-class PHP URL shortener, 438 LOC
**Source stack:** PHP 5.x+ · MySQL · PDO · no framework
**Target stack:** Python 3.12 · FastAPI 0.110 · SQLAlchemy 2.x async · PostgreSQL 16 · pytest
**Scope:** Full pipeline (Discovery → Comprehension → Planning → CodeGen → Self-Review → TestGen → Validation) + dual-run vs live PHP + cockpit playback artefact
**Orchestrator:** Claude Code session (this conversation)
**HITL:** Rahul Chandra

## Why this engagement exists

The FrontAccounting POC (`poc-2-FrontAccounting-master/`) proved the pipeline works on
a real ERP module. shorty is a deliberately tiny, second-codebase pilot to prove
the pipeline isn't FA-specific — same agents, same gates, different domain. Output
becomes a second case study and a re-skinnable cockpit fixture.

## Pipeline stages and gates

| # | Stage | Agent | Output | Gate | HITL |
|---|---|---|---|---|---|
| 1 | Discovery | code-explorer | `output/discovery/discovery-001.md` | Gate 1 | Approve before Comprehension |
| 2 | Comprehension | code-explorer + general | `output/comprehension/comprehension-001.md` | Gate 2 | Approve before Planning |
| 3 | Planning | code-architect | `output/planning/planning-001.md` | Gate 3 | Approve before CodeGen |
| 4 | Code Generation | general-purpose | `generated/backend/` | (continues) | (verified at next gate) |
| 5 | Self-Review | code-reviewer | `output/self-review/self-review-001.md` | Gate 4 (review) | Approve flagged items before TestGen |
| 6 | TestGen | general-purpose | `generated/tests/` + `output/testgen/testgen-001.md` | Gate 5 | Approve test coverage before parity run |
| 7 | Dual-run parity | (scripted) | `dual-run/parity-report.json` | Gate 6 | Approve before cockpit playback |

## Workspace layout

```
migrations/shorty/
├── README.md                ← this file
├── source/                  ← shorty repo (chmod a-w — read-only)
├── prompts/                 ← per-stage prompts (generalised from FA POC)
├── output/                  ← agent artefacts
│   ├── discovery/
│   ├── comprehension/
│   ├── planning/
│   ├── codegen/
│   ├── self-review/
│   ├── testgen/
│   └── gates/               ← HITL gate decision records
├── generated/
│   ├── backend/             ← FastAPI app
│   └── tests/               ← pytest suite
├── dual-run/                ← parity harness (PHP + FastAPI side-by-side)
└── logs/
    └── audit.jsonl          ← append-only event log
```

## Audit log

Every stage transition and gate decision is appended to `logs/audit.jsonl`.
Never edit; never delete. One JSON object per line.

## Gate decisions

Recorded in `output/gates/gate-N.md` at each gate. Format:

```
Gate N — <stage> review · YYYY-MM-DD HH:MM
Status: APPROVED | REVISE | REJECT
Reviewer: <name>
Notes: <one or more bullets>
```

## What's NOT in scope for this engagement

- Multi-MWU sequencing (shorty is a single module — no PR ordering needed)
- Authentication migration (shorty has no auth; FA-AUTH design is reused if needed for future engagements)
- Multi-company schema isolation (single-tenant app)
- Production deployment (Phase 5)
