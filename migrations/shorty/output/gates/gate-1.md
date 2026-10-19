# Gate 1 — Discovery review

**Date:** 2026-05-14
**Reviewer:** Rahul Chandra (HITL)
**Stage reviewed:** Discovery (`output/discovery/discovery-001.md`)
**Status:** ✅ **APPROVED**

## Summary

Discovery agent (Sonnet 4-6 via `feature-dev:code-explorer`) produced a thorough 681-line
DRAFT report. Coverage:

- **File inventory:** 5 files catalogued (3 PHP + 1 SQL + 1 README), 438 PHP LOC total
- **Data model:** MySQL DDL → PostgreSQL DDL with full type-mapping rationale
- **Business rules:** 15 BRs identified — every BR cites `file:line`, includes migration mapping + edge cases
- **UI/API contract:** 4 routes documented (R1–R4), 4 output formats (text/json/xml/default)
- **Dependencies:** 30+ PHP built-ins mapped to Python/FastAPI equivalents
- **Risk flags:** 12 RFs — including the 2 critical encoding-stability flags (RF-02, RF-03) that gate everything downstream
- **Open questions:** 10 OQs cited, 4 marked HIGH impact

## Approval criteria met

- ✅ Report is exhaustive on business rules (15 BRs; load-bearing `encode/decode/get_seed`
      triplet fully documented in BR-05)
- ✅ Every risk flag has a recommended fix
- ✅ Every open question cites source line
- ✅ Classification correctly marked DRAFT (awaits Comprehension consolidation)

## Decisions on flagged open questions

The Discovery agent flagged 3 blockers for downstream stages. Resolved here so Comprehension
can proceed without ambiguity:

| OQ | Question | Decision |
|---|---|---|
| OQ-01 | Production salt value | **Empty salt** (`""`). This is a greenfield POC — no production data to preserve. Documented in CodeGen config as `SHORTY_SALT=""`. |
| OQ-02 | Production padding + chars | **padding=3, default chars** (config.php line 9 — `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789`). Matches config.php defaults. |
| OQ-07 | GET-with-side-effects vs RESTful POST | **Preserve `GET /?url=...`** as primary interface to enable byte-for-byte parity with live PHP in the dual-run harness. Add `POST /shorten` as alias for forward-compatibility (returns same payload, identical semantics). |
| OQ-09 | Existing data migration? | **Greenfield.** Empty seed DB for dual-run. No data migration script required for this POC. |
| OQ-03 | BIGINT for id/hits? | **INTEGER (signed 32-bit).** Demo scale; document the threshold (~2.1B). Phase 5 production deployment would upgrade. |
| OQ-04 | TEXT vs VARCHAR(2048) for url | **TEXT.** PostgreSQL idiomatic; no truncation risk. |
| OQ-05 | Stricter URL validation? | **Preserve legacy regex** for parity-test correctness. Stricter pydantic validators can layer on as an optional middleware in Phase 5. |
| OQ-06 | Hit-counter failure handling | **Fire-and-forget.** Log the error, redirect anyway. Matches legacy behavior. |
| OQ-08 | Whitelist config source | **Env var** (`SHORTY_IP_WHITELIST=10.0.0.1,10.0.0.2`). Comma-separated. Empty = open mode (matches legacy default). |
| OQ-10 | 301 vs 302 redirect | **Preserve 301** to match legacy behavior. Required for parity. |

## What Comprehension should focus on

(Forwarded from Discovery's §9 recommendation, with my prioritisation:)

1. **Formal encode/decode round-trip invariant** — produce a property-based test specification
   so Stage 6 has a clear test contract.
2. **Risk-flag triage matrix** — re-rank the 12 RFs against the decisions above. RF-02 and
   RF-03 (encoding stability) are now the most critical given OQ-02 is locked.
3. **Behavioural rule consolidation** — cluster the 15 BRs into 3–5 bounded contexts
   (creation, lookup, format-negotiation, security, observability).

---

**Next stage:** Comprehension (Stage 2). Subagent: `general-purpose` (Opus). Output to
`output/comprehension/comprehension-001.md`.
