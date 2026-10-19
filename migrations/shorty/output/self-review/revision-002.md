# MWU-SHORTY-001 — Revision-002 (post-TestGen fix pass)

**Date:** 2026-05-14
**Author:** orchestrator (claude-code) under HITL direction
**Triggered by:** TestGen-001 §"Gate 5 must check" (3 critical findings)
**Status:** ✅ All 3 TestGen findings resolved + 6 test-infrastructure issues uncovered by the actual pytest run also resolved.

## TestGen-flagged findings — RESOLVED

### F1: Seed-branch encode bug — `zfill` left-pads but PHP `str_pad` right-pads

- **File:** `app/modules/urls/encode.py:119`
- **Before:** `return str(num).zfill(padding)` (left-pad)
- **After:** `return str(num).ljust(padding, "0")` (right-pad, matches PHP default `STR_PAD_RIGHT`)
- **Verified:** Vector B4 `(n=1000, salt="testsalt")` now produces `rm1k` (matches PHP), previously produced `bS5c`.
- **Risk note:** Latent only under production lock-in (salt=""). Now corrected for any future salt-enabled deployment.

### F2: Router import defect — `Query(default=None)` under `Annotated`

- **File:** `app/modules/urls/router.py:100-102`
- **Before:** `Annotated[str | None, Query(default=None, max_length=2048)] = None`
- **After:** `Annotated[str | None, Query(max_length=2048)] = None` (×3 query params)
- **Impact:** Integration test tier now actually runs. Before this fix, `create_app()` failed at import time under FastAPI ≥0.103.

### F3: BR-C-02 IPv4 spec disagreement (documentation, not code)

- **Files:** `tests/unit/test_schemas.py` (test renamed + assertion flipped), `output/comprehension/comprehension-001.md` (BR-C-02 corrected note added)
- **Resolution:** The legacy regex `^http[s]?://\w+` is NOT end-anchored. `http://192.168.1.1` is accepted by both PHP and the Python port. Test now asserts acceptance. Comprehension annotated with the correction so downstream stages don't relitigate.

## Test-infrastructure issues uncovered while running the suite — RESOLVED

The integration suite never ran during CodeGen or Self-Review (it errored at collection due to F2). Once F2 was fixed, six additional issues surfaced:

### F4: ASGITransport doesn't trigger lifespan → dependency singletons uninitialised

- **File:** `tests/conftest.py` (`app_instance` fixture)
- **Fix:** Override `get_settings` and `get_url_service` in `dependency_overrides`, build a test-scoped `UrlService` bound to the test's `session_factory`. Singletons are no longer touched by tests.

### F5: `require_ip_allowed` called `get_settings()` and `get_client_ip(request)` directly → `dependency_overrides` bypassed

- **Files:** `app/modules/urls/dependencies.py`, `app/modules/urls/router.py`
- **Fix:** Refactor `require_ip_allowed` to take both `settings` and `client_ip` via `Annotated[..., Depends(...)]`. `root_handler` now also accepts `client_ip: Annotated[str, Depends(get_client_ip)]` and passes both explicitly when calling `require_ip_allowed` inline.
- **Net effect:** TestIpWhitelist tests with spoofed IPs and custom whitelists now work, AND the production code path through `Depends(require_ip_allowed)` on R4 still works.

### F6: `pytest==8.0.0` / `pytest-asyncio==0.23.4` constraint conflict

- **File:** `pyproject.toml`
- **Fix:** Relax to `pytest>=8.0,<9` and `pytest-asyncio>=0.24,<1`. Resolver now succeeds.

### F7: SQLite `:memory:` + `StaticPool` + multi-session async writes — background-task UPDATEs silently invisible to subsequent read sessions

- **File:** `tests/conftest.py` (`db_engine` fixture)
- **Diagnosis:** With `:memory:` + StaticPool, fire-and-forget telemetry tasks complete without raising but their committed UPDATEs are not visible to the test's read session. Verified by direct invocation (works) vs ASGITransport invocation (fails). Behaviour is consistent under tempfile-backed SQLite.
- **Fix:** Switch `db_engine` to a per-test tempfile-backed SQLite (`tempfile.mkstemp(...)` + `os.unlink` on teardown). Negligible perf cost (~110 tests in ~1.5s).

### F8: `test_BR_C_07_location_header` URL with embedded `&` parsed as query boundary

- **File:** `tests/integration/test_lookup.py`
- **Fix:** Use httpx `params=` kwarg so the `&` inside the stored URL is properly percent-encoded.

### F9: `TestFireAndForget` test called `get_url_service()` directly (module singleton, not overridden)

- **File:** `tests/integration/test_telemetry.py`
- **Fix:** Retrieve the test-scoped service via `app_instance.dependency_overrides[get_url_service]()` instead. Also widen log-record matcher to accept the test's `shorty.urls.service.test` child-logger name.

## Files touched (10)

| File | Change | Net LOC |
|---|---|---|
| `app/modules/urls/encode.py` | F1: zfill → ljust + docstring update | +5 / −2 |
| `app/modules/urls/router.py` | F2: Query() default + F5: client_ip dep + require_ip_allowed call | +6 / −4 |
| `app/modules/urls/dependencies.py` | F5: settings + client_ip via Annotated/Depends | +12 / −9 |
| `pyproject.toml` | F6: pytest version constraint | +2 / −2 |
| `tests/conftest.py` | F4: dep overrides + F7: tempfile SQLite | +35 / −14 |
| `tests/integration/test_create.py` | F4/F5: TestIpWhitelist _build_client overrides | +13 / −2 |
| `tests/integration/test_lookup.py` | F8: URL-encoding fix | +3 / −2 |
| `tests/integration/test_telemetry.py` | F9: service lookup + log matcher | +7 / −2 |
| `tests/unit/test_schemas.py` | F3: IPv4 test rename + assertion flip | +6 / −3 |
| `output/comprehension/comprehension-001.md` | F3: BR-C-02 corrected note | +2 / 0 |

## Test results after revision-002

```
$ pytest tests/ -q
.................................................... [100%]
107 passed, 4 skipped, 1 warning in 1.49s
```

The 4 skips are `tests/parity/test_php_parity.py` — they require `PHP_REFERENCE_URL` and `PYTHON_TARGET_URL` env vars set, which only happens when the Stage-7 dual-run harness is up.

## Effective verdict

- BR-C coverage: **12/12 PASS** with **107 tests green**
- Encode invariants I-1..I-10: PASS (verified by 21 real PHP-generated vectors + property tests)
- IP whitelist (BR-C-04): full 5-test matrix passes
- Telemetry fire-and-forget (BR-C-10): both happy + failure paths verified
- ProxyHeadersMiddleware (RF-05): live XFF resolution test passes

Gate 5 ready to be APPROVED.
