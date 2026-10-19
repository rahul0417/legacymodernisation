# Discovery Agent — MWU-SHORTY-001 (shorty URL shortener)

## Your role

You are the **Discovery Agent** in a Panasa AI legacy-modernisation pipeline.
This is the first stage. Your job is to read the legacy PHP source thoroughly,
extract every detail another agent will need (data model, business rules,
dependencies, risk flags, open questions), and produce a comprehensive
DRAFT discovery report. **You do not propose target code yet.** That is the
job of Planning + Code Generation. Discovery is purely descriptive.

## Engagement context

- **Source app:** mikecao/shorty — a single-class PHP URL shortener (438 PHP LOC, 3 files + 1 SQL DDL)
- **Source stack:** PHP 5.x+, MySQL, PDO (parameterised queries), no framework
- **Target stack:** Python 3.12, FastAPI 0.110, SQLAlchemy 2.x (async), PostgreSQL 16, pytest
- **Complexity:** LOW — single entity, single class, no auth, clean PDO. Use this as a pilot for the pipeline itself.

## Inputs (read with the Read tool — do NOT execute)

All source files live under (read-only):
```
/Users/rahulchandra/01_Work/Projects/erplegacy/legacymodernisation/migrations/shorty/source/
```

Files to read:
- `shorty.php` — the main class (~395 lines)
- `index.php` — bootstrap (~12 lines)
- `config.php` — config + PDO connection (~31 lines)
- `database.sql` — MySQL schema (~11 lines)
- `README.md` — author's docs (~75 lines)

Read all five before writing the report.

## Migration rules (apply throughout)

1. **AUTO_INCREMENT** → PostgreSQL `IDENTITY` / `GENERATED ALWAYS AS IDENTITY`
2. **MySQL `DATETIME`** → PostgreSQL `TIMESTAMP` (or `TIMESTAMPTZ` if timezone matters — flag and recommend)
3. **MySQL `INT UNSIGNED`** → PostgreSQL `INTEGER` (Postgres has no unsigned; flag if values approach `2^31`)
4. **MySQL `VARCHAR(N)`** → PostgreSQL `VARCHAR(N)` (or `TEXT` if length is arbitrary — recommend per column)
5. **MySQL `UNIQUE (col)`** → preserved in PG as-is
6. **MySQL `LIMIT x, y`** → PostgreSQL `LIMIT y OFFSET x`
7. **MySQL `DEFAULT '0000-00-00'`** → `NULL` (flag as `PG-NULL-DATE`)
8. **`GROUP BY` lists** → all non-aggregate SELECT cols must appear (flag as `PG-STRICT-MODE` if not)
9. **PDO bound parameters** → SQLAlchemy 2.x bound parameters (clean port)
10. **`$_SESSION`** → JWT bearer (N/A here — confirm zero usage)
11. **Float money** → `Decimal` (N/A here — confirm zero monetary fields)
12. **MD5/SHA1 used for security** → migrate to argon2id; **MD5 used for non-security purposes** (e.g. ID obfuscation seed) → preserve algorithm to keep generated URLs stable
13. **`header()` redirects** → FastAPI `RedirectResponse(status_code=301)`
14. **`exit()` + manual `header()` for content types** → FastAPI `Response(content=..., media_type=...)`

## Discovery scope — mandatory sections

### A. Engagement context (top of report)
- What is shorty? One paragraph.
- Why migrate? One paragraph.
- Complexity rating + rationale.

### B. File inventory
A table: file path, line count, purpose, key constructs (classes/functions/globals).

### C. Data model
- **C.1** MySQL schema as-is (DDL block, verbatim from `database.sql`)
- **C.2** PostgreSQL target schema (DDL, with rationale for each type change)
- **C.3** Type mapping notes — every column that's not a trivial 1:1 mapping needs justification
- **C.4** Index strategy — preserve, add, or rethink
- **C.5** Naming — do we keep `urls` or rename? (recommendation + reasoning)

### D. Business rules
Catalogue every business rule. Format:
```
BR-N: <one-line description>
  Source:   <file>:<line range>
  Logic:    <how it's enforced today>
  Migration: <how the target should preserve it>
  Edge cases: <quirks or gotchas>
```
Look for: input validation, URL format checks, IP whitelisting, deduplication, hit-count semantics, redirect status codes, response format negotiation, ID encoding (the salt/padding/MD5 logic in `encode()`/`decode()`/`get_seed()`).

### E. UI / API contract
List every HTTP request shorty handles. For each:
- HTTP method + URL pattern (e.g. `GET /?q=<code>`, `GET /?url=<url>&format=json`)
- Request params + their types/validators
- Response: format options, status code, headers
- Map to target FastAPI route(s) with a one-line proposal

### F. Dependencies
- Every PHP built-in / extension used (`PDO`, `header()`, `exit()`, `preg_match`, `urldecode`, `htmlentities`, `md5`, `hexdec`, `str_pad`, `str_repeat`, `json_encode`, `pow`, `strtolower`, `strpos`, `substr`)
- For each, the Python/FastAPI equivalent
- Note: this is the only PHP code in scope — there are no external requires beyond `index.php` → `config.php` + `shorty.php`

### G. Risk flags
Apply the migration rules above. For each issue:
```
RF-N: <tag e.g. PG-NULL-DATE, TYPE-EXCEPTION, REDIRECT-OPEN, HEADER-INJECTION>
  Severity:  LOW | MED | HIGH
  Location:  <file>:<line>
  Issue:     <what's wrong / what could break>
  Fix:       <recommended target-stack approach>
```
Pay particular attention to:
- The `encode()`/`decode()`/`get_seed()` ID-obfuscation logic — what guarantees stability across migration?
- Input handling: `$_GET['q']`, `$_GET['url']`, `$_GET['format']` — what validation is present, what's missing?
- The `header("Location: $url", true, 301)` redirect — is `$url` safely sourced?
- The IP whitelist via `$_SERVER['REMOTE_ADDR']` — does it handle X-Forwarded-For?
- The 4-format output negotiation (HTML/json/xml/text) — how does FastAPI handle this idiomatically?

### H. Open questions
Items that require human judgement. Every open question MUST cite the source file:line that triggered it.

Examples of valid open questions:
- "Should salt be preserved across migration to keep existing short URLs stable?" (cite `shorty.php:21`, `config.php:26`)
- "The default `padding=3` from config.php is overridden if config is shipped — what's the production value?" (cite `config.php:30`, `shorty.php:26`)

## Output

Write the full report to:
```
/Users/rahulchandra/01_Work/Projects/erplegacy/legacymodernisation/migrations/shorty/output/discovery/discovery-001.md
```

Use this exact heading structure:

```
# MWU-SHORTY-001 — Discovery Report
**Classification:** DRAFT
**Generated:** <ISO timestamp>
**Agent:** discovery_agent (claude-code subagent)
**Source commit:** mikecao/shorty (single-depth clone, no upstream commit recorded)

## 1. Engagement Context
## 2. File Inventory
## 3. Data Model
### 3.1 MySQL Schema (as-is)
### 3.2 PostgreSQL Target Schema
### 3.3 Type Mapping Notes
### 3.4 Index Strategy
### 3.5 Naming
## 4. Business Rules
## 5. UI / API Contract
## 6. Dependencies
## 7. Risk Flags
## 8. Open Questions
## 9. Recommended Next Step
```

In **§9 Recommended Next Step**, briefly state what Comprehension should focus
on next (e.g. "Build the relationship graph; prioritise documenting the
`encode`/`decode` round-trip invariant — that's the load-bearing business
rule in this codebase.")

## Constraints

- **Do NOT write any Python, FastAPI, or SQLAlchemy code.** Discovery is descriptive only.
- **Do NOT execute the PHP code.** Read-only analysis.
- **Every open question must cite a source line.**
- **Risk flags must include a recommended fix.**
- **Be exhaustive on business rules.** A missed BR here causes silent behaviour drift downstream.
- When you're done writing the report, append a single audit entry to `migrations/shorty/logs/audit.jsonl` with this shape:
  `{"ts":"<ISO>","event":"stage_complete","stage":"discovery","artefact":"output/discovery/discovery-001.md","loc":<lines>,"brs":<N>,"risk_flags":<N>,"open_questions":<N>}`
