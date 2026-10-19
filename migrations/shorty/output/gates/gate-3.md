# Gate 3 — Planning review

**Date:** 2026-05-14
**Reviewer:** Rahul Chandra (HITL)
**Stage reviewed:** Planning (`output/planning/planning-001.md`)
**Status:** ✅ **APPROVED**

## Summary

Planning agent (Opus 4-6 via `feature-dev:code-architect`) produced a 1,074-line
implementation blueprint with 16 sections. Coverage:

- **§1 Architecture:** layered (models / schemas / service / router / encode-module) with
  hard import firewall (service ≠ fastapi, router ≠ sqlalchemy direct)
- **§2 File tree:** 50 files, 15 logic-carrying, paths under `generated/backend/`
- **§3 PostgreSQL schema + Alembic single migration**
- **§4–§9:** SQLAlchemy model + Pydantic schemas + encode module + UrlService + router + config — all signatures specified, zero implementation freedom
- **§10 Build order:** 7 phases (A1 encode → A2 db+model+config → B1 schemas+errors+formatting → B2 service+deps → C1 router+main → C2 alembic+docker+health → D1 parity scaffold)
- **§11–§13:** test plan, dual-run harness contract, cockpit playback contract
- **§14 Self-check matrix: 37/37 PASS** (12 BR-Cs + 9 MUST FIX + 1 SHOULD FIX + 2 WONT-FIX-with-TODOs + 10 Gate-1 + 3 Gate-2 OQ-C)

## Approval criteria met

- ✅ Every BR-C mapped to a concrete `file:method` (12/12)
- ✅ Every MUST FIX risk flag has a target location (9/9 including 1 net-new decode-overflow)
- ✅ All 10 Gate-1 + 3 Gate-2 locked decisions surface explicitly
- ✅ Encode module signatures are byte-exact and reference Comprehension §4.1
- ✅ Build order is implementable phase-by-phase
- ✅ TODO marker convention specified (`# TODO(stage5-review): ...`) for SHOULD-FIX / WONT-FIX items

## Decisions on residual OQ-Ps

| OQ-P | Suggestion | Decision |
|---|---|---|
| OQ-P-01 | Telemetry session via `async_sessionmaker` constructor injection (matches FA POC) | **Accepted.** |
| OQ-P-02 | `/healthz` runs `SELECT 1` (k8s probe accuracy) | **Accepted.** |
| OQ-P-03 | If chars string is changed at deployment, document as invariant violation | **Accepted.** Phase 1 uses default; document in README. |

## What CodeGen should focus on

1. **Phase A1 first:** `app/modules/urls/encode.py` — invariants I-1..I-10 are non-negotiable. The function signatures in Planning §6.2 are byte-exact; do not deviate. Pure stdlib imports only.
2. **Phase A2 next:** Settings + engine + model — establishes the DB and config foundation. SQLite-only integration tests for everything except the BR-C-01 `ON CONFLICT` test (which needs testcontainers-postgresql).
3. **Service `_record_hit` runs in a background task** with an **independent** session from the request session (OQ-P-01).
4. **Three TODO markers must appear verbatim** (`# TODO(stage5-review): ...`) per Planning §14.2 — RF-01 on `Url.id`, RF-04 on `CreateUrlRequest.url`.
5. **Traceability headers** at the top of every logic-carrying file (FA POC convention).

---

**Next stage:** Code Generation (Stage 4). Subagent: `general-purpose` (Opus). Output to
`migrations/shorty/generated/backend/**`.
