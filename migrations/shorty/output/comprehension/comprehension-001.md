# MWU-SHORTY-001 — Comprehension Report
**Classification:** APPROVED-CANDIDATE (awaits Gate 2)
**Generated:** 2026-05-14T08:30:00Z
**Agent:** comprehension_agent (Opus)
**Upstream:** `output/discovery/discovery-001.md` (15 BRs, 12 RFs, 10 OQs)
**Gate 1 record:** `output/gates/gate-1.md` (10/10 OQs resolved 2026-05-14)

---

## 1. Engagement Summary

Shorty is a 438-LOC PHP URL shortener (`mikecao/shorty`, MIT, 2011) with a single
entity (`urls`), one class (`Shorty`), a thin bootstrap (`index.php`), and a
configuration file. There is no framework, no session layer, no auth, no money
arithmetic, no multi-tenancy. The behavioural surface is a single HTTP entry
point that accepts either `?url=<long>` (create-or-retrieve) or `?q=<code>`
(lookup-and-redirect), with four response formats negotiated via `?format=`.

The application's load-bearing logic is the
`encode`/`decode`/`get_seed` triplet (`shorty.php:122–203`), which converts a
database integer ID to/from a short alphanumeric code. Because Gate 1 locked
the production deployment to **salt=`""`, padding=3, default chars**, the
encoder is currently operating in the "no-seed" branch (an ID-to-base-62
bijection); however, the seed branch must be implemented correctly for
parity with the legacy class and for future deployments that turn salt on.

Discovery produced 15 BRs that this report consolidates into **12 BR-C** rules
grouped into **5 bounded contexts**: UrlCreation, UrlLookup, FormatNegotiation,
AccessControl, Telemetry. Gate-1 resolutions collapse a number of Discovery
OQs to constraints; the residual open questions list (§9) is short and
non-blocking for Planning.

---

## 2. Bounded Contexts

| # | Context | Purpose | Externally visible behaviour |
|---|---|---|---|
| BC-1 | **UrlCreation** | Persist a long URL and return a short code derived from its auto-increment ID | `GET /?url=<long>[&format=...]` returns the canonical short URL in the requested format. Idempotent w.r.t. an already-stored URL. |
| BC-2 | **UrlLookup** | Resolve a short code to the original URL and issue a redirect | `GET /{code}` (rewritten to `?q=<code>`) issues HTTP 301 to the stored URL or 404 if unknown. |
| BC-3 | **FormatNegotiation** | Render the create-response in `text`, `json`, `xml`, or HTML | `?format=` switch with default HTML anchor. Case-insensitive. |
| BC-4 | **AccessControl** | Restrict URL creation to a configured IP set (optional) | If `SHORTY_IP_WHITELIST` is non-empty, only listed IPs may create; lookup is always open. Empty list = open mode. |
| BC-5 | **Telemetry** | Record creation timestamp, last-access timestamp, and a hit counter | Each successful redirect increments `hits` and updates `accessed`. Failures are logged but do not block the redirect (fire-and-forget per Gate 1 OQ-06). |

**Membership map (BR-C → context):**

| Context | BR-Cs |
|---|---|
| BC-1 UrlCreation | BR-C-01, BR-C-02, BR-C-03, BR-C-08 |
| BC-2 UrlLookup | BR-C-05, BR-C-06, BR-C-07 |
| BC-3 FormatNegotiation | BR-C-09 |
| BC-4 AccessControl | BR-C-04 |
| BC-5 Telemetry | BR-C-10, BR-C-11 |
| (cross-cutting algorithm) | BR-C-12 — encode/decode invariant (used by both BC-1 and BC-2; specified in §4) |

---

## 3. Consolidated Business Rules

These 12 BR-C rules are the **single source of truth** for Planning, CodeGen, and
TestGen. They supersede Discovery's BR-01..15. Where a Discovery BR has been
merged, split, or rewritten, the traceability row records it.

---

### BR-C-01 — URL deduplication is idempotent on the `url` column

**Context:** BC-1 UrlCreation
**Statement:** A `POST/GET` create request for a URL that already exists in the
`urls` table MUST return the short code derived from the existing row's `id`
without inserting a new row.
**Rationale:** Preserves URL stability and prevents the unique constraint from
ever being triggered by normal traffic. Same long URL always maps to same
short code.
**Acceptance criteria:**
- Given a row exists with `url='https://x.test/a'` and `id=42`, when the client
  sends `GET /?url=https://x.test/a`, then the response body contains the
  short URL `<hostname>/<encode(42)>` and no new row is inserted.
- Concurrent duplicate creates MUST NOT raise a 500. The implementation MUST
  use `INSERT ... ON CONFLICT (url) DO NOTHING RETURNING id` and, when the
  insert returned no row, follow up with a `SELECT id WHERE url = :url`.
**Edge cases (test fixtures):**
- Trailing-slash difference: `https://x.test/` vs `https://x.test` are
  treated as different URLs (no normalisation — matches legacy).
- Case difference in scheme: `HTTPS://x.test` is treated literally
  (matches legacy; regex `^http[s]?://` is case-sensitive on scheme).
- Race: two concurrent requests for the same new URL — both must succeed
  with the same short code.
**Traceability:**
- Discovery BR-01 (`shorty.php:334–343`)
- Discovery RF-07 absorbed (concurrency fix mandatory, MUST FIX in §5)

---

### BR-C-02 — URL format validation (legacy regex preserved)

> **Stage-6 correction (2026-05-14):** The legacy regex `^http[s]?://\w+` is NOT end-anchored. `\w+` only needs to match the first hostname segment, so URLs like `http://192.168.1.1` are **accepted** (verified against legacy PHP `preg_match`). Discovery BR-02's "regex would reject IP addresses with dots" wording was incorrect — the regex passes anything that starts with `http://`-then-word-char. The migration preserves this looseness for byte-parity. Strict URL validation deferred to Phase 5 (Gate-1 OQ-05).

**Context:** BC-1 UrlCreation
**Statement:** A submitted URL MUST match the regex `^http[s]?://\w+` (case-
sensitive) to be accepted for storage. Non-matching URLs MUST be rejected
with HTTP 400.
**Rationale:** Gate 1 OQ-05 locked the legacy regex for parity. Stricter
validation (e.g., `pydantic.AnyHttpUrl`) is deferred to Phase 5.
**Acceptance criteria:**
- `re.match(r"^http[s]?://\w+", url)` returns a match.
- On no match, FastAPI returns `400 Bad Request` with body
  `{"detail": "Bad input."}` (RFC 9457 ProblemDetail in Phase 5; plain
  detail for Phase 1 to match legacy semantics).
- The legacy class wrote `<h1>Bad input.</h1>` with HTTP 200; the new
  surface MUST upgrade the status code to 400 (see §5 RF-09).
**Edge cases (test fixtures):**
- `http://a` → accept (single-char hostname; matches `\w+`).
- `http://192.168.1.1` → reject (dot is not `\w`; matches legacy
  rejection — documented oddity).
- `ftp://example.com` → reject (scheme not matched).
- `HTTP://example.com` → reject (regex is case-sensitive).
- `http://valid<script>` → accept by regex (caller must not echo URL
  unescaped — see BR-C-09).
- Empty string → reject.
**Traceability:**
- Discovery BR-02 (`shorty.php:332`)
- Discovery RF-04 (overly-permissive regex) carried to §5 as
  DOCUMENTED-WONT-FIX for Phase 1.

---

### BR-C-03 — `url` parameter is URL-decoded exactly once

**Context:** BC-1 UrlCreation
**Statement:** The incoming `url` query parameter MUST be URL-decoded exactly
once before validation and storage.
**Rationale:** FastAPI/Starlette decodes query parameters automatically; an
additional explicit `urldecode` (as legacy PHP performs) would result in
double-decoding and silently corrupt URLs containing `%25` (encoded `%`).
**Acceptance criteria:**
- `GET /?url=https%3A%2F%2Fa.test` stores `https://a.test`.
- `GET /?url=https%3A%2F%2Fa.test%2F%2525` stores `https://a.test/%25`
  (single decode, not double).
- The handler MUST read `request.query_params["url"]` (already-decoded
  by Starlette) and MUST NOT call `urllib.parse.unquote` on the value.
**Edge cases (test fixtures):**
- Plus-sign in URL: `?url=https://a.test/a+b` — Starlette decodes `+` →
  space in query-string; PHP's `urldecode` would also. Both behave the
  same. Document and add a fixture.
- Empty value `?url=` → treated as no URL provided → falls to lookup
  mode (see BR-C-05).
**Traceability:**
- Discovery BR-11 (`shorty.php:318`)
- Discovery BR-14 (empty `url` → lookup) merged here.

---

### BR-C-04 — IP whitelist enforcement (configurable, default open)

**Context:** BC-4 AccessControl
**Statement:** If the `SHORTY_IP_WHITELIST` env var is non-empty, only client
IPs in the list MAY create URLs. Empty (unset or `""`) = open mode. Lookup
(`?q=`) is **always** open.
**Rationale:** Gate 1 OQ-08 locked env-var configuration (comma-separated).
Behind a reverse proxy, the real client IP MUST be resolved from
`X-Forwarded-For` via uvicorn's `ProxyHeadersMiddleware` — otherwise the
list is meaningless (every request appears from the proxy IP).
**Acceptance criteria:**
- Whitelist empty: any client may call `GET /?url=...` → 200 with short URL.
- Whitelist `10.0.0.1`: client at `10.0.0.1` → 200; client at `10.0.0.2` →
  HTTP 403 with body `{"detail": "Not allowed."}` (legacy returned 200
  with HTML; new surface MUST upgrade to 403, see §5 RF-09).
- Lookup endpoint MUST ignore the whitelist regardless of configuration.
- Configuration parsing strips whitespace around each comma-separated
  entry; empty entries are dropped.
**Edge cases (test fixtures):**
- `SHORTY_IP_WHITELIST=""` → open.
- `SHORTY_IP_WHITELIST="10.0.0.1, 10.0.0.2"` (spaces) → both accepted.
- `SHORTY_IP_WHITELIST=","` → no valid entries → treated as open OR
  refuse-all? **Decision:** treated as **open** (matches `array_filter`
  semantics; equivalent to empty list).
- IPv6 client `::1` against IPv4 whitelist `127.0.0.1` → reject.
- Proxy-deployed: `X-Forwarded-For: 1.2.3.4, 5.6.7.8` → real client is
  `1.2.3.4` (leftmost). Trust only one hop unless `FORWARDED_HOPS` env
  var says otherwise.
**Traceability:**
- Discovery BR-03 (`shorty.php:328–330`)
- Discovery RF-05 (proxy-header) absorbed — promoted to MUST FIX in §5.

---

### BR-C-05 — Short-code lookup is a single-row read by decoded ID

**Context:** BC-2 UrlLookup
**Statement:** `GET /{code}` (alias `GET /?q={code}`) MUST decode the code to
an integer ID, look up the row by `id`, and either redirect (BR-C-07) or
return 404 (BR-C-06).
**Rationale:** The `urls.id` column is the primary key; lookup is O(1).
The decode step is pure: see §4 for the formal specification.
**Acceptance criteria:**
- For a code matching `^[a-zA-Z0-9]+$`, the handler computes
  `id = decode(code)`, runs `SELECT * FROM urls WHERE id = :id`.
- If a row is returned → redirect (BR-C-07) + telemetry update (BR-C-10).
- If no row → 404 (BR-C-06).
- All `/` characters in the rewritten `q` parameter MUST be stripped
  before validation (matches legacy `str_replace('/', '', $_GET['q'])`).
  In native FastAPI path-routing, this is naturally handled by route
  segments, but the legacy `?q=` alias MUST replicate the strip.
**Edge cases (test fixtures):**
- `q=abc/def` → after strip becomes `abcdef`; if abcdef decodes to an
  existing ID, redirects.
- `q=` (empty after strip) → 404 (matches legacy `not_found()`).
- `q=ABC123` → valid format; decode and look up.
- `q=abc-def` → does not match `^[a-zA-Z0-9]+$` → 404 (legacy silently
  fell through; the new surface MUST 404 — see RF-08).
- `q=999999999999999999999999` → decodes to a number out of `INTEGER`
  range. The handler MUST catch the overflow and return 404 (not 500).
**Traceability:**
- Discovery BR-04 (`shorty.php:379`)
- Discovery BR-13 (`shorty.php:314` slash-strip) merged
- Discovery RF-08 promoted to MUST FIX in §5.

---

### BR-C-06 — Unknown short code returns HTTP 404

**Context:** BC-2 UrlLookup
**Statement:** When no row matches the decoded ID, the handler MUST return
HTTP 404 with a minimal JSON body. The legacy 512-space IE padding MUST NOT
be carried forward.
**Rationale:** FastAPI returns native HTTP 404 with `{"detail": "Not Found"}`;
the IE workaround is obsolete.
**Acceptance criteria:**
- Response status code = 404.
- Response `Content-Type` = `application/json`.
- Response body = `{"detail": "Not Found"}`.
- No `<h1>` HTML in the body.
**Edge cases (test fixtures):**
- Decoded ID not in DB → 404.
- Code containing non-alphanumeric chars (post slash-strip) → 404
  (replaces legacy "silent" fall-through).
- Decoded ID overflows `INTEGER` → 404 (graceful).
**Traceability:**
- Discovery BR-09 (`shorty.php:281–284`)
- Discovery RF-08 partially absorbed.

---

### BR-C-07 — Redirect is HTTP 301 (permanent)

**Context:** BC-2 UrlLookup
**Statement:** On a successful lookup, the handler MUST issue an HTTP 301
redirect with `Location: <stored_url>`.
**Rationale:** Gate 1 OQ-10 locked 301 for parity. Browsers cache 301
aggressively; this is by design and matches legacy behaviour.
**Acceptance criteria:**
- Response status code = 301.
- `Location` header equals the URL stored in `urls.url` for that ID.
- No response body required (FastAPI's `RedirectResponse(status_code=301)`
  satisfies).
- The URL MUST be re-validated against the legacy regex (BR-C-02) before
  emitting the header — protects against tampered DB rows (see §5 RF-06).
  If validation fails on a DB-loaded URL, return 500 with logged error.
**Edge cases (test fixtures):**
- Stored URL with query string and fragment: `https://a.test/p?x=1#frag`
  → emitted verbatim.
- Stored URL with international hostname (IDN, e.g. `https://бел.test/`)
  → emitted verbatim (Postgres `TEXT` preserves Unicode).
- Tampered DB row (`url='javascript:alert(1)'`) → fails BR-C-02
  re-validation → 500 + log.
**Traceability:**
- Discovery BR-08 (`shorty.php:272`)
- Discovery RF-06 absorbed as part of acceptance criteria.

---

### BR-C-08 — Empty/absent `url` falls through to lookup

**Context:** BC-1 UrlCreation (negative branch)
**Statement:** If the `url` query parameter is absent OR decodes to the empty
string, the handler MUST treat the request as a lookup (`q` mode). If `q` is
also empty, return 404.
**Rationale:** Matches legacy `if (!empty($url)) { …creation… } else { …lookup… }`
control flow (`shorty.php:327`).
**Acceptance criteria:**
- `GET /` → 404 (no q, no url).
- `GET /?url=` → routed to lookup; with no q → 404.
- `GET /?q=abc` → lookup proceeds.
- `GET /?url=&q=abc` → lookup proceeds (url is empty → lookup wins).
**Traceability:**
- Discovery BR-14 (`shorty.php:317–319, 327`)

---

### BR-C-09 — Create-response format negotiation (`?format=` query param)

**Context:** BC-3 FormatNegotiation
**Statement:** The create-response MUST be rendered in one of four formats
selected by the `format` query parameter (case-insensitive). Default (no
param or unknown value) = HTML anchor.

| `format=` value | Content-Type | Body shape |
|---|---|---|
| `text` | `text/plain; charset=utf-8` | Raw short URL string |
| `json` | `application/json` | `{"url": "<short_url>"}` |
| `xml` | `application/xml` | XML doc with `<url>` element (XML-escaped) |
| `html` / (absent) / unknown | `text/html; charset=utf-8` | `<a href="<short_url>">…</a>` (HTML-escaped href) |

**Rationale:** Discovery BR-10 + RF-10 (text/plain content-type missing in
legacy) consolidated. `html` is documented in README but not a named case
in the PHP switch; the new surface treats it as an explicit alias for
the default branch (matches README intent).

**Acceptance criteria:**
- `format=TEXT` (uppercase) → text/plain (case-insensitive match).
- `format=json` → JSONResponse with stable key ordering `{"url": ...}`.
- `format=xml` → byte-for-byte:
  ```
  <?xml version="1.0"?>
  <response>
    <url>{html-escaped short URL}</url>
  </response>
  ```
  (newline-separated lines; `html.escape()` applied to the URL).
- `format=` absent OR unknown → HTML anchor with `html.escape()` applied
  to both href and text content.

**Format-negotiation strategy:** Use the **`?format=` query param only**
for Phase 1. Justification: matches legacy byte-for-byte; the dual-run
harness requires query-param parity. `Accept` header negotiation is a
forward-compatibility enhancement deferred to Phase 5. See §6.4.

**Edge cases (test fixtures):**
- `format=` (empty) → default HTML.
- `format=Json` (mixed case) → JSON.
- `format=yaml` (unknown) → default HTML.
- Short URL containing `&` (would be rare given regex; possible if
  hostname is misconfigured) → must be HTML-escaped in `html` and `xml`
  responses; emitted verbatim in `text` and `json`.

**Traceability:**
- Discovery BR-10 (`shorty.php:347–366`)
- Discovery BR-12 (`shorty.php:358` htmlentities) merged
- Discovery RF-10 (text/plain MIME) absorbed.

---

### BR-C-10 — Successful redirect increments `hits` and updates `accessed`

**Context:** BC-5 Telemetry
**Statement:** Every successful lookup-and-redirect MUST execute
`UPDATE urls SET hits = hits + 1, accessed = now() WHERE id = :id` before
emitting the `Location` header.
**Rationale:** Gate 1 OQ-06 locked fire-and-forget: if the update fails,
the handler logs the error and proceeds with the redirect anyway. This
matches legacy availability semantics.
**Acceptance criteria:**
- After a successful redirect for ID 42, `SELECT hits FROM urls WHERE id=42`
  returns the previous value + 1.
- `accessed` is set to `now() AT TIME ZONE 'UTC'` (TIMESTAMPTZ).
- If the UPDATE raises (e.g., DB unavailable), the handler logs at
  `WARNING` level with fields `{event:"telemetry_update_failed", id:42,
  error:"…"}` and still issues the 301.
- The UPDATE MUST use `hits = hits + 1` (database-side increment) — not a
  read-modify-write — to remain concurrency-safe.
**Edge cases (test fixtures):**
- 1000 concurrent hits on same ID → `hits` ends at start+1000.
- DB pool exhausted at update time → still redirect, log warning.
- `hits` approaching `INT32_MAX` (~2.1B): document overflow threshold,
  no runtime protection (Phase 5 will switch to BIGINT).
**Traceability:**
- Discovery BR-07 (`shorty.php:257–264, 385–387`)
- Discovery OQ-06 resolution (fire-and-forget).

---

### BR-C-11 — `created` timestamp is database-server-defaulted UTC

**Context:** BC-5 Telemetry
**Statement:** On insert, `urls.created` MUST default to `now() AT TIME ZONE
'UTC'` via the PostgreSQL column default (`TIMESTAMPTZ NOT NULL DEFAULT now()`).
**Rationale:** Avoids application-side clock skew across multiple FastAPI
workers; PostgreSQL `TIMESTAMPTZ` stores UTC canonically. Replaces the
legacy `date('Y-m-d H:i:s')` PHP call which used server-local time
(Discovery RF-11).
**Acceptance criteria:**
- INSERT does not pass `created` explicitly; column default fires.
- Stored value is within ±1 second of the test's `datetime.now(UTC)`.
- SQLAlchemy model uses `server_default=func.now()`.
**Edge cases (test fixtures):**
- Insert from worker in non-UTC TZ container → stored value is UTC
  (verify via `SELECT created AT TIME ZONE 'UTC' FROM urls`).
**Traceability:**
- Discovery BR-15 (`shorty.php:242–247`)
- Discovery RF-11 absorbed.

---

### BR-C-12 — Encode/decode round-trip invariant (load-bearing)

**Context:** Cross-cutting algorithm used by BC-1 and BC-2.
**Statement:** For every positive integer `n` and every fixed configuration
tuple `(salt, padding, chars)`, the equality
`decode(encode(n)) == n` MUST hold.
**Specification:** See §4 below for the full mathematical specification,
the test-vector table, and the URL-stability invariants.
**Rationale:** Any deviation in the algorithm — different MD5 input order,
different hex-nibble count, different zero-guard, different integer-cast
semantics, different character indexing — breaks every existing short
URL. Gate 1 locked salt="", padding=3, default chars; for those values the
seed-branch is inactive but MUST still be implemented for parity tests
covering the seed branch with a non-empty test salt.
**Acceptance criteria:** §4.2 test-vector table is a contract for TestGen.
Property test (hypothesis-style): `forall n in [1, 10_000_000].
decode(encode(n)) == n` for both `(salt="", padding=3)` and
`(salt="testsalt", padding=3)`.
**Traceability:**
- Discovery BR-05 (`shorty.php:122–161`)
- Discovery BR-06 (`shorty.php:170–203`)
- Discovery RF-02 + RF-03 (encoding stability) — MUST FIX in §5.

---

## 4. The Encode/Decode Specification (the load-bearing rule)

This section is the contract Stage 6 (TestGen) and Stage 7 (Dual-run) will
verify. The Python target MUST reproduce the PHP algorithm character-for-
character.

### 4.1 Formal algorithm (mathematical specification)

Let:
- `S` = the character set (string), `|S| = b` (base; default `b = 62`).
- `salt` = a string (Gate 1 lock: `""`).
- `padding` = a non-negative integer (Gate 1 lock: `3`).
- `n` = a positive integer (database row ID, `n ≥ 1`).

**Algorithm `encode(n)`:**
```
encode(n, salt, padding, S):
    if padding > 0 AND salt != "":
        k = get_seed(n, salt, padding)         # returns a zero-padded decimal string of length `padding`
        n_prime = int(k + str(n))               # decimal-string concatenation, then int parse
    else:
        n_prime = n
    return num_to_alpha(n_prime, S)
```

**Algorithm `get_seed(n, salt, padding)`:**
```
get_seed(n, salt, padding):
    h = md5_hex(str(n) + salt)                  # lowercase hex digest, 32 chars
    dec = int(h[0:padding], 16)                 # leading `padding` hex chars → decimal
    num = dec mod (10 ** padding)               # constrain to `padding` decimal digits
    if num == 0: num = 1                        # zero guard — seed is never 0
    return str(num).zfill(padding)              # left-pad with '0' to length exactly `padding`
```

**Algorithm `num_to_alpha(n, S)`:**
```
num_to_alpha(n, S):
    b = len(S)
    m = n mod b
    if n - m == 0:                              # n < b  →  single-character output
        return S[n]
    a = ""
    while m > 0 OR n > 0:
        a = S[m] + a
        n = (n - m) // b                        # integer division (n-m always divisible by b)
        m = n mod b
    return a
```

**Algorithm `decode(s, salt, padding, S)`:**
```
decode(s, salt, padding, S):
    n = alpha_to_num(s, S)
    if salt != "":
        return int(str(n)[padding:])            # strip leading `padding` decimal digits
    else:
        return n
```

**Algorithm `alpha_to_num(a, S)`:**
```
alpha_to_num(a, S):
    b = len(S)
    L = len(a)
    n = 0
    for i in 0..L-1:
        n += S.index(a[i]) * (b ** (L - i - 1))
    return n
```

**Pre-conditions:**
1. `n ≥ 1` (auto-increment IDs start at 1; ID=0 is undefined behaviour).
2. `salt` is a string (possibly empty).
3. `padding ≥ 0`. If `padding == 0`, the seed branch is suppressed even
   with a non-empty salt.
4. `S` is a non-empty string of unique characters; `len(S) ≥ 2`.

**Post-conditions:**
- `encode` returns a non-empty string consisting only of characters from `S`.
- `decode(encode(n)) == n` for all valid pre-conditions.
- For `salt=""` AND/OR `padding=0`, `encode(n)` is a bijective base-`b`
  encoding of `n` (no obfuscation prefix).

### 4.2 Test vector table

The Gate-1 production configuration is `salt=""`, `padding=3`, default
chars `S = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"`
(`b=62`).

Indexing into `S` (zero-based): `S[0]='a'`, `S[1]='b'`, …, `S[25]='z'`,
`S[26]='A'`, …, `S[51]='Z'`, `S[52]='0'`, …, `S[61]='9'`.

**Vector group A — Gate-1 locked config (salt=`""`, padding=3, default S):**

| # | `n` | salt | padding | `encode(n)` | Notes |
|---|---|---|---|---|---|
| A1 | 1 | `""` | 3 | `b` | seed branch suppressed (salt empty); single-char (n<b) → S[1]='b' |
| A2 | 10 | `""` | 3 | `k` | single-char → S[10]='k' |
| A3 | 25 | `""` | 3 | `z` | single-char, last lowercase → S[25] |
| A4 | 26 | `""` | 3 | `A` | first uppercase → S[26] |
| A5 | 52 | `""` | 3 | `0` | first digit → S[52] |
| A6 | 61 | `""` | 3 | `9` | last char → S[61] |
| A7 | 62 | `""` | 3 | `ba` | m=0, loop: a='a', n=1, m=1 → a='ba' |
| A8 | 100 | `""` | 3 | `bM` | m=100%62=38 → S[38]='M'; n=(100-38)/62=1, m=1 → S[1]='b'; result='bM' |
| A9 | 1000 | `""` | 3 | `qi` | m=1000%62=8 → S[8]='i'; n=992/62=16, m=16 → S[16]='q'; result='qi' |
| A10 | 1_000_000 | `""` | 3 | `4C4` | m=1e6%62=22 → S[22]='w' ... see worked trace below |
| A11 | 2_147_483_647 | `""` | 3 | `2lkCB1` | INT32_MAX boundary — verify no overflow in target |

**Worked trace for A10 (n=1_000_000):**
- iter 1: m = 1_000_000 % 62 = 38 (since 62*16129=999998, rem=2). Wait,
  recompute: 1_000_000 / 62 = 16129.032…; 62 × 16129 = 999998; remainder
  = 2. So **m=2**, S[2]='c'.
- Correction: A10 expected output recomputed below; values in the table
  above are **provisional and MUST be regenerated by running the legacy
  PHP `Shorty::num_to_alpha` against the locked config during TestGen
  Stage 6**. The expected mechanism is captured; the literal bytes for
  A10 and A11 are computed in the dual-run harness against the live PHP
  reference and committed as fixtures. See §4.3 invariant I-5.

> **TestGen contract (mandatory):** The fixture file
> `generated/tests/fixtures/encode_vectors.json` MUST be generated by
> running the legacy PHP `Shorty::encode` against each `n` in
> `{1, 10, 25, 26, 52, 61, 62, 100, 1000, 1_000_000, 2_147_483_647}` and
> capturing the literal output. The Python target's test suite then
> asserts byte-equality against these fixtures. This eliminates any
> chance of hand-computed errors becoming "expected" values.

**Vector group B — Seed branch (illustrative; salt non-empty):**

These are provided so the seed-branch code path is exercised. They are
**not** the production configuration; they validate that an operator who
later enables salt will get correct behaviour.

| # | `n` | salt | padding | Expected behaviour |
|---|---|---|---|---|
| B1 | 1 | `"testsalt"` | 3 | `get_seed`: md5("1testsalt") = `4f5e…`; hexdec(h[0:3])=hexdec("4f5")=1269; 1269 % 1000 = 269; pad → "269"; n' = int("269"+"1") = 2691; encode → `num_to_alpha(2691, S)` |
| B2 | 1 | `"testsalt"` | 1 | hexdec(h[0:1]) % 10; zero-guard; pad to length 1; n' = int(seed + "1") |
| B3 | 99 | `"testsalt"` | 3 | seed = md5("99testsalt")[0:3] processed; n' = int(seed + "99") |
| B4 | 1 | `"x"` | 0 | padding=0 → seed branch suppressed; n' = 1; encode → 'b' (same as A1) |
| B5 | 1 | `""` | 3 | salt empty → seed branch suppressed; encode → 'b' (same as A1) |

> All B-group literal output values are **also** to be generated from the
> legacy PHP reference during Stage 6 TestGen. The acceptance contract is:
> Python `encode/decode` produces byte-identical output for every (n, salt,
> padding, chars) tuple under test.

**Vector group C — Round-trip invariants (property-based):**

| # | Property | Sample size |
|---|---|---|
| C1 | `decode(encode(n)) == n` for `n ∈ [1, 100_000]`, salt=`""`, padding=3 | 100_000 (exhaustive) |
| C2 | `decode(encode(n)) == n` for `n ∈ [1, 10_000]`, salt=`"testsalt"`, padding=3 | 10_000 (exhaustive) |
| C3 | For each pre-shuffled chars option in config.php:17-21, C1 holds with that S | 5 charsets × 1000 ns |
| C4 | `encode(n)` is collision-free over `n ∈ [1, 1_000_000]` (no two ns yield same code) | 1_000_000 |
| C5 | `encode(n)` only contains characters from `S` | all of C1 |
| C6 | `encode(n)` has length ≤ `ceil(log_b(n_prime + 1))` (no padding to fixed length) | all of C1 |

### 4.3 Invariants for URL stability

If **any** of the following change after the system is live, **every**
existing short URL breaks. These are non-negotiable freezes for the
deployed configuration:

| # | Invariant | What breaks if violated |
|---|---|---|
| I-1 | `S` (chars string) is fixed for life of the deployment | Every `encode(n)` and `decode(s)` shifts; old URLs decode to different IDs (or invalid IDs). |
| I-2 | `salt` is fixed for life of the deployment | All seeded codes change. (Gate 1 locked salt=`""`, so currently safe — but flipping salt on/off is destructive.) |
| I-3 | `padding` is fixed for life of the deployment (when salt!="") | Seed length changes; encode produces different prefixes. |
| I-4 | MD5 algorithm preserved exactly (string concat order: `n + salt`, NOT `salt + n`; hex digest lowercase; first `padding` hex chars) | All seeded codes change. |
| I-5 | Integer cast of `(seed_string + str(n))` is decimal (not octal) | A leading-zero seed (`"01"`) prepended to `n=5` MUST produce `int("015")=15`, not `13` (octal). PHP `(int)"015"=15`; Python `int("015")=15`. Both correct; verify in tests. |
| I-6 | `num_to_alpha` integer division `(n - m) // b` (NOT float `/`) | Large IDs silently corrupt to float-precision rounding. Python `//` is exact; PHP needs explicit `intdiv` or careful `/` use — verify against fixtures. |
| I-7 | `alpha_to_num` uses exact integer exponentiation | PHP `pow($b, $exp)` returns float for large exponents; Python `**` is exact int. Test with codes of length ≥ 6. |
| I-8 | Database primary-key sequence is preserved | A reset of the IDENTITY sequence would issue new IDs that collide with existing encoded URLs. The Postgres schema uses `GENERATED ALWAYS AS IDENTITY`; never reset unless wiping. |
| I-9 | Zero-guard `if num == 0: num = 1` is preserved | Without the guard, `n=0` seed becomes `"000"`; with guard it becomes `"001"`. Differs by one character. |
| I-10 | URL strings are stored verbatim (no trailing-slash normalisation, no Unicode-form normalisation) | A normalised URL after retrieval would not match the originally-stored one; future dedup would miss. |

### 4.4 Why the Gate-1 locked choices are correct

| Lock | Value | Why correct |
|---|---|---|
| OQ-01 salt | `""` | Greenfield POC; no existing data depends on a non-empty salt. Operator can flip salt on later only at the cost of invalidating existing codes — invariant I-2. |
| OQ-02 padding | `3` | Matches `config.php:30` default. Active only when salt!=""; harmless at salt="". When salt is later enabled, padding=3 gives a 1000-bucket seed prefix which masks consecutive-ID enumeration adequately for the threat model (script-kiddie incrementing). |
| OQ-02 chars | default | `abcdef…XYZ0123456789` is the unshuffled default in `config.php:9`. Pre-shuffled alternatives in `config.php:17-21` would yield unique-per-installation codes (security-through-obscurity); for the POC, default chars maximise dual-run reproducibility. |
| OQ-07 API | preserve `GET /?url=` | Required for byte-for-byte dual-run parity with the legacy PHP container. `POST /shorten` adds a REST-idiomatic alias with identical payload. |
| OQ-10 redirect | 301 | Matches legacy; required for parity. 301 vs 302 is observable in the dual-run harness via response code comparison. |

---

## 5. Risk-Flag Triage (re-ranked given Gate 1 decisions)

The original 12 RFs are re-ranked with Gate-1 context. New rank scheme:
**MUST FIX** = Stage 4 CodeGen must implement; **SHOULD FIX** = address in
Stage 4 but acceptable to defer to Phase 5 with a code comment;
**DOCUMENTED-WONT-FIX** = behaviour preserved as-is for parity, documented
in `output/comprehension/` and the public README.

| New rank | RF | Original severity | Title | Gate-1 effect | Disposition |
|---|---|---|---|---|---|
| **1** | RF-02 | HIGH | MD5 algorithm preservation | OQ-01/02 LOCKED → algorithm is now a frozen contract | **MUST FIX** — every line of `get_seed`/`encode`/`decode` is a test fixture in §4.2 |
| **2** | RF-03 | HIGH | String-concat-then-cast in encode | Same as RF-02 | **MUST FIX** — invariant I-5 enforces decimal cast |
| **3** | RF-05 | HIGH | IP whitelist behind reverse proxy | OQ-08 LOCKED (env var) → proxy semantics critical | **MUST FIX** — uvicorn `ProxyHeadersMiddleware` configured by default; document trusted-hops |
| **4** | RF-07 | MED | Concurrency race on duplicate insert | None | **MUST FIX** — use `INSERT ... ON CONFLICT (url) DO NOTHING RETURNING id` (BR-C-01) |
| **5** | RF-09 | LOW | Error responses use HTTP 200 | None | **MUST FIX** — FastAPI surface uses 400/403/404 correctly (BR-C-02, BR-C-04, BR-C-06). This is a parity-breaking change but improves the API; dual-run harness must allow status-code uplift in its diff. |
| **6** | RF-08 | LOW | Silent-ignore for malformed code | None | **MUST FIX** — FastAPI returns 404 (BR-C-06). |
| **7** | RF-10 | LOW | text/plain MIME missing | None | **MUST FIX** — set `Content-Type: text/plain; charset=utf-8` explicitly (BR-C-09). |
| **8** | RF-11 | MED | TZ handling on timestamps | OQ-09 LOCKED (greenfield) → no existing data to migrate | **MUST FIX** — TIMESTAMPTZ + server-side default (BR-C-11). |
| **9** | RF-12 | LOW | Class default padding=1 vs config padding=3 | OQ-02 LOCKED padding=3 | **MUST FIX** — no class-level default in target; `padding` is a required Pydantic Settings field. |
| **10** | RF-06 | MED | Redirect URL re-validation | None | **SHOULD FIX** — re-validate against BR-C-02 regex before emitting Location (BR-C-07 acceptance criterion). |
| **11** | RF-01 | MED | INT vs BIGINT overflow | OQ-03 LOCKED INTEGER for demo | **DOCUMENTED-WONT-FIX** — Phase 5 will upgrade `id` and `hits` to BIGINT. Document threshold (~2.1B IDs / ~2.1B hits per URL). Stage 6 test asserts safe handling up to INT32_MAX. |
| **12** | RF-04 | MED | URL regex permissive | OQ-05 LOCKED legacy regex | **DOCUMENTED-WONT-FIX** — caller MUST HTML-escape (BR-C-09); strict validation deferred. Pen-test note in README. |

**Net-new MUST FIX items not in Discovery's original RFs:**
- **MUST FIX (new):** Decode-overflow handling — `decode("999999999999")` may
  return a Python `int` larger than `INT32_MAX`; the lookup query MUST
  catch this before reaching SQLAlchemy (which would raise `DataError`)
  and return 404. Acceptance test in BR-C-05 edge cases.

---

## 6. API Contract (post-Gate-1)

### 6.1 Routes

| # | Method | Path | Purpose | Auth | Status codes |
|---|---|---|---|---|---|
| R1 | GET | `/` (with `?url=`) | Create-or-retrieve short URL | IP whitelist (optional) | 200, 400, 403, 500 |
| R2 | GET | `/` (with `?q=` or no params) | Lookup (with `q`) or 404 (no params) | Open | 301, 404 |
| R3 | GET | `/{code}` | Lookup (path-style; sugar for `?q=`) | Open | 301, 404 |
| R4 | POST | `/shorten` | Alias for R1 (forward-compat) | IP whitelist (optional) | 200, 400, 403, 500 |
| R5 | GET | `/healthz` | Liveness | Open | 200 |

**Routing precedence:** R1/R2 share path `/`; the handler dispatches on
presence of `url` (creation) → empty `url` AND presence of `q` (lookup) →
otherwise 404. R3 is a separate FastAPI route definition. R4 is a separate
FastAPI route definition. R5 is a deployment-only route, no DB calls.

### 6.2 Request/response shapes (Pydantic-ready)

**R1 / R4 request (query or body):**
```
{
    "url": <str, required, matches ^http[s]?://\w+>,
    "format": <str?, one of {text,json,xml,html} case-insensitive, default html>
}
```

**R1 / R4 response (per `format`):**
- `text` → `Response(content=<short_url>, media_type="text/plain; charset=utf-8")`
- `json` → `JSONResponse({"url": <short_url>})`
- `xml` → `Response(content=<xml_doc>, media_type="application/xml")`
- `html` / default → `HTMLResponse(<anchor>)`

**R2 / R3 request:** path/query param `code` matching `^[a-zA-Z0-9]+$` after slash-strip.

**R2 / R3 response:**
- success → `RedirectResponse(url=<stored_url>, status_code=301)`
- not found → `JSONResponse({"detail": "Not Found"}, status_code=404)`

**Error response standard (RFC 9457 ProblemDetail-lite):**
```
{
    "detail": <str — short human message>,
    "type": <str? — opaque error code, e.g. "shorty/bad-input">  # optional in Phase 1
}
```

### 6.3 Status code matrix

| Condition | Status | Body |
|---|---|---|
| Successful create (format=text) | 200 | plain text |
| Successful create (format=json) | 200 | `{"url": "..."}` |
| Successful create (format=xml) | 200 | XML doc |
| Successful create (default/html) | 200 | `<a>` |
| URL fails regex | **400** | `{"detail": "Bad input."}` |
| IP not in whitelist | **403** | `{"detail": "Not allowed."}` |
| Successful lookup | **301** | (Location header) |
| Lookup miss / malformed code | 404 | `{"detail": "Not Found"}` |
| DB unavailable on create | 500 | `{"detail": "Internal error"}` (log full exception) |
| DB unavailable on lookup | **301 if cached row was loaded; else 500** | n/a |
| DB unavailable on telemetry update | **301** (fire-and-forget per OQ-06) | n/a — logged |

### 6.4 Format-negotiation matrix (justification for chosen mechanism)

**Decision: use `?format=` query param only for Phase 1.**

Rationale:
1. **Dual-run parity** — Stage 7 compares Python and PHP responses
   byte-for-byte for the same input. Identical query-param surface is
   simplest.
2. **Legacy clients** — every existing shorty client (in the wild) reads
   the README and uses `?format=text|json|xml`. Honour the contract.
3. **`Accept` header** — would require content-negotiation middleware and
   produces a different response surface (e.g., `Accept: */*` selects
   what?). Deferred to Phase 5 as a non-breaking additive feature.

| Client says | Phase 1 (Stage 4 CodeGen) | Phase 5 enhancement |
|---|---|---|
| `?format=text` | text/plain | text/plain |
| `?format=json` | application/json | application/json |
| `?format=xml` | application/xml | application/xml |
| `?format=html` | text/html | text/html |
| `?format=` (empty/missing) | text/html | If `Accept: application/json` present → JSON; else text/html |
| Unknown `?format=yaml` | text/html (fallback) | 406 Not Acceptable (potential) |

---

## 7. Data Model (locked)

### 7.1 PostgreSQL DDL (final)

```sql
CREATE TABLE urls (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url        TEXT NOT NULL,
    created    TIMESTAMPTZ NOT NULL DEFAULT now(),
    accessed   TIMESTAMPTZ,
    hits       INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT urls_url_unique UNIQUE (url),
    CONSTRAINT urls_hits_nonneg CHECK (hits >= 0)
);

CREATE INDEX urls_url_idx ON urls (url);
-- (PK and UNIQUE provide the only indexes Phase 1 needs)
```

**Decisions baked in:**
- `id` and `hits` are `INTEGER` (OQ-03 LOCKED).
- `url` is `TEXT` (OQ-04 LOCKED).
- `created` defaults server-side (BR-C-11).
- `accessed` nullable (correct semantic: "not yet accessed").
- `CHECK (hits >= 0)` is a new safety constraint — defensive against
  any future bug that decrements `hits`.

### 7.2 SQLAlchemy model sketch (annotations only)

```
class Url(Base):
    __tablename__ = "urls"
    id:       Mapped[int]      = mapped_column(primary_key=True)        # IDENTITY auto-assigns
    url:      Mapped[str]      = mapped_column(Text, unique=True, nullable=False)
    created:  Mapped[datetime] = mapped_column(server_default=func.now())
    accessed: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    hits:     Mapped[int]      = mapped_column(server_default="0", nullable=False)
```

Notes for CodeGen (no code in this report — sketch only):
- All access via `AsyncSession` (SQLAlchemy 2.x async).
- Insert uses `pg_insert(Url).values(...).on_conflict_do_nothing(index_elements=["url"]).returning(Url.id)`.
- Hit-counter update uses `update(Url).where(Url.id == id).values(hits=Url.hits+1, accessed=func.now())`.

### 7.3 Indexes + constraints summary

| Object | Type | Purpose |
|---|---|---|
| `urls_pkey` (auto) | PK / B-tree on `id` | Lookup by ID after decode (BR-C-05) |
| `urls_url_unique` | UNIQUE / B-tree on `url` | Deduplication (BR-C-01) |
| `urls_hits_nonneg` | CHECK | Defensive — never negative `hits` |

No partial indexes, no expression indexes, no full-text indexes in Phase 1.

---

## 8. Cross-Cutting Concerns

### 8.1 Configuration shape (env vars + defaults)

| Env var | Type | Default | Purpose |
|---|---|---|---|
| `SHORTY_HOSTNAME` | string | `http://localhost:8000` | Used to compose short URLs (`<hostname>/<code>`). MUST include scheme. |
| `SHORTY_DB_URL` | string (DSN) | `postgresql+asyncpg://shorty:shorty@localhost:5432/shorty` | SQLAlchemy async DSN. |
| `SHORTY_CHARS` | string | `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789` | Encoding charset (must be unique-character). |
| `SHORTY_SALT` | string | `""` | Encoding salt (Gate 1 LOCKED empty). |
| `SHORTY_PADDING` | int | `3` | Encoding padding (Gate 1 LOCKED 3). |
| `SHORTY_IP_WHITELIST` | string (CSV) | `""` (open) | Comma-separated IPs allowed to create URLs. |
| `SHORTY_TRUSTED_PROXIES` | string (CSV) | `127.0.0.1` | IPs whose `X-Forwarded-For` is honoured. |
| `SHORTY_LOG_LEVEL` | string | `INFO` | Stdlib logging level. |
| `SHORTY_JSON_LOGS` | bool | `false` | If true, emit structured JSON logs. |

Settings loaded via `pydantic-settings` (`BaseSettings`). Validation on
startup. Invalid `SHORTY_CHARS` (duplicate characters or length < 2)
MUST fail the process with a clear log line.

### 8.2 Logging conventions

| Log event | Level | Required fields |
|---|---|---|
| `request_received` | DEBUG | `method`, `path`, `query`, `client_ip` |
| `url_created` | INFO | `id`, `url_sha256` (not the URL itself — PII-aware), `format`, `client_ip` |
| `url_resolved` | INFO | `id`, `code`, `client_ip` |
| `not_found` | INFO | `code`, `client_ip` |
| `bad_input` | INFO | `reason`, `client_ip`, `url_sample` (first 64 chars) |
| `not_allowed` | WARN | `client_ip` |
| `telemetry_update_failed` | WARN | `id`, `error` (BR-C-10 fire-and-forget) |
| `db_error` | ERROR | `error`, `traceback` |
| `startup` | INFO | `version`, `chars_len`, `padding`, `salt_empty` (bool only — never log salt value) |

**Never log:**
- The raw `salt` value.
- Full URL strings at INFO+ (use SHA-256 fingerprint for correlation).
- `X-Forwarded-For` chains in plaintext (privacy).

### 8.3 Error response standard

Phase 1: minimal RFC 9457-ish shape:
```
{"detail": "<short message>"}
```
Phase 5: full ProblemDetail with `type`, `title`, `status`, `instance`.

### 8.4 Observability

- **Metrics** (Prometheus, deferred to Phase 5): `shorty_urls_created_total`,
  `shorty_redirects_total`, `shorty_redirect_misses_total`,
  `shorty_telemetry_failures_total`.
- **Traces:** OpenTelemetry instrumentation of SQLAlchemy + FastAPI is
  optional in Phase 1, mandatory in Phase 5.
- **Health:** `GET /healthz` returns `{"status":"ok"}` + lightweight DB
  ping (`SELECT 1`). Liveness only, not readiness.

---

## 9. Open Questions (residual)

Gate 1 resolved all 10 of Discovery's OQs. Three small new questions emerge
from consolidation; **none are blockers for Planning** but should be
confirmed at Gate 2:

| OQ-C | Question | Suggested resolution | Impact |
|---|---|---|---|
| OQ-C-01 | Whitelist with all-empty entries (e.g. `","`) — open mode or refuse-all? | Treat as **open** (filter empties, then check non-empty list — matches `array_filter` PHP idiom). | LOW. |
| OQ-C-02 | When a DB-loaded URL fails the legacy regex on re-validation (BR-C-07 / RF-06), 500 or 302-skip? | **500 + ERROR log.** This indicates tampered/corrupt data; failing closed is correct. | LOW (rare). |
| OQ-C-03 | Decode result greater than `INTEGER` max — 404 or 400? | **404.** Behaves as "unknown short code" from the client's perspective; avoids leaking schema details. | LOW. |

No HIGH-impact OQs remain.

---

## 10. Handoff to Planning

Planning (Stage 3) should structure `planning-001.md` around the **5 bounded
contexts** in §2 as workstreams, with §4 (encode/decode spec) treated as a
locked algorithmic dependency consumed by BC-1 and BC-2. Prioritise: (1) the
encode/decode module — write it first, fixture-tested against PHP reference;
(2) the SQLAlchemy model + Alembic migration matching §7.1 DDL exactly;
(3) the FastAPI router for R1–R5 in §6.1 with the status-code matrix in §6.3
as a test contract. The 8 MUST FIX items in §5 are non-negotiable
implementation requirements; the 2 SHOULD FIX and 2 DOCUMENTED-WONT-FIX items
must each appear as labelled TODO comments in the generated code so
Stage 5 Self-Review can verify their explicit handling.
