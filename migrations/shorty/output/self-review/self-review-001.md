# MWU-SHORTY-001 — Self-Review Report

**Classification:** CONDITIONAL_PASS
**Generated:** 2026-05-14T14:00:00Z
**Agent:** self_review_agent (claude-sonnet-4-6 via feature-dev:code-reviewer)
**Upstream:** planning-001.md (37-row self-check), 42 files at generated/backend/
**Verdict:** 2 blocking defects found; 88/99 checks pass; encode load-bearing component fully correct.

---

## 1. Verdict Summary

- Total checks: 99
- PASS: 88
- WARN: 7
- FAIL: 4
- Critical issues (blocking): 2
- Recommendations (non-blocking): 5

---

## 2. Category A — Business Rule Completeness

| BR-C | A1 Enforcement Point | A2 Correct Impl? | A3 Edge Cases | Row Verdict |
|---|---|---|---|---|
| BR-C-01 | `service.py:77-103` — ON CONFLICT DO NOTHING + fallback SELECT | PASS — idempotent, correct `was_created` flag | Trailing-slash URLs treated as distinct (no normalisation). Concurrent creates deferred to `requires_pg` marker | PASS |
| BR-C-02 | `schemas.py:55-58` Field pattern; `router.py:119` manual regex for R1 `GET /` | PASS — `^http[s]?://\w+` preserved character-for-character from `shorty.php:332` | `http://192.168.1.1` rejects (dot not `\w`); `HTTP://` rejects (case-sensitive) | PASS |
| BR-C-03 | `router.py:100` Starlette Query param (already single-decoded) — no `unquote` call | PASS — `%25` → `%`, not `5` | PASS |
| BR-C-04 | `dependencies.py:64-75` `require_ip_allowed`; R4 uses `Depends(require_ip_allowed)` at `router.py:83`; R1 calls inline at `router.py:115` | PASS — open mode when whitelist empty; lookup branch correctly exempt | PASS — implementation correct. **Tests: FAIL** (see D-BR-C-04) |
| BR-C-05 | `service.py:122-133` decode → INT32 bounds → SELECT | PASS — single-row read by id | Overflow `> INT32_MAX` → UrlNotFound at `service.py:126-128` | PASS |
| BR-C-06 | `errors.py:30-37` UrlNotFound; `main.py:108-113` → 404 | PASS — `{"detail": "Not Found", "type": "shorty/not-found"}` | Malformed code → path regex `router.py:149` → RequestValidationError → 404 | PASS |
| BR-C-07 | `router.py:156-157` `RedirectResponse(status_code=301)` | PASS — 301 redirect. **WARN**: re-validation raises `BadUrl` but handler maps it to 400, not 500 (CRITICAL-1) | WARN |
| BR-C-08 | `router.py:111-138` decision tree | PASS — matches `shorty.php:327` branch | `url=""` → falsy → lookup. `q=""` after strip → UrlNotFound | PASS |
| BR-C-09 | `formatting.py:30-80`; `schemas.py:38-46` OutputFormat.parse | PASS — byte-for-byte XML matches Planning §8.5 locked format. `html.escape()` applied | Unknown format → HTML. Case-insensitive via `.lower()` | PASS |
| BR-C-10 | `service.py:144` `asyncio.create_task(self._record_hit(row.id))` | PASS — fire-and-forget; exceptions caught and logged WARNING | Independent session via `self.session_factory` (S4: PASS) | PASS |
| BR-C-11 | `models.py:54-57` `server_default=func.now()`, TIMESTAMP(timezone=True) | PASS — DB-side default, no app-side timestamp. INSERT never passes `created` | PASS |
| BR-C-12 | `encode.py:64-100` `encode`/`decode` | PASS — all 10 invariants verified (see §7.1) | Placeholder vectors skip gracefully | PASS |

---

## 3. Category B — Behavioural Equivalence

| Route | B1 Inputs/Outputs | B2 Status Codes | B3 Format Negotiation | B4 Contract Items | Verdict |
|---|---|---|---|---|---|
| R1 `GET /` | PASS — `router.py:95-138` | **FAIL** — `BadUrl` from re-validation maps to 400, not 500 (CRITICAL-1; `main.py:94-99`) | PASS — 4 formats via `OutputFormat.parse` | PASS — decision tree; 404 on neither | WARN |
| R2 `GET /?q=` | PASS — slash-strip at `router.py:128` | **FAIL** — same `BadUrl`/400 issue | n/a (lookup) | PASS — 301 at `router.py:135` | WARN |
| R3 `GET /{code}` | PASS — path regex `router.py:148-150` | **FAIL** — `BadUrl` from `service.py:141` returns 400 not 500 | n/a (lookup) | PASS — `RedirectResponse(status_code=301)` at `router.py:157` | WARN |
| R4 `POST /shorten` | PASS — `CreateUrlRequest` body; `router.py:77-88` | PASS for normal cases | PASS — `OutputFormat.parse(body.format)` | PASS — `Depends(require_ip_allowed)` at `router.py:83` | PASS |
| R5 `GET /healthz` | PASS — `router.py:60-70` | PASS — always 200 | PASS — `HealthResponse` JSON | PASS — `SELECT 1` via `service.ping:152-165` | PASS |

---

## 4. Category C — Code Quality

| Check | Status | Evidence |
|---|---|---|
| C1: Type hints on every public function | PASS | All public functions type-annotated. `encode.py:64,87,103,122,143,163,168`; `service.py:66,105,148,152`; `router.py:61,77,95,145`. |
| C2: Async only where I/O | PASS | encode.py, formatting.py, errors.py, schemas.py — sync (no I/O). service.py, router.py, engine.py — async. No sync I/O anywhere. |
| C3: Layer firewall intact | PASS | `service.py` imports: no `fastapi`. `router.py` imports `AsyncSession` typing only from sqlalchemy. |
| C4: No global mutable state except documented singletons | PASS | `engine.py:33-34` and `dependencies.py:34-35` documented. No other module-level mutable state. |
| C5: No `print()` | PASS | Zero `print(` calls in app/. Logger used throughout. |
| C6: Decimal/int/str types appropriate | PASS | `Mapped[int]` for id/hits, `Mapped[str]` for url, `SecretStr` for salt. No float anywhere. |
| C7: Telemetry uses fresh session from `session_factory` | PASS | `service.py:178`: `async with self.session_factory() as bg_db:`. |
| C8: Error responses use ProblemDetail shape | PASS | All handlers in `main.py:94-145` return `{"detail": ..., "type": ...}`. |
| C9: No SQL string concatenation | PASS | All queries use SQLAlchemy Core API. `engine.py:101`: `_text("SELECT 1")` with no user input. |
| C10: Test fixtures match Planning §11.3 | **WARN** | `seeded_urls` (function-scope, Planning §11.3) is absent. `pg_db_engine` acceptable to defer to Stage 6. |

---

## 5. Category D — Test Adequacy

| BR-C | Tests Present | Exercises BR | Hypothesis | Verdict |
|---|---|---|---|---|
| BR-C-01 | `test_BR_C_01_create_returns_short_url`, `test_BR_C_01_duplicate_url_returns_same_code` | PASS | n/a | PASS |
| BR-C-02 | 6 methods across test_create.py + test_schemas.py | PASS | n/a | PASS |
| BR-C-03 | `test_BR_C_03_single_decode_of_url_param` | PASS | n/a | PASS |
| **BR-C-04** | **ZERO METHODS** — traceability header claims coverage; grep confirms none in entire suite | **FAIL** | n/a | **FAIL** |
| BR-C-05 | `test_BR_C_05_valid_code_redirects`, `test_BR_C_05_overflow_returns_404` | PASS | n/a | PASS |
| BR-C-06 | `test_BR_C_06_unknown_code_404`, `test_BR_C_06_malformed_code_404` | PASS | n/a | PASS |
| BR-C-07 | `test_BR_C_07_redirect_status_301` | PASS — 301 verified. Tampered-URL path not tested (blocked by CRITICAL-1) | n/a | PASS |
| BR-C-08 | `test_BR_C_08_no_params_404`, `test_BR_C_08_q_param_with_slash_stripped`, `test_BR_C_08_empty_url_falls_through_to_lookup` | PASS | n/a | PASS |
| BR-C-09 | 14 methods across test_formatting.py + test_create.py + test_schemas.py | PASS | n/a | PASS |
| BR-C-10 | `test_BR_C_10_hits_increment_on_redirect` PASS. `test_BR_C_10_telemetry_failure_does_not_block_redirect` tests happy path only | **WARN** | n/a | WARN |
| BR-C-11 | `test_BR_C_11_created_default_is_server_side` | PASS | n/a | PASS |
| BR-C-12 | Vector tests (skip-pending Stage 6), single-char sanity, round-trip hypothesis | PASS | `test_BR_C_12_roundtrip_no_salt`: `n∈[1,100_000]`. `test_BR_C_12_roundtrip_with_salt`: `n∈[1,10_000]`. PASS | PASS |

---

## 6. Category E — Traceability

| Check | Status | Evidence |
|---|---|---|
| E1: Every logic-carrying file has traceability header | PASS | All 15 logic-carrying files verified. |
| E2: Headers list correct BR-Cs | **WARN** | `router.py` RULES header omits BR-C-10. Router is the entry point for lookup; enforcement is in service.py. Non-blocking. |
| E3: Legacy file:line references correct | PASS | encode.py → shorty.php:122-203. service.py → shorty.php:226-264,311-394. router.py → shorty.php:311-394. All verified. |
| E4: 2 TODO markers present verbatim | PASS | `models.py:44` (Url.id) and `schemas.py:54` (CreateUrlRequest.url) both correct. |
| E5: No phantom BR references | PASS | All header-to-implementation mappings verified. |

---

## 7. Shorty-Specific Adversarial Checks

### 7.1 Encode Invariants I-1 through I-10

| Invariant | Verdict | Evidence |
|---|---|---|
| I-1: chars fixed for life of deployment | PASS | `config.py:78-85` model_validator enforces uniqueness; `EncoderConfig` frozen+slots. |
| I-2: salt fixed for life of deployment | PASS | `Settings.salt` is `SecretStr` with no setter; `EncoderConfig.salt` frozen. |
| I-3: padding fixed when salt non-empty | PASS | `config.py:63` `Field(default=3, ge=0, le=16)`; `EncoderConfig.padding` frozen. |
| I-4: MD5 arg order `str(n) + salt` NOT `salt + str(n)` | PASS | `encode.py:113`: `h = _md5_hex(str(n) + salt)`. Match confirmed against PHP `shorty.php:154`. |
| I-5: `int(k + str(n), 10)` explicit decimal | PASS | `encode.py:80`: `n_prime = int(k + str(n), 10)`. Explicit base=10. |
| I-6: `//` integer division in num_to_alpha | PASS | `encode.py:137`: `n = (n - m) // b`. Python `//` preserves invariant. |
| I-7: `b ** e` exact integer exponentiation | PASS | `encode.py:159`: `n += idx * (b ** (L - i - 1))`. Python `**` is exact integer. Improvement over PHP `pow()`. |
| I-8: DB PK sequence preserved | PASS | `models.py:45-49`: `Identity(always=True)`. |
| I-9: zero-guard `if num == 0: num = 1` | PASS | `encode.py:117-118`. Exact match against PHP. |
| I-10: URL strings stored verbatim | PASS | `service.py:77-80` stores `url` as-received. No normalisation. |

**All 10 invariants: PASS.**

### 7.2 OQ-CG Gap Verdicts

**S2.1 — OQ-CG-01: 42 vs 50 file count**

VERDICT: **The correct count is 42. The §2 summary claiming 50 is a Planning error.** Literal enumeration of Planning §2 file tree yields 42 files (root config 6 + app/ markers+main 3 + core/ 2 + db/ 3 + migrations/ 2 + versions/ 1 + modules/ 2 + urls/ 8 + tests/ 2 + fixtures/ 2 + unit/ 4 + integration/ 5 + parity/ 2 = 42). Matches CodeGen audit entry. The Cockpit Playback Contract §13.1 `files_planned=50` should be corrected to 42.

**S2.2 — OQ-CG-02: Engine split into init/get/dispose**

VERDICT: **Planning gap correctly filled. Not a deviation.** The split correctly separates lifecycle (init/dispose) from access (get) and is consistent with the `dependencies.py` `init_url_service`/`get_url_service` pattern. ACCEPTED.

**S2.3 — OQ-CG-03: Router R1 signature reordering and inline IP-gate**

VERDICT: **BR-C-04 semantics preserved. Acceptable.** The lookup-branch exemption is correctly preserved: `require_ip_allowed(request)` is called inline at `router.py:115` inside the `if url:` branch only. Loss of `client_ip` as a separately-injected dependency is a minor observability gap, not a functional defect. ACCEPTED.

### 7.3 Round-Trip Property Test (S3)

**PASS.** `test_encode.py:118-120`: `@given(n=st.integers(min_value=1, max_value=100_000))` asserts `decode(encode(n, cfg), cfg) == n` for salt="". `test_encode.py:124-127`: same for salt="testsalt", n∈[1,10_000].

### 7.4 Background-Task Session Isolation (S4)

**PASS.** `service.py:169-196` `_record_hit` uses `async with self.session_factory() as bg_db:` — independent of the request session. The two sessions are fully independent.

### 7.5 RF-06 Inline Implementation (S5)

**CONDITIONAL PASS (see CRITICAL-1).** `service.py:136-141` implements RF-06: `_LEGACY_RE.match(row.url)` re-validates the stored URL before emitting Location. ERROR log at `service.py:137-140` present as required. However, `raise BadUrl()` at `service.py:141` propagates to `main.py:94-99` which maps `BadUrl` → 400, not 500 as required by OQ-C-02. Logic correct; status code wrong.

---

## 8. Hallucination Findings

**HALLUC-1:** `EncodeOverflow` defined at `errors.py:56-62` but never raised. Python's arbitrary-precision integers remove the PHP float-overflow risk this class was modelled on. Non-blocking — dead code, removable in Phase 5.

**HALLUC-2:** `_problem()` helper at `router.py:161-164` defined but never called. Dead code. Non-blocking.

Expected hallucination count: 0. Actual: 2 (both non-blocking).

---

## 9. Critical Issues (BLOCKING — must fix before Gate 4)

### CRITICAL-1: `BadUrl` from stored-URL re-validation returns HTTP 400 instead of HTTP 500

- **Files:** `app/modules/urls/service.py:141` (raise site) + `app/main.py:94-99` (handler)
- **Contract violated:** Gate-2.md OQ-C-02: "500 + ERROR log." Planning §7.2 step 4.
- **Root cause:** `BadUrl` serves two roles: (a) user-submitted URL validation failure (correct → 400), (b) stored-URL re-validation failure (should → 500). One handler maps both to 400.
- **Fix:** Introduce `StoredUrlCorrupt(ShortyError)` exception with `detail="Internal error"`, `type_code="shorty/internal"`. In `service.lookup_and_redirect` line 141, raise `StoredUrlCorrupt` instead of `BadUrl`. Register `@app.exception_handler(StoredUrlCorrupt)` → 500 in `main.py`.

### CRITICAL-2: BR-C-04 (IP whitelist) has zero test coverage

- **File:** `tests/integration/test_create.py` (traceability header claims BR-C-04; zero methods)
- **Contract violated:** Planning §11.2 requires 5 named test methods for BR-C-04.
- **Severity:** IP whitelist is the only access-control mechanism in the system. Zero tests = could regress silently.
- **Fix:** Add `test_BR_C_04_empty_whitelist_open`, `test_BR_C_04_ip_in_whitelist_allowed`, `test_BR_C_04_ip_not_in_whitelist_403`, `test_BR_C_04_lookup_ignores_whitelist`, `test_BR_C_04_xforwardedfor_resolves_real_ip` to `test_create.py`. Use `create_app(Settings(ip_whitelist_raw="10.0.0.1", ...))` with `dependency_overrides` for `get_client_ip`.

---

## 10. Recommendations (NON-BLOCKING)

1. **Double-commit inconsistency:** Service commits explicitly (`service.py:93`), then `get_db_session` commits again (`engine.py:98`). No-op in practice but contradicts Planning §7.1. Fix in Phase 5: remove unconditional commit from `get_db_session`.
2. **BR-C-10 fire-and-forget failure test is placeholder** (`test_telemetry.py:67-85`): Stage 6 must inject a `SQLAlchemyError` into `_record_hit` and assert 301 still returns.
3. **`seeded_urls` fixture absent** (`conftest.py`): Planning §11.3 specifies it; Stage 6 should add it for test isolation.
4. **`EncodeOverflow` and `_problem()` are dead code:** Remove in Phase 5 cleanup.
5. **`files_planned` in Cockpit Playback Contract** (Planning §13.1): Correct 50 → 42.

---

## 11. Final Verdict

**CONDITIONAL_PASS**

**Conditions (must be met before Gate 4):**
1. Fix `BadUrl`/500 mapping for stored-URL re-validation failure (CRITICAL-1) — introduce `StoredUrlCorrupt` exception
2. Add all 5 BR-C-04 test methods (CRITICAL-2)

**Deferred to Stage 6 (non-blocking):**
- Double-commit cleanup
- BR-C-10 failure path test
- `seeded_urls` fixture

The encode/decode load-bearing component passes all 10 invariant checks against both the formal spec and the legacy PHP source. The architectural firewall (service ≠ fastapi, router ≠ sqlalchemy direct) is intact across all 15 logic-carrying files. 88 of 99 checks pass without qualification.
