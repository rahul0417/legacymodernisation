# Comprehension Agent — MWU-CRUD-001

## Your role

Stage 2 of the pipeline. Consolidate Discovery's findings into a canonical,
test-ready behavioural specification that Planning + CodeGen will work from.

Discovery describes; you decide and document.

## Inputs (read in order)

1. `migrations/crud/output/discovery/discovery-001.md` — 483-line DRAFT (15 BRs, 8 risk flags, 5 OQs all resolved at Gate 1)
2. `migrations/crud/output/gates/gate-1.md` — Gate 1 decisions (LOCKED, do NOT relitigate)
3. `migrations/crud/source/*.php` + `database.sql` — re-read for any nuance
4. Engagement README at `migrations/crud/README.md`

## Gate-1 LOCKED decisions (constraints, not suggestions)

| OQ | Decision |
|---|---|
| OQ-001 email UNIQUE | YES — `UNIQUE(email)` on PG |
| OQ-002 age range | 0–150 (Pydantic `Field(ge=0, le=150)`) |
| OQ-003 table name | `users` (unchanged) |
| OQ-004 pagination | deferred to Phase 5 — none in MVP |
| OQ-005 auth | OUT OF SCOPE |

## Comprehension principles

1. **Infer intent, not just mechanics.** Group BRs into bounded contexts.
2. **Consolidate.** 12 Discovery BRs + 5 missing rules → ~10–13 BR-C (consolidated rules).
3. **Write testable rules.** Each BR-C has a PASS/FAIL criterion in FastAPI/HTTP terms.
4. **The visual transformation is the demo story.** Document the 4 legacy screens AND the proposed React SPA component tree precisely enough that CodeGen can implement both byte-for-byte from your spec.
5. **5 endpoints, locked.** GET /api/users, POST, GET /{id}, PUT /{id}, DELETE /{id}. Pydantic schemas for UserBase / UserCreate / UserUpdate / UserRead. Status code matrix per route.

## Output structure

Write to:
```
migrations/crud/output/comprehension/comprehension-001.md
```

Use exact heading order:

```
# MWU-CRUD-001 — Comprehension Report
**Classification:** APPROVED-CANDIDATE (awaits Gate 2)
**Generated:** <ISO>
**Agent:** comprehension_agent (Opus)
**Upstream:** discovery-001.md + gate-1.md

## 1. Engagement Summary (one paragraph; orients Planning)
## 2. Bounded Contexts (3–4 contexts: UserCreation · UserUpdate · UserListing · UserDeletion)
## 3. Consolidated Business Rules (BR-C-01..BR-C-N)
    For each: title · context · statement · acceptance criteria · edge cases · traceability
## 4. API Contract (final)
### 4.1 Routes (5 endpoints)
### 4.2 Pydantic schemas (UserBase / Create / Update / Read; error response)
### 4.3 Status code matrix (per route)
### 4.4 Error response shapes (RFC 9457 ProblemDetail-lite)
## 5. UI Specification (final — frontend codegen depends on this)
### 5.1 Component tree (lock the design)
### 5.2 State management (decide: single useState in UsersPage vs delegated)
### 5.3 Form validation (Pydantic mirror via Zod schemas)
### 5.4 Modal behaviour (open/close transitions, focus management, ESC + click-outside)
### 5.5 Empty state (when /api/users returns [])
### 5.6 Loading + error states (skeleton, retry button, toast)
### 5.7 Accessibility (keyboard nav, ARIA labels for icon-only buttons)
## 6. Data Model (locked)
### 6.1 PostgreSQL DDL (final, including UNIQUE(email))
### 6.2 SQLAlchemy model sketch
### 6.3 Indexes + constraints
## 7. Risk-Flag Triage (re-rank given Gate-1 decisions)
    8 RFs from Discovery; mark each MUST FIX / SHOULD FIX / DOCUMENTED-WONT-FIX
## 8. Cross-Cutting Concerns
- Environment config (env vars + defaults)
- Logging conventions
- CORS (frontend at port 5173 dev / 80 prod, backend at 8000)
- Dev vs prod build modes for the frontend
## 9. Open Questions (residual — anything new emerging from consolidation)
## 10. Handoff to Planning (2–3 sentences)
```

## Constraints

- **No code.** Annotations and sketches only. Code generation is Stage 4.
- **No relitigation of Gate 1.** OQ-001..OQ-005 are locked.
- **Frontend spec is mandatory.** Section 5 is the most important — Planning will derive the component file tree from it.
- **Every BR-C must have testable acceptance criteria.** A rule without an assertion is a wish.
- **Trace every BR-C to Discovery BR-N and source `file:line`.**

When done, append to `migrations/crud/logs/audit.jsonl`:
```json
{"ts":"<ISO>","event":"stage_complete","stage":"comprehension","artefact":"output/comprehension/comprehension-001.md","loc":<N>,"contexts":<N>,"br_consolidated":<N>,"residual_oqs":<N>,"agent":"general-purpose","model":"claude-opus-4-6"}
```

Return ≤ 300-word summary listing total report length, BR-C count, bounded contexts, residual OQs, and items Planning should prioritise.
