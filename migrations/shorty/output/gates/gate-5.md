# Gate 5 — TestGen + Revision review

**Date:** 2026-05-14
**Reviewer:** Rahul Chandra (HITL)
**Stages reviewed:** Stage 6 TestGen, Revision-002 fix pass
**Status:** ✅ **APPROVED**

## Summary

Stage 6 TestGen produced 21 real test vectors from legacy PHP (via `php` 8.5.6 native +
Docker fallback), enhanced the test suite by +588 LOC, and completed all 3 deferred items
from Stage 5 (BR-C-10 failure-path test, `seeded_urls` fixture, double-commit cleanup).

It also surfaced 3 critical findings (encode `zfill→ljust`, router `Query(default=…)` import
defect, BR-C-02 IPv4 spec error) — all resolved in **Revision-002**.

Running pytest after Revision-002 then uncovered 6 additional test-infrastructure issues
that had never surfaced before because the integration suite had never actually executed
under CodeGen / Self-Review (it errored at collection). All 6 fixed.

## Final test results

```
107 passed, 4 skipped, 1 warning in 1.49s
```

- Unit suite: 69/69 PASS
- Integration suite: 38/38 PASS
- Parity scaffold: 4 skipped (need PHP_REFERENCE_URL/PYTHON_TARGET_URL env vars; provided by Stage 7 dual-run harness)

## Approval criteria met

- ✅ All 12 BR-Cs have working test coverage (12/12)
- ✅ Encode invariants I-1..I-10 PASS — verified against 21 real PHP-generated vectors plus property tests
- ✅ IP whitelist (BR-C-04) full 5-test matrix passes — including X-Forwarded-For middleware path
- ✅ Telemetry fire-and-forget (BR-C-10) both happy and failure paths verified
- ✅ Layer firewall intact (service ≠ fastapi imports; router ≠ direct sqlalchemy)
- ✅ All 3 deferred items from Stage 5 done
- ✅ 3 TODO markers preserved (2 from Planning §14.2 + the spec correction in comprehension)

## What changed across the 10 modified files

See `output/self-review/revision-002.md` for the full list and motivation. Headline:

- **Application code:** 3 small fixes (encode `zfill→ljust`, Query() signature, `require_ip_allowed` Depends chain). All app-side changes are correctness-preserving and tighten test-friendliness.
- **Test infrastructure:** Tempfile-backed SQLite replaces `:memory:`+StaticPool (the latter is broken for multi-session async writes). Dep-overrides handle the lifespan-not-triggered case.
- **Spec:** Comprehension §3 BR-C-02 annotated with the correction that the legacy regex is not end-anchored.

## Deferred / out of scope

The dual-run harness skip count (4) is intentional — these tests come alive in Stage 7. No
other deferred items remain.

---

**Next stage:** Dual-run parity harness (Stage 7). Brings up PHP shorty + MySQL on one side
and FastAPI + PostgreSQL on the other, all 127.0.0.1-bound inside a private docker network.
Parity runner script hits both with the same input matrix and diffs normalised responses.
