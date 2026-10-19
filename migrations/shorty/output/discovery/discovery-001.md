# MWU-SHORTY-001 — Discovery Report
**Classification:** DRAFT
**Generated:** 2026-05-14T00:00:00Z
**Agent:** discovery_agent (claude-code subagent — feature-dev:code-explorer)
**Source commit:** mikecao/shorty (single-depth clone, no upstream commit recorded)

---

## 1. Engagement Context

### What is shorty?

Shorty is a self-hosted, single-file PHP URL shortener authored by Mike Cao (MIT licence, 2011). It accepts a long URL via a query-string parameter, stores it in a single MySQL `urls` table, and returns a short alphanumeric code derived from the auto-incremented row ID. Subsequent requests using that short code are resolved with a permanent HTTP 301 redirect back to the original URL. The code is entirely contained in one class (`Shorty`, `shorty.php`), one bootstrap (`index.php`), and one config file (`config.php`). There is no framework, no auth layer, no queue, and no cache — it is a minimal, stateless PHP script.

### Why migrate?

The source stack (PHP 5.x / MySQL / Apache mod_rewrite) is end-of-life. The target organisation is standardising on Python 3.12 + FastAPI + PostgreSQL 16, and this codebase is selected as the pilot migration unit precisely because of its low complexity: single entity, clean PDO, no sessions, no money fields, no complex joins. A successful migration here validates the pipeline (Discovery → Comprehension → Planning → CodeGen → Self-Review → TestGen → Dual-run → Gate 4) before it is applied to the larger FrontAccounting ERP.

### Complexity Rating

**LOW.** Rationale: single database table, single class (~395 lines), zero external library dependencies, no authentication, no monetary arithmetic, no multi-tenancy, no batch operations. The only algorithmic complexity worth careful attention is the `encode`/`decode`/`get_seed` ID-obfuscation triplet, which is the load-bearing logic for URL stability across migration.

---

## 2. File Inventory

| File | Line Count | Purpose | Key Constructs |
|---|---|---|---|
| `shorty.php` | 395 | Main class — all business logic | `class Shorty`; public methods: `run()`, `encode()`, `decode()`, `fetch()`, `find()`, `store()`, `update()`, `redirect()`, `not_found()`, `error()`, `allow()`; static methods: `get_seed()`, `num_to_alpha()`, `alpha_to_num()`; private properties: `$chars`, `$salt`, `$padding`, `$hostname`, `$connection`, `$whitelist` |
| `index.php` | 12 | Bootstrap / entry point | Requires `shorty.php` and `config.php`; instantiates `Shorty`; calls `$shorty->run()` |
| `config.php` | 31 | Runtime configuration | Globals: `$hostname`, `$connection` (PDO), `$chars`, `$salt`, `$padding`; five pre-shuffled example `$chars` strings |
| `database.sql` | 12 | MySQL DDL for `urls` table | Table `urls`; columns: `id`, `url`, `created`, `accessed`, `hits`; `PRIMARY KEY (id)`, `UNIQUE (url)` |
| `README.md` | 64 | User documentation | Installation steps; Apache `.htaccess` + Nginx rewrite rules; format options; whitelist usage; requirements |

**Total PHP LOC: 438** (395 + 12 + 31).

---

## 3. Data Model

### 3.1 MySQL Schema (as-is)

```sql
CREATE TABLE urls (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    url VARCHAR(1000) NOT NULL,
    created DATETIME NOT NULL,
    accessed DATETIME,
    hits INT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE (url)
);
```

Source: `database.sql:4–12`

### 3.2 PostgreSQL Target Schema

```sql
CREATE TABLE urls (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url        TEXT NOT NULL,
    created    TIMESTAMPTZ NOT NULL DEFAULT now(),
    accessed   TIMESTAMPTZ,
    hits       INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT urls_url_unique UNIQUE (url)
);
```

Rationale for each change: see §3.3 below.

### 3.3 Type Mapping Notes

| Column | MySQL Type | PostgreSQL Type | Rationale |
|---|---|---|---|
| `id` | `INT UNSIGNED AUTO_INCREMENT` | `INTEGER GENERATED ALWAYS AS IDENTITY` | PostgreSQL has no unsigned integer type. Max value of `INT UNSIGNED` is 4,294,967,295; `INTEGER` (signed 32-bit) holds up to 2,147,483,647. For a URL shortener the signed limit is almost certainly sufficient, but see RF-01. Migration rule 1 + 3 applied. |
| `url` | `VARCHAR(1000)` | `TEXT` | URL length of 1000 is an arbitrary cap; PostgreSQL `TEXT` has no practical limit and avoids silent truncation if ever a longer URL is encountered. Alternatively `VARCHAR(2048)` to match RFC 7230 practical maximum — decision left to Comprehension. See OQ-04. |
| `created` | `DATETIME NOT NULL` | `TIMESTAMPTZ NOT NULL` | MySQL `DATETIME` has no timezone. `TIMESTAMPTZ` stores in UTC and converts on read — correct for a global shortener. Migration rule 2 applied. |
| `accessed` | `DATETIME` (nullable) | `TIMESTAMPTZ` (nullable) | Same timezone reasoning. NULL is correct default (not yet accessed). Migration rule 2 applied. |
| `hits` | `INT UNSIGNED NOT NULL DEFAULT 0` | `INTEGER NOT NULL DEFAULT 0` | No unsigned in PG. Max `INTEGER` is ~2.1 billion hits per URL. If a viral URL exceeds this, `BIGINT` should be used. Risk is LOW for most deployments. Migration rule 3 applied. |

No `DECIMAL`/float monetary fields exist. Migration rule 11 is N/A.
No `$_SESSION` usage exists anywhere in the source. Migration rule 10 is N/A.
No `DEFAULT '0000-00-00'` date values exist. Migration rule 7 is N/A.

### 3.4 Index Strategy

| Index | MySQL | PostgreSQL Recommendation | Notes |
|---|---|---|---|
| `PRIMARY KEY (id)` | B-tree | Preserved — `GENERATED ALWAYS AS IDENTITY` creates it automatically | No change required |
| `UNIQUE (url)` | B-tree | Preserved — `CONSTRAINT urls_url_unique UNIQUE (url)` | Drives the deduplication lookup in `find()` (BR-01). Critical to keep. |
| `(url)` full-text search | Not present | Not needed | Only exact-match lookups are performed |
| `(hits)` | Not present | Not recommended | No query sorts by hits; skip |
| `(created)` / `(accessed)` | Not present | Optional if analytics queries are added later | Out of scope for Phase 1 |

### 3.5 Naming

**Retain the table name `urls` unchanged.** Rationale:
1. Semantically accurate and unambiguous.
2. No conflict with PostgreSQL reserved words.
3. Renaming would require changes in all SQLAlchemy model references with no functional benefit.
4. Single-schema deployment (no multi-tenancy) means no namespace collision risk.

If a schema prefix is desired to align with the FrontAccounting pattern, a `shorty` schema could be used: `shorty.urls`. Deployment decision for Planning.

---

## 4. Business Rules

```
BR-01: URL deduplication — same long URL always returns the same short code
  Source:    shorty.php:334–343
  Logic:     Before storing, `find($url)` performs a SELECT on the UNIQUE-indexed `url` column.
             If a matching row exists, its existing `id` is encoded and returned.
             If not, `store($url)` inserts and returns `lastInsertId()`.
  Migration: The `find()` query must execute before `store()` to maintain deduplication.
             The UNIQUE constraint on `url` provides a database-level safety net.
  Edge cases: Race condition — two simultaneous requests for the same new URL could both
             pass the `find()` check before either inserts, resulting in a unique constraint
             violation on the second insert. The PHP code does not handle this; it would throw
             an uncaught PDOException. The target should use INSERT ... ON CONFLICT DO NOTHING
             or retry logic. See RF-07.
```

```
BR-02: URL format validation — only http:// and https:// URLs are accepted
  Source:    shorty.php:332
  Logic:     `preg_match('/^http[s]?\:\/\/[\w]+/', $url)` — the URL must start with
             `http://` or `https://` followed by at least one word character.
  Migration: Re-implement the regex in Python. Note the regex is quite permissive —
             `\w+` matches word characters only in the hostname, but does not validate
             the full URL structure. See RF-04 for a discussion of what the regex misses.
  Edge cases: The regex would reject URLs like `http://192.168.1.1` (IP addresses with dots).
             `http://a` (single character hostname) would pass — `+` means one or more.
             See OQ-05.
```

```
BR-03: Whitelist access control — URL creation is restricted to listed IPs if whitelist is non-empty
  Source:    shorty.php:328–330
  Logic:     If `$this->whitelist` is non-empty AND `$_SERVER['REMOTE_ADDR']` is not in the
             array, the request is rejected with `error('Not allowed.')`.
             If whitelist is empty, all IPs are permitted (open mode).
  Migration: FastAPI equivalent: compare `request.client.host` against a configured list.
             Critical gap: `REMOTE_ADDR` does not see the real client IP behind a reverse
             proxy or load balancer. The target must handle `X-Forwarded-For` / `X-Real-IP`.
             See RF-05.
  Edge cases: Whitelist is configured in `index.php` by calling `$shorty->allow(...)` after
             instantiation. The default config ships with no whitelist calls, meaning the
             instance is open by default.
```

```
BR-04: Short code format validation — only alphanumeric codes are accepted for lookup
  Source:    shorty.php:379
  Logic:     `preg_match('/^([a-zA-Z0-9]+)$/', $q, $matches)` — the short code must consist
             entirely of alphanumeric characters. Codes containing any other character are
             silently ignored (fall through to end of `run()` without a 404).
  Migration: Apply the same validation. Note the silent-ignore path is a minor bug — a
             malformed code should return 404, not silently terminate. The target should
             return HTTP 404. See RF-08.
  Edge cases: The `q` parameter is pre-processed by `str_replace('/', '', $_GET['q'])`
             (shorty.php:314) before validation — forward slashes are stripped.
```

```
BR-05: Encoding stability — same database ID always encodes to the same short code given
       identical (salt, padding, chars) configuration
  Source:    shorty.php:122–131 (encode), 139–143 (decode), 153–161 (get_seed)
  Logic:     encode(n):
                if padding > 0 AND salt is non-empty:
                    k = get_seed(n, salt, padding)      // deterministic MD5-derived prefix
                    n = int(str(k) + str(n))             // string-concat k and n, cast to int
                return num_to_alpha(n, chars)            // base-62 encode the resulting integer
             get_seed(n, salt, padding):
                hash = md5(str(n) + salt)
                dec = hexdec(first `padding` hex chars of hash)
                num = dec % 10^padding
                if num == 0: num = 1                     // zero guard: seed is never 0
                num = str_pad(num, padding, '0')         // left-pad to exactly `padding` digits
                return num
             decode(s):
                n = alpha_to_num(s, chars)               // base-62 decode
                if salt non-empty: return n[padding:]    // strip the leading `padding` digits
                else: return n
  Migration: The Python target MUST reproduce this algorithm exactly, character by character,
             including the `md5` call, the `hexdec` of the first `padding` hex nibbles, the
             modulo, the zero guard (num=1), and the string-concatenate. Any deviation will
             break all existing short URLs. See RF-02 and RF-03.
  Edge cases:
    - When salt is empty OR padding == 0, no seed is prepended; encode is pure base-conversion.
    - The string concatenation `(int)($k.$n)` where k='01' and n=5 produces int 15, not int 015
      (octal). PHP's (int) cast on a string starting with '0' does NOT treat it as octal — it
      parses left-to-right decimal. The Python equivalent int(k + str(n)) behaves identically.
    - Zero guard makes the minimum seed digit-value 1, so str_pad of 1 with padding=2 gives '01'.
    - Large IDs: PHP handles arbitrarily large integers on 64-bit systems. Python int is unbounded.
```

```
BR-06: Base-62 encoding — num_to_alpha implements a bijective base-N conversion
  Source:    shorty.php:170–185 (num_to_alpha), 194–203 (alpha_to_num)
  Logic:     num_to_alpha(n, s):
                b = len(s)   // base (62 for default charset)
                m = n % b
                if n - m == 0: return s[n]   // n < b: single character
                a = ''
                while m > 0 or n > 0:
                    a = s[m] + a
                    n = (n - m) / b
                    m = n % b
                return a
             alpha_to_num(a, s):
                b = len(s)
                for each char at position i (0-indexed):
                    n += index_of(char_in_s) * b^(length - i - 1)
                return n
  Migration: Straightforward Python port. Division must be integer division (//) not float.
             Python's `str.index()` or a precomputed dict for O(1) lookup.
  Edge cases:
    - n=0 is a special case: `n - m == 0` when m=0 → returns `s[0]` = 'a'. MySQL AUTO_INCREMENT
      starts at 1, so ID=0 should never appear in practice.
    - The while loop condition `m > 0 or n > 0` terminates correctly because integer division
      shrinks n toward 0.
    - `alpha_to_num` uses `pow(b, ...)` which in PHP returns float for large exponents.
      Python's `**` operator returns exact int. Python is more precise.
```

```
BR-07: Hit counter increment — every successful redirect increments `hits` and updates `accessed`
  Source:    shorty.php:257–264 (update), shorty.php:385–387 (call site in run())
  Logic:     `UPDATE urls SET hits = hits + 1, accessed = ? WHERE id = ?`
             Called unconditionally after a successful `fetch()`.
  Migration: Use SQLAlchemy `update()` with `hits = urls.c.hits + 1`. The timestamp
             should be `datetime.now(timezone.utc)` in the async handler.
  Edge cases:
    - Update is not atomic with the redirect in the PHP code. In FastAPI, the update should
      be awaited before issuing `RedirectResponse`.
    - Concurrent hits: `hits + 1` at the database level is safe (atomic SQL arithmetic).
    - If the update fails (DB error), the redirect still happens in the PHP code (no try/catch).
      Decision for Comprehension: block redirect on update failure or fire-and-forget? See OQ-06.
```

```
BR-08: Redirect status code is 301 (Permanent)
  Source:    shorty.php:272
  Logic:     `header("Location: $url", true, 301)` — hard-coded 301.
  Migration: FastAPI `RedirectResponse(url=result.url, status_code=301)`. Browsers cache 301
             aggressively. Changing to 302 would be a behaviour change.
  Edge cases: Browser caching of 301 means if a short URL is later deleted or re-targeted, the
             browser will continue redirecting from its cache. Inherent to 301, not a bug.
```

```
BR-09: 404 response includes IE padding
  Source:    shorty.php:281–284
  Logic:     `not_found()` outputs `<h1>404 Not Found</h1>` followed by 512 spaces.
             Well-known "friendly error page" workaround for old IE versions.
  Migration: FastAPI should return HTTP 404 with `{"detail": "Not Found"}` (default JSON).
             The IE padding is obsolete and should not be carried forward.
  Edge cases: The PHP `header('Status: 404 Not Found')` call sets a CGI/FastCGI status header;
             the correct Apache/PHP header for HTTP status is `header('HTTP/1.1 404 Not Found')`.
             Minor bug in the legacy code. FastAPI handles status codes natively and correctly.
```

```
BR-10: Output format negotiation — four formats supported for URL creation responses
  Source:    shorty.php:347–366
  Logic:     The `format` parameter (case-insensitively lowercased) selects the response:
                - 'text'  → plain text, Content-Type not set (defaults to text/html in PHP)
                - 'json'  → Content-Type: application/json, JSON object {"url": "<short_url>"}
                - 'xml'   → Content-Type: application/xml, XML document with <url> element
                - default → HTML anchor tag <a href="...">...</a>
  Migration: FastAPI route should accept a `format` query param and return:
                - 'text'  → Response(content=url, media_type="text/plain")
                - 'json'  → JSONResponse({"url": url})
                - 'xml'   → Response(content=xml_string, media_type="application/xml")
                - default → HTMLResponse with anchor tag
  Edge cases: The 'html' format string is documented in README.md but is not handled as a named
             case in the switch statement — it falls through to `default`. The FastAPI target
             should treat 'html' as an explicit case equal to default for clarity.
```

```
BR-11: URL is URL-decoded before processing
  Source:    shorty.php:318
  Logic:     `$url = urldecode($_GET['url'])` — incoming URL is explicitly decoded once.
  Migration: FastAPI/Starlette automatically decodes query string parameters. Explicit
             double-decoding in the target would be a bug. Use the raw value from
             `request.query_params['url']` without additional decoding.
  Edge cases: If the caller percent-encodes the URL twice, PHP's single explicit `urldecode`
             would decode it once. FastAPI's automatic decode would do the same. Consistent.
```

```
BR-12: XML output uses htmlentities() on the URL
  Source:    shorty.php:358
  Logic:     `htmlentities($url)` is applied to the URL before embedding in the XML response.
  Migration: In the Python target, the short URL composed as `hostname + '/' + code` will never
             contain XML-unsafe characters. However, to be safe, the target should XML-escape
             the URL. Python's `html.escape()` is sufficient.
  Edge cases: `$hostname` could theoretically contain '&' if misconfigured. Proper escaping
             guards against malformed XML output in that case.
```

```
BR-13: Short code is stripped of forward slashes before lookup
  Source:    shorty.php:314
  Logic:     `$q = str_replace('/', '', $_GET['q'])` — all '/' chars are removed before processing.
  Migration: Apply the same stripping. This accommodates web-server rewrite rules that may
             produce `?q=abc/def` for a request to `/abc/def`. Review during Planning.
  Edge cases: If the path contains multiple segments (e.g. `/a/b/c`), the rewrite produces
             `q=a/b/c`, which after slash removal becomes `q=abc`. Consistent.
```

```
BR-14: URL creation requires a non-empty `url` parameter; empty or absent `url` triggers lookup
  Source:    shorty.php:317–319, 327
  Logic:     The code first checks `isset($_GET['url'])` and decodes it into `$url`.
             Then `if (!empty($url))` branches to creation mode; otherwise falls to lookup mode.
  Migration: FastAPI: `url: Optional[str] = None` query parameter. If None or empty, proceed
             to lookup; otherwise proceed to creation.
  Edge cases: A request with `?url=` (empty value) would go to lookup mode after urldecode('')
             returns '' and empty('') is true. Consistent.
```

```
BR-15: Created timestamp is set at application layer, not by database default
  Source:    shorty.php:242–247
  Logic:     `date('Y-m-d H:i:s')` is computed in PHP and passed as a bound parameter to
             the INSERT. The database column has `NOT NULL` but no `DEFAULT`.
  Migration: The PostgreSQL target schema adds `DEFAULT now()` to `created`. The SQLAlchemy
             model can use `server_default=func.now()` or pass `datetime.now(timezone.utc)`
             explicitly. Either valid; `server_default` is cleaner and avoids clock skew.
  Edge cases: The PHP code uses server local time (not UTC). PostgreSQL `TIMESTAMPTZ` stores
             UTC. Migration should document whether existing rows' timestamps need timezone
             adjustment.
```

---

## 5. UI / API Contract

Shorty is entirely driven through query-string parameters on a single entry point (`/`). The web server rewrite rule maps `/<code>` to `/?q=<code>`. There is no web UI for entering URLs — all interactions are programmatic.

### 5.1 Route Table

| # | Method | URL Pattern | Description |
|---|---|---|---|
| R1 | GET | `/?url=<long_url>` | Create/retrieve a short URL (open mode) |
| R2 | GET | `/?url=<long_url>&format=<fmt>` | Create/retrieve with specified response format |
| R3 | GET | `/<code>` (rewritten to `/?q=<code>`) | Redirect to long URL |
| R4 | GET | `/` (no params) | Returns 404 |

### 5.2 R1/R2 — Create Short URL

**Request parameters:**

| Parameter | Type | Validation | Required |
|---|---|---|---|
| `url` | string | Must match `^http[s]?://\w+` | Yes |
| `format` | string | One of: `text`, `json`, `xml`, `html`, (default) | No |

**Responses:**

| Format | Status | Content-Type | Body |
|---|---|---|---|
| `text` | 200 | text/html (not set) | Raw short URL string |
| `json` | 200 | application/json | `{"url": "http://example.com/9xq"}` |
| `xml` | 200 | application/xml | XML document with `<url>` element |
| `html` / default | 200 | text/html | `<a href="http://example.com/9xq">http://example.com/9xq</a>` |
| Invalid URL | 200 | text/html | `<h1>Bad input.</h1>` (terminates via `exit()`) |
| IP not whitelisted | 200 | text/html | `<h1>Not allowed.</h1>` (terminates via `exit()`) |

Note: PHP uses `exit()` throughout; HTTP status code for errors is effectively 200. The target FastAPI should use proper status codes (400 / 403 / 422).

**FastAPI route proposal:** `GET /shorten?url=<long_url>&format=<fmt>` or preserve `GET /?url=...&format=...`.

### 5.3 R3 — Redirect (Lookup)

**Request parameters:**

| Parameter | Type | Validation | Required |
|---|---|---|---|
| `q` | string | Must match `^[a-zA-Z0-9]+$` after slash-removal | Yes (via rewrite) |

**Responses:**

| Condition | Status | Response |
|---|---|---|
| Code found | 301 | `Location: <long_url>` header |
| Code not found | 404 | HTML `<h1>404 Not Found</h1>` + 512-space padding |
| Invalid code format | (silent) | No response — falls off end of `run()` |

**FastAPI route proposal:** `GET /{code}` with path parameter `code: str` validated against `^[a-zA-Z0-9]+$`.

### 5.4 R4 — Empty Request

- `GET /` with no parameters: `q` resolves to empty string → `not_found()` → 404.
- FastAPI equivalent: a separate handler for `GET /` returning 404 or a landing page.

---

## 6. Dependencies

### 6.1 PHP Built-ins and Extensions Used

| PHP Construct | Location | Purpose | Python / FastAPI Equivalent |
|---|---|---|---|
| `PDO` | `config.php:6`, `shorty.php:38,212,228,244,261` | Database connectivity with bound params | `sqlalchemy.ext.asyncio.AsyncSession` + `asyncpg` |
| `PDO::FETCH_ASSOC` | `shorty.php:217,231` | Rows as associative arrays | SQLAlchemy `Row` → `dict` or mapped model |
| `$pdo->prepare()` | `shorty.php:212,228,244,261` | Parameterised statements | `session.execute(select(...).where(...))` |
| `$stmt->execute()` | `shorty.php:215,230,247,263` | Statement execution with bound params | Handled by SQLAlchemy ORM/core |
| `$pdo->lastInsertId()` | `shorty.php:249` | Get auto-increment ID | `result.inserted_primary_key[0]` or `RETURNING id` |
| `header()` | `shorty.php:272,280,283,353,356` | Set HTTP response headers | FastAPI `Response` headers / `RedirectResponse` |
| `exit()` | Throughout | Terminate and send output | FastAPI `return` with appropriate `Response` |
| `preg_match()` | `shorty.php:332,379` | Regular expression matching | `re.match()` in Python |
| `urldecode()` | `shorty.php:318` | URL-decode the `url` parameter | Starlette auto-decodes (no explicit call needed) |
| `htmlentities()` | `shorty.php:358` | Escape HTML special chars for XML | `html.escape()` |
| `md5()` | `shorty.php:154` | Non-security hash for ID obfuscation seed | `hashlib.md5()` — preserved for URL stability |
| `hexdec()` | `shorty.php:155` | Convert hex string to decimal integer | `int(hex_string, 16)` |
| `str_pad()` | `shorty.php:158` | Left-pad number string to fixed width | `str(num).zfill(padding)` |
| `str_repeat()` | `shorty.php:283` | IE 512-byte padding | Obsolete — do not migrate |
| `json_encode()` | `shorty.php:353` | Serialize to JSON | `fastapi.responses.JSONResponse` |
| `pow()` | `shorty.php:156,199` | Exponentiation | `**` operator (exact int in Python) |
| `strtolower()` | `shorty.php:323` | Case-normalise format param | `str.lower()` |
| `strpos()` | `shorty.php:199` | Find character position in charset string | `str.index()` or precomputed dict |
| `substr()` | `shorty.php:142,155,158,179,183,199` | String slicing | Python slice notation `s[a:b]` |
| `strlen()` | `shorty.php:171,196` | String length | `len()` |
| `is_string()` | `shorty.php:74` | Type check | `isinstance(x, str)` |
| `empty()` | Throughout | Falsy check | `not x` in Python |
| `is_array()` | `shorty.php:302` | Type check for whitelist param | `isinstance(ip, list)` |
| `array_merge()` | `shorty.php:303` | Merge IP arrays | `list.extend()` or `+` |
| `array_push()` | `shorty.php:306` | Append to whitelist | `list.append()` |
| `in_array()` | `shorty.php:328` | IP whitelist check | `value in list` |
| `implode()` | `shorty.php:357` | Join array with newline | `"\n".join(...)` |
| `date()` | `shorty.php:242,259` | Current timestamp | `datetime.now(timezone.utc)` |
| `str_replace()` | `shorty.php:314` | Strip slashes from `q` param | `str.replace('/', '')` |
| `$_GET` | `shorty.php:314,317,321` | Query string input | FastAPI `Query(...)` parameters |
| `$_SERVER['REMOTE_ADDR']` | `shorty.php:328` | Client IP address | `request.client.host` |

### 6.2 External Dependencies

None. Shorty has zero external PHP library dependencies beyond PDO (a core PHP extension). The only `require` statements in `index.php` are project-internal files.

### 6.3 Web Server Rewrite Dependency

Shorty depends on an Apache `.htaccess` rewrite rule (or Nginx equivalent) to route path requests (`/abc`) to the index page as `?q=abc`. The FastAPI equivalent uses path routing natively; no external rewrite rule is needed.

---

## 7. Risk Flags

```
RF-01: TYPE-EXCEPTION — INT UNSIGNED overflow potential in PostgreSQL
  Severity: MED
  Location: database.sql:5 (id column), database.sql:9 (hits column)
  Issue:    MySQL INT UNSIGNED holds 0–4,294,967,295. PostgreSQL INTEGER is signed
            and holds -2,147,483,648 to 2,147,483,647. If a deployment has accumulated
            more than ~2.1 billion URLs, or if any single URL has >2.1 billion hits,
            migration will overflow.
  Fix:      Use BIGINT for `id` and `hits` in the PostgreSQL schema to be safe, or
            document the INTEGER decision with a monitoring alert threshold.
```

```
RF-02: ENCODE-STABILITY — MD5 algorithm must be preserved exactly for URL stability
  Severity: HIGH
  Location: shorty.php:154 (get_seed), shorty.php:122–131 (encode), shorty.php:139–143 (decode)
  Issue:    `get_seed()` uses MD5 as a deterministic hash to derive a numeric seed prefix.
            Migration rule 12 calls this out as a "preserve for stability" case. Any deviation
            (different string concat order, different hex nibble count, different zero-guard)
            will break every existing short URL.
  Fix:      Implement Python `get_seed(n, salt, padding)` using `hashlib.md5()` with identical
            logic. Write a round-trip test verifying Python encode(n) == PHP encode(n) for
            a known set of (n, salt, padding) triples.
```

```
RF-03: ENCODE-STABILITY — String concatenation `(int)($k.$n)` must use decimal string join
  Severity: HIGH
  Location: shorty.php:127
  Issue:    PHP concatenates string $k with string-of-int $n, then casts to int. Any
            implementation using arithmetic (e.g. k * 10^len(n) + n) could produce same
            result for most cases but documenting string-join is safer.
  Fix:      Always implement as `new_n = int(k + str(n))` in Python. Add an explicit comment
            referencing this line. Test with padding=2, n=5, k="07".
```

```
RF-04: INPUT-VALIDATION — URL regex is overly permissive
  Severity: MED
  Location: shorty.php:332
  Issue:    `preg_match('/^http[s]?\:\/\/[\w]+/', $url)` only validates the scheme and first
            hostname segment. Malformed URLs like `http://valid<script>XSS</script>` would
            pass the check. The URL is later output in HTML, XML, and JSON responses.
  Fix:      Use Python's `urllib.parse.urlparse()` or `pydantic.AnyHttpUrl`. HTML-escape the
            URL in the href attribute.
```

```
RF-05: SECURITY — IP whitelist ignores X-Forwarded-For / reverse proxy headers
  Severity: HIGH (in reverse-proxy deployments)
  Location: shorty.php:328
  Issue:    `$_SERVER['REMOTE_ADDR']` returns the direct TCP connection IP. Behind an Nginx
            or AWS ALB reverse proxy, this will always be the proxy IP, not the real client IP.
  Fix:      Use `ProxyHeadersMiddleware` from `uvicorn.middleware.proxy_headers` or configure
            `trusted_hosts`. Use `request.client.host` only after middleware has resolved the
            real IP from `X-Forwarded-For`. Document which header is trusted.
```

```
RF-06: REDIRECT-OPEN — redirect URL is sourced directly from the database without re-validation
  Severity: MED
  Location: shorty.php:387 (redirect call), shorty.php:272 (redirect method)
  Issue:    The URL fetched from the database is passed directly to `header("Location: $url")`.
            Since `store()` only inserts URLs passing the `^http[s]?://\w+` check at write
            time, this is a second-order concern. Direct DB injection bypassing the API could
            insert malicious URLs.
  Fix:      In the FastAPI target, re-validate the URL scheme before issuing RedirectResponse.
            Reject any URL not starting with `http://` or `https://`.
```

```
RF-07: CONCURRENCY — race condition on duplicate URL insertion
  Severity: MED
  Location: shorty.php:334–340
  Issue:    The find-then-store pattern has a TOCTOU race. Two concurrent requests for the
            same new URL can both pass `find()`, then both attempt `store()`. The second
            insert violates the UNIQUE constraint and throws an uncaught PDOException.
  Fix:      Use `INSERT INTO urls (url, created) VALUES (:url, :created) ON CONFLICT (url)
            DO NOTHING RETURNING id`. If no row returned, SELECT to get the existing ID.
            Atomic; eliminates the race.
```

```
RF-08: SILENT-IGNORE — invalid short code format produces no response
  Severity: LOW
  Location: shorty.php:379–393
  Issue:    If `$q` is non-empty but does not match `/^[a-zA-Z0-9]+$/`, the `preg_match`
            fails and `run()` returns without any response (no 404). Likely results in empty
            200 response.
  Fix:      FastAPI route `GET /{code}` with `str` path parameter naturally 404s if no route
            matches. Add explicit validation with a 404 response for invalid characters.
```

```
RF-09: HTTP-STATUS — error responses use HTTP 200 with HTML body
  Severity: LOW
  Location: shorty.php:292–294 (error method), shorty.php:329 (not allowed), shorty.php:369 (bad input)
  Issue:    `$this->error()` calls `exit("<h1>$message</h1>")` without setting an HTTP status
            code. PHP defaults to 200. So "Bad input." and "Not allowed." return HTTP 200,
            invisible to API clients checking status codes.
  Fix:      FastAPI target should return HTTP 400 for "Bad input.", HTTP 403 for "Not allowed.",
            HTTP 422 for validation failures. JSON error responses consistent with FastAPI defaults.
```

```
RF-10: CONTENT-TYPE — text/plain format does not set Content-Type header
  Severity: LOW
  Location: shorty.php:349
  Issue:    `case 'text': exit($url)` — no Content-Type header is set. PHP defaults to
            `text/html; charset=UTF-8`. A client expecting `text/plain` may receive wrong MIME.
  Fix:      FastAPI: `return Response(content=url, media_type="text/plain")`.
```

```
RF-11: TIMEZONE — created/accessed timestamps use local server time without timezone info
  Severity: MED
  Location: shorty.php:242, shorty.php:259
  Issue:    `date('Y-m-d H:i:s')` returns local time with no timezone offset. MySQL DATETIME
            stores no timezone info. If the server is not UTC, stored times are in an
            unknown local timezone.
  Fix:      PostgreSQL target uses TIMESTAMPTZ. The FastAPI application should always pass
            `datetime.now(timezone.utc)`. Existing data migration requires timezone
            normalisation if the source MySQL server was not UTC.
```

```
RF-12: PADDING-DEFAULT — config.php default padding=3 but shorty.php class default padding=1
  Severity: LOW (config clarification)
  Location: config.php:30 (padding=3), shorty.php:26 (private $padding = 1)
  Issue:    Class default is 1; runtime value (from index.php → config.php) is always 3.
            Reading shorty.php in isolation is misleading.
  Fix:      Document the config-always-wins pattern. Python target should define padding as
            a required config value (Pydantic `Settings`) with no implicit default in the
            encoder class, or explicitly default to 3 in the Settings model.
```

---

## 8. Open Questions

```
OQ-01: Salt preservation across migration
  Source:   shorty.php:21, config.php:26
  Question: The production value of `$salt` is unknown from the source files (config.php
            ships with $salt=''). If a production deployment has a non-empty salt, ALL
            existing short URLs depend on that salt value for decode correctness.
  Impact:   HIGH — wrong salt means all existing short URLs return 404 after migration.
```

```
OQ-02: Production padding value and chars string
  Source:   config.php:30 (padding=3), config.php:9–21 (chars options)
  Question: The production deployment may be using one of the five pre-shuffled $chars
            strings rather than the default. Which chars and padding values are in production?
  Impact:   HIGH — wrong chars or padding means all existing short URLs break.
```

```
OQ-03: Should the `hits` counter use BIGINT in PostgreSQL?
  Source:   database.sql:9
  Question: MySQL INT UNSIGNED supports up to ~4.3 billion hits per URL. PostgreSQL INTEGER
            only ~2.1 billion. Regression for heavily-trafficked installations.
  Impact:   LOW for typical deployments.
```

```
OQ-04: Should `url` column use TEXT or VARCHAR(2048)?
  Source:   database.sql:6
  Question: MySQL VARCHAR(1000) vs RFC 7230 practical max ~2048 vs unbounded TEXT.
  Impact:   LOW — TEXT is the safe default.
```

```
OQ-05: URL validation regex — should it be strengthened?
  Source:   shorty.php:332
  Question: Should the target use a stricter validator (pydantic AnyHttpUrl)? Doing so might
            reject URLs the legacy accepted.
  Impact:   MED — changing validation tightens the contract.
```

```
OQ-06: Hit counter update failure — block or ignore?
  Source:   shorty.php:385–387
  Question: PHP redirects even if the UPDATE fails. Should FastAPI block or fire-and-forget?
  Impact:   LOW — analytics vs availability tradeoff.
```

```
OQ-07: Should the FastAPI target preserve `?url=` GET interface or use RESTful POST?
  Source:   shorty.php:313–370, README.md:32–34
  Question: GET-with-side-effects is non-idiomatic. POST /shorten with JSON body is cleaner
            but breaks existing API consumers.
  Impact:   MED — architectural decision with API compatibility implications.
```

```
OQ-08: Whitelist configuration — environment variable or database-backed?
  Source:   shorty.php:44–46, index.php:10
  Question: Legacy is code-configured. FastAPI should read from env var or config file.
            Should it also support database-backed dynamic whitelist?
  Impact:   LOW for Phase 1; defer dynamic whitelist.
```

```
OQ-09: Does the production deployment have existing URL data requiring migration?
  Source:   database.sql:4–12, shorty.php:241–249
  Question: Greenfield or existing data?
  Impact:   HIGH if existing data — determines whether a data migration script is needed.
```

```
OQ-10: Should 301 (permanent) redirects be preserved, or changed to 302 (temporary)?
  Source:   shorty.php:272
  Question: 301 caches permanently in browsers. If URLs ever need to change or be deleted,
            browser caches won't respect the change. Configurable type?
  Impact:   LOW for a simple migrator; MED if URL management is in scope.
```

---

## 9. Recommended Next Step

The Comprehension Agent should focus on three areas:

1. **The `encode`/`decode`/`get_seed` round-trip invariant.** This is the single load-bearing business rule. Formally document the mathematical guarantee: given fixed (salt, padding, chars), `decode(encode(n)) == n` for all positive integers `n`. Specify exactly what each configuration change implies for URL stability.

2. **The (salt, padding, chars) production configuration.** OQ-01 and OQ-02 are blockers for Planning. Before any code is generated, the production values must be known. If they cannot be determined from source artefacts, Comprehension should flag this as a HITL requirement.

3. **API contract clarification (OQ-07).** The decision between preserving the `GET /?url=` interface and adopting RESTful `POST /shorten` affects every downstream code generation step. Resolve at Comprehension stage so Planning can lock the API contract.
