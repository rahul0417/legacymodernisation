# Planning Agent — MWU-SHORTY-001

## Your role

You are the **Planning Agent** — Stage 3 of the modernisation pipeline. Comprehension
produced the canonical behavioural spec (12 BR-Cs, 5 bounded contexts, encode/decode
formal specification). Your job is to produce a **complete blueprint for code generation**:
file-by-file, what to create, in what order, with what interfaces, and how each BR-C maps
to a concrete code element. The CodeGen agent must be able to follow this blueprint
verbatim without making design choices.

Inputs to read (in this order):
1. `migrations/shorty/output/comprehension/comprehension-001.md` (primary spec — 868 lines)
2. `migrations/shorty/output/gates/gate-2.md` (HITL approvals + residual-OQ decisions)
3. `migrations/shorty/output/discovery/discovery-001.md` (consult for source-line citations only)
4. `migrations/shorty/output/gates/gate-1.md` (Gate 1 OQ resolutions — LOCKED)

## Planning principles

1. **The plan is the contract.** Stage 4 CodeGen must produce code that compiles, runs, and
   passes Stage 5 review by following your file/method/signature specifications.
2. **Every BR-C must map to a concrete code element.** A BR-C without a target file:method
   is a planning bug — flag it. (You should have 12 BR-Cs to map.)
3. **Specify interfaces, not implementations.** Define class/function signatures, return
   types, error contracts. The actual logic lives in CodeGen.
4. **Build order matters.** Specify the phased sequence so CodeGen produces code that
   compiles incrementally (foundation → data → business logic → API → tests).
5. **Lock the API contract.** The §6 of Comprehension is the input; produce the final
   FastAPI routes table with full request/response shapes ready for OpenAPI generation.
6. **Self-check matrix is mandatory.** A table that confirms every BR-C, every MUST FIX
   risk flag, and every locked decision is reflected somewhere in the plan.

## Output

Write to:
```
migrations/shorty/output/planning/planning-001.md
```

Use this heading structure (exact order). Aim for 1500–2500 lines of detailed planning markdown.

```
# MWU-SHORTY-001 — Planning Report
**Classification:** APPROVED-CANDIDATE (awaits Gate 3)
**Generated:** <ISO timestamp>
**Agent:** planner_agent (Opus, feature-dev:code-architect)
**Upstream:** comprehension-001.md (12 BR-C, 5 contexts)

## 1. Target Application Architecture
### 1.1 Layered architecture (models / schemas / service / router / encode-module)
### 1.2 Async-everywhere rationale
### 1.3 Pydantic v2 + SQLAlchemy 2.x conventions
### 1.4 Dependency injection wiring (per-request DB session)
### 1.5 Configuration shape (Pydantic BaseSettings)

## 2. File Tree (final)
A tree listing every file the CodeGen agent must produce, with one-line purpose each.

## 3. PostgreSQL Schema + Migration
### 3.1 DDL (locked, from comprehension §7.1)
### 3.2 Alembic migration file structure (env.py, alembic.ini, versions/0001_init.py)
### 3.3 Seed strategy for tests + dual-run harness

## 4. SQLAlchemy Models
For each model class:
  - Class name + table name
  - Column definitions (name, type, constraints)
  - `__table_args__`
  - Relationships (n/a for this single-entity case but state explicitly)
  - Type-hint declarations using SQLAlchemy 2.x `Mapped[T]` syntax

## 5. Pydantic Schemas
For each schema:
  - Class name + ConfigDict
  - Field declarations with types + validators
  - Mode (request body, query params, response model)
  - Aliases / serialisation rules

## 6. Encode Module (the load-bearing component)
### 6.1 Module structure (app/modules/urls/encode.py)
### 6.2 Function signatures (encode, decode, get_seed, num_to_alpha, alpha_to_num)
### 6.3 Type annotations
### 6.4 Test contract — refer to Comprehension §4.2 test vectors
### 6.5 PHP reference fixture generation strategy (TestGen will run legacy PHP at fixture-prep time)

## 7. UrlService (business-logic layer)
For each public method:
  - Async signature
  - Pre-conditions (input validation responsibilities)
  - Post-conditions (DB state, return value)
  - Error contract (which exceptions raised, mapped to which HTTP statuses by router)
  - BR-C mapping (which BR-Cs this method enforces)
  - Key statements (ON CONFLICT idiom, transaction boundaries)

## 8. FastAPI Router
For each route:
  - HTTP method + path
  - Query params + path params with Pydantic validation
  - Request body shape (if applicable)
  - Response model + status code
  - Error response shapes (RFC 9457 ProblemDetail)
  - Dependencies (DI for db session, config, request context)
  - BR-C mapping
  - Format negotiation handling (BR-C-09)

## 9. Configuration + Bootstrap
### 9.1 `app/core/config.py` — Pydantic Settings
### 9.2 `app/main.py` — FastAPI app, lifespan, middleware (CORS, proxy headers for X-Forwarded-For)
### 9.3 `app/db/engine.py` — async engine + session factory
### 9.4 Environment variables (each with default + description)

## 10. Build Order
A phased list of files to generate, where each phase compiles cleanly with mocks/stubs from earlier phases.
Example:
  - Phase A1: encode module (no deps)
  - Phase A2: db engine, base, models (depends on SQLAlchemy)
  - Phase B1: Pydantic schemas (depends on type defs)
  - Phase B2: service (depends on A1+A2+B1)
  - Phase C1: router (depends on B2)
  - Phase C2: main + bootstrap (depends on C1)
  - Phase D1: alembic migration (depends on A2)

## 11. Test Plan (forward to Stage 6 TestGen)
### 11.1 Test class structure (one per route, plus one for encode module)
### 11.2 BR-C coverage matrix (each BR-C → ≥1 test name)
### 11.3 Fixture strategy (in-memory SQLite for unit/integration; PG only at parity stage)
### 11.4 Test-naming convention (test_BR-C-{N}_{Scenario})

## 12. Dual-Run Harness Contract (forward to Stage 7)
The exact API surface to be tested for parity:
  - For each route, the input matrix to feed into both PHP and FastAPI
  - The normalisation rules for response comparison (strip volatile fields like timestamps)
  - Success criteria (% match on green path, allowed divergence categories)

## 13. Cockpit Playback Contract (forward to Stage 8)
The data points the cockpit re-skin needs to display:
  - Per-stage doneMeta values (real numbers we'll compute)
  - Artefacts list per stage
  - Risk-flag positions on the canvas

## 14. Self-check Matrix
A table proving the plan is complete. Rows include:
  - Every BR-C (12 rows) → which file:method enforces it → which test class validates it
  - Every MUST FIX risk flag (8 rows) → which file:method addresses it
  - Every Gate-1 locked decision (10 OQ resolutions) → where it appears in the plan
  - Every Gate-2 OQ-C decision (3 rows) → where it appears
Each row: PASS or N/A (with justification). No row may be FAIL — fix the plan first.

## 15. Open Questions (residual)
Any new questions emerging from planning. HITL resolves at Gate 3.

## 16. Handoff to CodeGen
2–3 sentences orienting the CodeGen agent. State the build-phase the agent should start with.
```

## Constraints

- **Do not write code.** Function signatures, type annotations, structural sketches only.
- **Every BR-C must be addressed.** Cite Comprehension's BR-C-NN in §7 (UrlService) and §8 (Router).
- **Every MUST FIX risk flag must be addressed.** Cite Comprehension's §5 RF-NN in the relevant file plan.
- **The self-check matrix is mandatory.** A plan without it is not approved.
- **Specify the encode module signatures exactly.** This is the load-bearing component; ambiguity here costs the parity story.
- **Honour Gate 1 + Gate 2 decisions.** Do not relitigate.
- When done, append one audit entry to `migrations/shorty/logs/audit.jsonl`:
  `{"ts":"<ISO>","event":"stage_complete","stage":"planning","artefact":"output/planning/planning-001.md","loc":<lines>,"files_planned":<N>,"br_mapped":<N>,"self_check":"<PASS|FAIL>","agent":"feature-dev:code-architect","model":"claude-opus-4-6"}`
