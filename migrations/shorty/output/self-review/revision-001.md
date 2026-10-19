# MWU-SHORTY-001 — Revision-001 (post-Self-Review fix pass)

**Date:** 2026-05-14
**Author:** orchestrator (claude-code) under HITL direction
**Triggered by:** Self-Review-001 § 9 (2 BLOCKING criticals)
**Status:** ✅ Both CRITICALs resolved.

## CRITICAL-1: `BadUrl`/500 mapping — RESOLVED

**Changes:**

1. **`app/modules/urls/errors.py`** — added new `StoredUrlCorrupt(ShortyError)` exception
   class with `detail="Internal error"`, `type_code="shorty/internal"`. Docstring cites
   RF-06 / OQ-C-02 and explains the distinction from `BadUrl` (data-integrity corruption
   vs client error).

2. **`app/modules/urls/service.py`** —
   - Import updated: `from .errors import BadUrl, StoredUrlCorrupt, UrlNotFound`
   - Module docstring's error contract block updated to list `StoredUrlCorrupt → 500`
   - Line 141 (stored-URL re-validation failure) now `raise StoredUrlCorrupt()` instead
     of `raise BadUrl()`. Inline comment clarifies the choice.

3. **`app/modules/urls/main.py`** —
   - Import updated to include `StoredUrlCorrupt`
   - New handler `_h_stored_corrupt` registered immediately after `_h_overflow`,
     returning HTTP 500 with `{"detail": ..., "type": ...}`

**Net effect:** Stored-URL re-validation failure now produces HTTP 500 (per Gate-2 OQ-C-02
decision), distinct from the HTTP 400 returned for user-submitted URL failures (BR-C-02).

## CRITICAL-2: BR-C-04 zero test coverage — RESOLVED

**Changes:**

1. **`tests/integration/test_create.py`** — added 5 test methods + supporting imports
   and `_build_client` static helper:
   - `test_BR_C_04_empty_whitelist_open` — empty whitelist permits any IP
   - `test_BR_C_04_ip_in_whitelist_allowed` — whitelisted IP allowed to create
   - `test_BR_C_04_ip_not_in_whitelist_403` — non-whitelisted IP returns 403 with correct ProblemDetail body
   - `test_BR_C_04_lookup_ignores_whitelist` — lookup branch exempt (returns 404 not 403)
   - `test_BR_C_04_xforwardedfor_resolves_real_ip` — exercises `ProxyHeadersMiddleware` with both whitelisted and non-whitelisted XFF values

   File grew from 117 → 264 LOC (+147 LOC).

**Mechanism:** `_build_client` static helper constructs a fresh `FastAPI` app per test
with custom `ip_whitelist_raw` Settings and optionally overrides `get_client_ip` via
`dependency_overrides`. For the XFF test, the override is skipped so the real middleware
chain runs and resolves `request.client.host` from the `X-Forwarded-For` header.

## Files touched (4)

| File | Change | Net LOC |
|---|---|---|
| `app/modules/urls/errors.py` | +1 class | +9 |
| `app/modules/urls/service.py` | imports + raise site + docstring | +3 |
| `app/main.py` | import + handler | +12 |
| `tests/integration/test_create.py` | imports + helper + 5 tests | +147 |

## Verification

```
=== CRITICAL-1 ===
class StoredUrlCorrupt(ShortyError)                          ✓
service.py raise StoredUrlCorrupt()                          ✓
main.py exception_handler(StoredUrlCorrupt) → status_code=500 ✓

=== CRITICAL-2 ===
test_BR_C_04_empty_whitelist_open                            ✓
test_BR_C_04_ip_in_whitelist_allowed                         ✓
test_BR_C_04_ip_not_in_whitelist_403                         ✓
test_BR_C_04_lookup_ignores_whitelist                        ✓
test_BR_C_04_xforwardedfor_resolves_real_ip                  ✓
```

## Status update

- Self-Review verdict was **CONDITIONAL_PASS** with 2 blocking criticals.
- Both criticals now resolved.
- Effective revised verdict: **PASS** (88 + 4 critical-related rows → all PASS;
  WARN rows unchanged at 7, all deferred to TestGen non-blocking scope).
- Gate 4 ready to be APPROVED.

## What remains (deferred to Stage 6 TestGen — non-blocking)

1. Double-commit cleanup (`get_db_session` unconditional commit)
2. `BR-C-10` failure path test (inject `SQLAlchemyError` into `_record_hit`)
3. `seeded_urls` fixture
4. `EncodeOverflow` and `_problem()` dead-code removal (Phase 5 cleanup)
5. `files_planned` correction (50 → 42) in cockpit playback metrics
