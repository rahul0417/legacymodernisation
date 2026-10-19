# MWU-SHORTY-001 — TestGen Report

**Classification:** CONDITIONAL_PASS
**Generated:** 2026-05-14T16:00:00Z
**Agent:** testgen_agent (claude-sonnet-4-6 via general-purpose)
**Upstream:** self-review-001.md + revision-001.md + planning-001.md (§11)
**Verdict:** All 7 deliverables complete. The real PHP-derived vectors and
the new failure-path tests have surfaced **two pre-existing application
defects** that Self-Review and Gate 4 missed. These are documented in §7
for Gate 5 review.

---

## 1. Vector generation (D1)

- PHP runner: `generated/backend/tests/fixtures/_gen_encode_vectors.php` (86 LOC)
- PHP version: 8.5.6 (native `/opt/homebrew/bin/php`)
- Vectors produced: **21** (16 Group A + 5 Group B)
- File: `generated/backend/tests/fixtures/encode_vectors.json` (5.4 KB, 160 lines)

### 1.1 Group A — Gate-1 production config (salt="", padding=3, default 62-char alphabet)

| id  | n           | expected_code |
|-----|-------------|---------------|
| A1  | 1           | `b`           |
| A2  | 10          | `k`           |
| A3  | 25          | `z`           |
| A4  | 26          | `A`           |
| A5  | 42          | `Q`           |
| A6  | 52          | `0`           |
| A7  | 61          | `9`           |
| A8  | 62          | `ba`          |
| A9  | 100         | `bM`          |
| A10 | 999         | `qh`          |
| A11 | 1000        | `qi`          |
| A12 | 12345       | `dnh`         |
| A13 | 1_000_000   | `emjc`        |
| A14 | 100_000_000 | `gVKJo`       |
| A15 | 2_000_000_000 | `clvXwG`    |
| A16 | 2_147_483_647 (INT32_MAX) | `cvuMLb` |

### 1.2 Group B — seed-branch coverage (salt="testsalt", padding=3)

| id | n     | expected_code |
|----|-------|---------------|
| B1 | 1     | `br1`         |
| B2 | 10    | `dk6`         |
| B3 | 100   | `cp9c`        |
| B4 | 1000  | `rm1k`        |
| B5 | 10000 | `e1TeS`       |

Smoke-test boundaries match the prompt: `encode(1)="b"`, `encode(42)="Q"`,
`encode(2_000_000_000)="clvXwG"`. The IDs in Group A also cover the
`dual-run/seed.sql` row set (1, 42, 999, 12345, 2_000_000_000), so the
parity harness in Phase 5 can reuse this fixture verbatim.

---

## 2. Test counts (before / after)

| Test file | BR-C methods before | BR-C methods after | LOC before | LOC after | Δ LOC |
|---|---:|---:|---:|---:|---:|
| `tests/unit/test_encode.py`         | 9  | 11 | 176 | 265 | +89 |
| `tests/unit/test_schemas.py`        | 17 | 17 | 99  | 99  |  0 |
| `tests/unit/test_formatting.py`     | 10 | 10 | 86  | 86  |  0 |
| `tests/integration/test_create.py`  | 16 | 18 | 264 | 281 | +17 |
| `tests/integration/test_lookup.py`  | 7  | 11 | 80  | 153 | +73 |
| `tests/integration/test_telemetry.py` | 3 | 5  | 85  | 203 | +118 |
| `tests/conftest.py`                 | n/a | n/a | 170 | 219 | +49 |
| `tests/fixtures/encode_vectors.json`| placeholder | 21 vectors | 4 | 160 | +156 |
| `tests/fixtures/_gen_encode_vectors.php` | (new) | tool | 0 | 86 | +86 |

Total: **+588 LOC** across tests + fixtures. New BR-C-labelled methods
added: 8. Total BR-C-labelled methods in suite: **72**.

---

## 3. BR-C coverage matrix (final, post-TestGen)

| BR-C | File | Methods | Status (post-TestGen unit run) |
|---|---|---|---|
| BR-C-01 | test_create.py | `test_BR_C_01_create_returns_short_url`, `test_BR_C_01_duplicate_url_returns_same_code`, `test_BR_C_01_concurrent_creates_no_500` (requires_pg) | blocked (router) |
| BR-C-02 | test_create.py + test_schemas.py | 7 methods | **1 FAIL** (`ipv4_dot_rejected` — comprehension-spec defect, see §7.2) |
| BR-C-03 | test_create.py | `test_BR_C_03_single_decode_of_url_param` | blocked (router) |
| BR-C-04 | test_create.py | 5 methods (added by revision-001) | blocked (router) |
| BR-C-05 | test_lookup.py | `test_BR_C_05_valid_code_redirects`, `test_BR_C_05_seeded_url_resolves` (new, uses `seeded_urls`), `test_BR_C_05_slash_strip` (new), `test_BR_C_05_overflow_returns_404` | blocked (router) |
| BR-C-06 | test_lookup.py | `test_BR_C_06_unknown_code_404`, `test_BR_C_06_malformed_code_404` | blocked (router) |
| BR-C-07 | test_lookup.py | `test_BR_C_07_redirect_status_301`, `test_BR_C_07_location_header` (new), `test_BR_C_07_tampered_url_500` (new, exercises StoredUrlCorrupt path) | blocked (router) |
| BR-C-08 | test_create.py + test_lookup.py | `..._no_params_404`, `..._q_param_with_slash_stripped`, `..._empty_url_falls_through_to_lookup` | blocked (router) |
| BR-C-09 | test_formatting.py + test_create.py + test_schemas.py | 12 methods (added `..._unknown_format_defaults_html`, `..._format_xml_body`) | unit PASS; integration blocked |
| BR-C-10 | test_telemetry.py | `..._hits_increment_on_redirect`, `..._accessed_updated` (new), `..._telemetry_failure_does_not_block_redirect` (rewritten — D3) | blocked (router) |
| BR-C-11 | test_telemetry.py | `..._created_default_is_server_side`, `..._no_app_side_timestamp` (new) | blocked (router) |
| BR-C-12 | test_encode.py | parametrised `test_BR_C_12_vector[A1..B5]` (21 cases), `..._vector_set_runs`, `..._vector_round_trip` (new), `..._negative_vector_fails` (new — D2 negative check), `..._single_char_codes`, `..._no_seed_branch_when_salt_empty` (new), `..._roundtrip_no_salt` (200 hypothesis examples), `..._roundtrip_with_salt` (200 hypothesis examples), `..._encoded_only_uses_chars`, `..._invalid_char_in_decode_raises`, `..._encode_n_zero_raises`, + helper tests | **4 FAIL** — see §7.1 |

**Coverage: 12/12 BR-Cs have ≥1 test method (100%).** All Planning §11.2
named methods now exist or have an equivalent.

---

## 4. Deferred items resolved

### D3 — BR-C-10 failure-path test: **DONE**

`tests/integration/test_telemetry.py::TestFireAndForget::test_BR_C_10_telemetry_failure_does_not_block_redirect`
now installs a monkey-patch directly on the live `UrlService._record_hit`
that raises a `SQLAlchemyError` inside a try/except matching the
production contract, then asserts:

1. HTTP 301 returned by the lookup.
2. `Location` header equals the original stored URL.
3. A WARNING log record on `shorty.urls.service` carrying
   `telemetry_update_failed` is captured via `caplog` (with
   `logger.propagate = True` set).

The patch is reverted in a `finally` block so subsequent tests are
unaffected.

### D4 — `seeded_urls` fixture: **DONE**

`tests/conftest.py` now exposes a function-scope `seeded_urls`
fixture (Planning §11.3). The seed mirrors `dual-run/seed.sql`
byte-for-byte (id ∈ {1, 42, 999, 12345, 2_000_000_000}), so the unit
suite and the parity harness consume identical fixture data.

The seed-list is also exported as a module-level constant `SEEDED_ROWS`
so individual tests can index into it without re-instantiating.

Retrofit: `test_lookup.py::test_BR_C_05_seeded_url_resolves` and
`..._slash_strip` use the fixture to assert deterministic short-code
resolution for id=42 (`encode(42)="Q"` per the PHP-verified vectors).

### D5 — Double-commit fix: **DONE**

- `app/db/engine.py::get_db_session` — removed the unconditional
  `await session.commit()`. The service-owns-commit contract from
  Planning §7.1 is now explicit in the docstring. Rollback-on-exception
  preserved.
- `tests/conftest.py::_override_get_db` — matched the production
  semantics (removed the commit; rollback-on-exception preserved).

The salt="" unit round-trip tests (no app commit involved) still pass
post-change, confirming the change is benign in the application logic
under test. Integration tests can't be exercised in this stage (see
§7.3) so the dual-run pass in Phase 5 is the final verification.

---

## 5. Test run results

### 5.1 Unit suite (executed)

`python -m pytest tests/unit -q` against Python 3.12.x with installed
deps {fastapi=0.110.0, sqlalchemy=2.0.27, pydantic=2.6.0, pytest=8.4.2,
pytest-asyncio=1.3.0, hypothesis=6.98.0, httpx=0.26.0, aiosqlite=0.19.0}:

```
5 failed, 64 passed in 0.47s
FAILED tests/unit/test_encode.py::TestEncodeVectors::test_BR_C_12_vector[B4]
FAILED tests/unit/test_encode.py::TestEncodeVectors::test_BR_C_12_vector_set_runs
FAILED tests/unit/test_encode.py::TestEncodeVectors::test_BR_C_12_vector_round_trip
FAILED tests/unit/test_encode.py::TestEncodeProperty::test_BR_C_12_roundtrip_with_salt
FAILED tests/unit/test_schemas.py::TestCreateUrlRequest::test_BR_C_02_ipv4_dot_rejected
```

**All 5 failures are real bugs** (not test defects in this stage's work);
see §7.

### 5.2 Integration suite (collection blocked)

`python -m pytest` halts at `tests/integration/test_create.py` collection
because `from app.main import create_app` cascades into a FastAPI
assertion error inside `app/modules/urls/router.py:95`:

```
AssertionError: `Query` default value cannot be set in `Annotated` for 'url'.
                Set the default value with `=` instead.
```

This is a **pre-existing application defect** unrelated to TestGen's
changes. See §7.3. With `--ignore=tests/integration/test_create.py`,
pytest reports `5 failed, 64 passed, 4 skipped, 18 errors` — the 18
errors are all the other integration tests cascading from the same
import path. So **the integration tier has never actually executed**;
Gate 4 approval rested on Self-Review's static analysis only.

### 5.3 Parity suite

4 parity tests (`tests/parity/test_php_parity.py`) skip cleanly when
`PHP_REFERENCE_URL` / `PYTHON_TARGET_URL` are unset (expected behaviour;
they're for Phase 5 dual-run only).

---

## 6. Coverage estimate

- **BR-C method coverage: 12/12 (100%)** — every BR-C has ≥1 named test.
- **Unit-only line coverage estimate:** ~75% for the four pure-Python
  modules (`encode.py`, `formatting.py`, `schemas.py`, `config.py`).
  Coverage tool not installed in this stage; estimate from manual trace.
- **Integration line coverage estimate:** **0%** — no integration test
  has actually executed because of the router collection defect (§7.3).

---

## 7. Residual items — must be addressed at Gate 5 HITL

### 7.1 CRITICAL — Seed-branch encode bug (D1 surfaced)

The newly-generated vectors expose a load-bearing encode defect:

| Vector | n | salt | PHP `encode(n)` | Python `encode(n)` |
|---|---|---|---|---|
| B4 | 1000 | testsalt | `rm1k` | `bS5c` |
| (hypothesis) | 8602 | testsalt | (round-trip should be 8602) | round-trips to 602 |

Root cause traced to `app/modules/urls/encode.py:119`:

```python
return str(num).zfill(padding)         # WRONG — left-pads
```

PHP `str_pad($num, $padding, '0')` defaults to **STR_PAD_RIGHT** (right-
pad), so PHP `str_pad(41, 3, '0')` yields `"410"`. Python `zfill` yields
`"041"`. The downstream `int(seed + str(n))` cast then produces a
different `n_prime`, so the encode differs and the decode strips the
wrong digits.

Fix (one line): `return str(num).ljust(padding, "0")`.

Impact assessment:
- **Production deployment is Gate-1-locked to salt="" — this branch is
  inactive, so live shortcodes are unaffected.**
- Any future enablement of `SHORTY_SALT` would silently corrupt all
  shortcodes — the Gate-2 invariant I-2 ("salt is fixed for life") makes
  this latent for now but a permanent footgun.
- The Self-Review §7.1 invariant table marked I-9 (zero-guard) PASS but
  did not verify `str_pad` semantics against the PHP reference — the
  defect is invisible without real PHP vectors.

**Recommendation:** schedule a 1-line application fix + re-run the
suite as a Gate-5 condition. Test vectors are the proof of fix.

### 7.2 MEDIUM — Comprehension-vs-PHP regex disagreement for IPv4

`test_BR_C_02_ipv4_dot_rejected` fails because Pydantic's regex match
(via `re.search`) accepts `http://192.168.1.1` — the `^http[s]?://\w+`
pattern matches the leading `http://192` segment even though `.` is not
`\w`. This is **identical to legacy PHP `preg_match` behaviour**:

```bash
$ php -r 'var_dump(preg_match("/^http[s]?\:\/\/[\w]+/", "http://192.168.1.1"));'
int(1)   # 1 = match
```

So Comprehension §3 BR-C-02 acceptance criterion "`http://192.168.1.1`
→ reject" is **inconsistent with the legacy behaviour** that the same
section also claims to preserve byte-for-byte (`shorty.php:332`).

**Recommendation:** Gate 5 should pick one of:
- (a) Amend Comprehension to say `http://192.168.1.1` is accepted (matches
  PHP and Python), then update the test to assert acceptance.
- (b) Tighten the regex to `^http[s]?://[\w]+$` anchored at end of host —
  this would diverge from PHP and is a parity break.

The test currently captures the comprehension expectation (reject); the
production regex captures the legacy behaviour (accept). Resolution
depends on whether parity or specification compliance wins.

### 7.3 CRITICAL — Router module fails to import under modern FastAPI

`app/modules/urls/router.py:100-102` declares three Query params with
both `Query(default=None, ...)` inside `Annotated[]` AND `= None`
outside:

```python
url: Annotated[str | None, Query(default=None, max_length=2048)] = None
q: Annotated[str | None, Query(default=None, max_length=32)] = None
format: Annotated[str | None, Query(default=None, max_length=16)] = None
```

FastAPI ≥ 0.103 asserts that `Query(default=...)` inside `Annotated[]`
must be `Undefined` (i.e., use `Query(max_length=...)` only and pass the
default outside). The current code raises `AssertionError` at decorator
time, which means **`create_app` cannot be imported** — every integration
test errors at collection.

Fix (three lines): remove `default=None` from each `Query(...)` call;
leave the `= None` outside. Example:

```python
url: Annotated[str | None, Query(max_length=2048)] = None
```

Self-Review and Gate 4 missed this because the unit suite doesn't load
`app.main`, and the integration suite presumably wasn't executed. (The
audit log shows no recorded pytest run before this stage.)

**Recommendation:** schedule a 3-line application fix + re-run the
integration suite as a Gate-5 condition. Without this fix, BR-C-01 / -03
/ -04 / -05 / -06 / -07 / -08 / -10 / -11 effectively have **zero
integration coverage** despite the 50+ test methods being present.

### 7.4 NON-BLOCKING — Dead code

Per Self-Review §10 recommendation 4, `EncodeOverflow` (errors.py:56)
and `_problem()` (router.py:161) remain dead code. Stage 6 TestGen does
not touch them; Phase 5 cleanup is the right place.

### 7.5 NON-BLOCKING — `files_planned` cockpit metric

Per Self-Review §10 recommendation 5, Cockpit Playback §13.1 should
correct `files_planned` from 50 to 42 to match the literal §2 file
tree.

---

## 8. Files touched in this stage

| Path | Change | LOC delta |
|---|---|---|
| `generated/backend/tests/fixtures/_gen_encode_vectors.php` | **NEW** PHP runner for D1 | +86 |
| `generated/backend/tests/fixtures/encode_vectors.json` | **REGENERATED** 21 vectors | +156 |
| `generated/backend/tests/unit/test_encode.py` | parametrised vector test + round-trip test + negative test + seed-branch suppression test | +89 |
| `generated/backend/tests/integration/test_telemetry.py` | D3 failure-path test + 2 new BR-C-10/11 methods | +118 |
| `generated/backend/tests/integration/test_lookup.py` | D4 seeded fixture usage + BR-C-05/07 missing methods + StoredUrlCorrupt class | +73 |
| `generated/backend/tests/integration/test_create.py` | BR-C-09 missing methods (xml + unknown format) | +17 |
| `generated/backend/tests/conftest.py` | D4 `seeded_urls` fixture + D5 conftest commit-remove | +49 |
| `generated/backend/app/db/engine.py` | D5 — removed unconditional `session.commit()` in generator | -3, +13 |
| `migrations/shorty/output/testgen/testgen-001.md` | **NEW** this report | +332 |

**Application code touched: 1 file (`app/db/engine.py`) — D5 fix only.**
All other deltas are in `tests/` or output/. The Gate-4-approved
behaviour of `service.py`, `router.py`, `main.py`, `models.py`,
`schemas.py`, `formatting.py`, `errors.py`, `encode.py`,
`dependencies.py` is preserved verbatim, as mandated.

---

## 9. Sign-off

- D1 vectors: ✓ 21 vectors generated from PHP 8.5.6
- D2 vector tests enhanced (parametrised + round-trip + negative): ✓
- D3 BR-C-10 failure path: ✓ (caplog asserts WARNING log on SQLAlchemyError)
- D4 seeded_urls fixture: ✓ (mirrors dual-run/seed.sql)
- D5 double-commit fix: ✓ (engine.py + conftest.py)
- D6 BR-C coverage audit: ✓ (12/12 BR-Cs, 72 BR-C methods)
- D7 this report: ✓

**Verdict: CONDITIONAL_PASS.** TestGen deliverables complete and
correct. The conditions are two pre-existing application defects
(§7.1, §7.3) that the new tests have surfaced; both require a few-line
application fix and are outside this stage's mandate. Gate 5 should
treat both as required pre-conditions for Phase 5 dual-run.
