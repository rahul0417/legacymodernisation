# MWU-CRUD-001 — Comprehension Report
**Classification:** APPROVED-CANDIDATE (awaits Gate 2)
**Generated:** 2026-05-14T22:15:00Z
**Agent:** comprehension_agent (Opus)
**Upstream:** discovery-001.md (483 LOC, 12 BRs + 5 BR-M, 8 RFs) + gate-1.md (OQ-001..OQ-005 LOCKED)

---

## 1. Engagement Summary

PNS-CRUD-001 migrates `chapagain/crud-php-simple` — a 222-LOC educational PHP CRUD over a single
`users(id, name, age, email)` table — to a Python 3.12 + FastAPI 0.110 + SQLAlchemy 2.x async +
PostgreSQL 16 backend **and** a React 18 + TypeScript + shadcn/ui + Tailwind + Vite single-page
frontend. The legacy app spans four full-page screens (list, add, edit, delete-confirm) rendered
with `<table border=0 bgcolor='#DDDDDD'>`-era HTML, a JavaScript `confirm()` delete gate, and inline
`<font color='red'>` validation feedback; it carries two confirmed CRITICAL SQL-injection vectors
(`edit.php`, `delete.php`), stored-XSS exposure on every list row, no CSRF protection, and a delete
side-effect bound to an HTTP GET. The business-rule footprint is intentionally tiny: 12 enforced
rules (mostly empty-field checks plus `ORDER BY id DESC`) and 5 absent-but-needed rules (email
format + uniqueness, age range, name length, REST-verb hygiene). This Comprehension stage
consolidates those 17 rule fragments into **11 testable BR-C statements** spanning four bounded
contexts (UserCreation, UserUpdate, UserListing, UserDeletion), locks the **five FastAPI endpoint
contracts** with full Pydantic schemas and an RFC-9457 error envelope, and — most importantly —
**locks the React component tree** plus its state-management decision (single `useState` cluster
in `UsersPage`, justified in §5.2). Because Gate 1 has already resolved all five legacy OQs (email
UNIQUE=yes, age 0–150, table=`users`, no pagination, no auth), Comprehension introduces only one
new residual OQ (timezone of any future `updated_at` audit column, deferred). The visual
transformation is the demo's load-bearing artefact; §5 therefore receives the largest share of
detail in this report so that Planning can derive the React file tree and CodeGen can implement
both halves byte-for-byte from this spec.

---

## 2. Bounded Contexts

The 11 consolidated rules group cleanly into four bounded contexts. Each context owns one
write path (or one read path) plus its validation invariants. The boundaries below intentionally
keep **UserCreation** and **UserUpdate** distinct rather than merging them into a single
"UserMutation" — they share schema but diverge on (a) identifier (Create=none, Update=path `id`),
(b) HTTP verb (POST vs PUT), (c) success status (201 vs 200), and (d) error surface (Create can
return 409 on duplicate email; Update can return 404 + 409). Merging would force every test
assertion to branch internally.

| Context | Purpose | Primary endpoint(s) | Owns BR-Cs |
|---|---|---|---|
| **UserListing** | Provide the default newest-first roster that powers the SPA's DataTable + the legacy `index.php` parity reference. | `GET /api/users` | BR-C-01, BR-C-02 |
| **UserCreation** | Add a new user record honouring all required-field, type-range, format, and uniqueness invariants. | `POST /api/users` | BR-C-03, BR-C-04, BR-C-05, BR-C-06, BR-C-11 |
| **UserUpdate** | Mutate an existing user's three editable columns while preserving the surrogate `id` and re-running every Create invariant. | `GET /api/users/{id}` (read for pre-fill) + `PUT /api/users/{id}` | BR-C-03, BR-C-04, BR-C-05, BR-C-06, BR-C-07, BR-C-11 |
| **UserDeletion** | Hard-delete a single user behind an explicit DELETE verb plus a UI confirmation gate; no soft-delete. | `DELETE /api/users/{id}` | BR-C-08, BR-C-09, BR-C-10 |

Notes on the slicing:

1. **UserListing** is read-only and stateless; it owns the ordering contract (`ORDER BY id DESC`)
   that legacy `index.php` enforces at the SQL layer. The DataTable's default sort must match this
   exactly so dual-run visual parity passes without sort-toggling.
2. **UserCreation** owns the *first* surface where email uniqueness becomes observable; on conflict
   it must emit `409 Conflict` rather than letting the underlying `IntegrityError` bubble.
3. **UserUpdate** is the only context that consumes *two* endpoints (read-then-write); the React
   `AddEditDialog(mode="edit")` opens with a `GET /api/users/{id}` to fill the form, then submits
   via `PUT`. The read is idempotent and side-effect-free.
4. **UserDeletion** is split out because it is the only mutating operation in legacy that is
   triggered by an HTTP GET — fixing this REST-verb hygiene is one of the highest-visibility
   modernisation deltas. The context owns BR-C-09 (DELETE verb mandatory) and BR-C-10 (UI
   confirmation gate preserved).

A cross-context invariant — BR-C-11 (Pydantic validation precedes DB write) — is listed under both
mutation contexts because acceptance tests for each must independently assert the 422 envelope.

---

## 3. Consolidated Business Rules

Each BR-C carries: title, owning context, statement, acceptance criteria (testable in HTTP +
React terms), edge cases, and traceability to Discovery BR-N and source `file:line`.

---

### BR-C-01 — Newest-first ordering on list
**Context:** UserListing
**Statement:** `GET /api/users` returns users sorted strictly descending by `id` (insertion-time
proxy). No pagination. No filter parameters. No alternate sort accepted in MVP.
**Acceptance:**
- AC-01a: After seeding rows in insertion order [A, B, C], `GET /api/users` returns array
  `[C, B, A]` — IDs strictly monotonically decreasing.
- AC-01b: Response is `200 OK` with `Content-Type: application/json` even on empty roster.
- AC-01c: Response body shape is `List[UserRead]`; never wrapped in `{"data": [...]}`.
- AC-01d: React `UsersDataTable` initial render shows the same first-row IDs as `index.php` would,
  given the same DB state.
**Edge cases:** empty table → `[]` not `null`; single row → array of length 1.
**Traceability:** Discovery BR-007 · `index.php:6` (`ORDER BY id DESC`).

---

### BR-C-02 — List read is side-effect-free
**Context:** UserListing
**Statement:** Listing is idempotent; no row is created, updated, or deleted as part of `GET`.
No `last_seen_at`-style mutation. Multiple concurrent listings see the same rowset modulo
external writes.
**Acceptance:**
- AC-02a: `GET /api/users` followed by `SELECT count(*) FROM users` returns the same count as
  before the request.
- AC-02b: No `UPDATE` or `INSERT` statements appear in the SQLAlchemy session log for this
  request path.
**Edge cases:** none.
**Traceability:** Implicit in `index.php:6` (pure SELECT). Explicit reinforcement vs. RF-007
(no GET-triggered mutations anywhere in target).

---

### BR-C-03 — All three editable fields are mandatory and non-blank
**Context:** UserCreation, UserUpdate
**Statement:** `name`, `age`, and `email` are required on both create and update. A value is
considered absent if missing from the payload, JSON `null`, or — for `name`/`email` — an empty
or whitespace-only string. `age` cannot be missing or null.
**Acceptance:**
- AC-03a: `POST /api/users` body `{}` → `422` with three field errors (`name`, `age`, `email`).
- AC-03b: `POST /api/users` body `{"name": "", "age": 30, "email": "a@b.c"}` → `422` with one
  field error on `name`.
- AC-03c: `POST /api/users` body `{"name": "   ", "age": 30, "email": "a@b.c"}` → `422`
  (whitespace-only treated as empty; Pydantic `StringConstraints(strip_whitespace=True,
  min_length=1)` or equivalent validator).
- AC-03d: `PUT /api/users/{id}` body `{"name": "X", "age": null, "email": "a@b.c"}` → `422`.
- AC-03e: React form's Save/Update button stays disabled until all three fields are non-empty
  (Zod `z.string().min(1)`), preserving the legacy `<font color='red'>` per-field feedback as
  inline error text under each input.
**Edge cases:** name containing only emoji is *not* empty; trailing whitespace stripped before
length check; `age = 0` is **valid** (see BR-C-04 — zero is in range).
**Traceability:** Discovery BR-001..BR-006 · `addAction.php:18-31`, `editAction.php:13-25`.

---

### BR-C-04 — Age must be an integer in [0, 150]
**Context:** UserCreation, UserUpdate
**Statement:** `age` is a Python `int` (SMALLINT on PG) constrained to `0 ≤ age ≤ 150`. Floats,
strings, and out-of-range integers are rejected at the Pydantic boundary before the DB write.
**Acceptance:**
- AC-04a: `POST /api/users` with `"age": -1` → `422` (`ge=0` violation).
- AC-04b: `POST /api/users` with `"age": 151` → `422` (`le=150` violation).
- AC-04c: `POST /api/users` with `"age": 0` → `201` (zero is valid — newborn).
- AC-04d: `POST /api/users` with `"age": 150` → `201` (boundary inclusive).
- AC-04e: `POST /api/users` with `"age": "thirty"` → `422` (type coercion fails).
- AC-04f: `POST /api/users` with `"age": 30.5` → `422` (Pydantic strict int; floats rejected).
- AC-04g: React form's `<Input type="number" min={0} max={150} step={1}>` blocks non-integer
  input client-side; submission still re-validates server-side.
**Edge cases:** `"age": "30"` (numeric string) — Pydantic v2 default coerces; acceptable.
**Traceability:** Discovery BR-011 + BR-M02 · OQ-002 Gate-1 LOCKED · `database.sql:8`.

---

### BR-C-05 — Email must match RFC-5322-lite format and fit `VARCHAR(100)`
**Context:** UserCreation, UserUpdate
**Statement:** `email` is validated by Pydantic `EmailStr` (which delegates to
`email-validator`'s RFC-5322-lite rules) and must additionally not exceed 100 characters to fit
the DB column.
**Acceptance:**
- AC-05a: `POST /api/users` with `"email": "not-an-email"` → `422`.
- AC-05b: `POST /api/users` with `"email": "a@b"` → `422` (no TLD).
- AC-05c: `POST /api/users` with `"email": "valid@example.com"` → `201`.
- AC-05d: `POST /api/users` with a 105-char syntactically valid email → `422` (`max_length=100`).
- AC-05e: React form `<Input type="email">` triggers native browser validation; Zod schema
  mirrors with `z.string().email().max(100)`.
**Edge cases:** internationalised email addresses (Unicode local-part) — accepted by
`EmailStr` and stored as-is; capital letters in domain part allowed but not normalised in MVP.
**Traceability:** Discovery BR-M01 + BR-M04 · `database.sql:9` (varchar(100)).

---

### BR-C-06 — Name length bounded by `VARCHAR(100)`
**Context:** UserCreation, UserUpdate
**Statement:** `name` is `1 ≤ len(name) ≤ 100` after whitespace stripping. Length is enforced at
the Pydantic boundary so the DB never sees an over-length payload.
**Acceptance:**
- AC-06a: 100-char name → `201`.
- AC-06b: 101-char name → `422`.
- AC-06c: Form's `<Input maxLength={100}>` hard-stops typing client-side.
**Edge cases:** multibyte characters count as 1 grapheme each in Pydantic (string length, not
byte length).
**Traceability:** Discovery BR-M04 · `database.sql:7`.

---

### BR-C-07 — Update preserves `id`; missing user yields 404
**Context:** UserUpdate
**Statement:** `PUT /api/users/{id}` mutates only `name`, `age`, `email`. The path `id` is the
canonical identifier; if the row does not exist, the response is `404` with an RFC-9457 envelope.
The request body must **not** contain an `id` field; if present, it is ignored (not echoed back
in the error envelope).
**Acceptance:**
- AC-07a: `PUT /api/users/99999` (no such row) → `404` with `{"type":"about:blank","title":
  "Not Found","status":404,"detail":"User 99999 not found"}`.
- AC-07b: Successful update → `200` with `UserRead` reflecting **path-id** (not any body-id).
- AC-07c: SQLAlchemy `UPDATE` statement targets exactly `WHERE id = :id`; no `id` column appears
  in the SET clause.
- AC-07d: React `AddEditDialog(mode="edit")` opens by fetching `GET /api/users/{id}`; if that
  returns 404, the dialog closes and a toast informs the user the row no longer exists.
**Edge cases:** concurrent delete-then-update race → 404 returned to the loser; no 500.
**Traceability:** Discovery BR-009 · `editAction.php:27`.

---

### BR-C-08 — Delete is permanent; no soft-delete
**Context:** UserDeletion
**Statement:** `DELETE /api/users/{id}` issues a SQL `DELETE` and removes the row. There is no
`deleted_at` column, no archive table, no audit. Subsequent reads return 404.
**Acceptance:**
- AC-08a: After successful `DELETE /api/users/{id}`, `GET /api/users/{id}` → `404`.
- AC-08b: After successful `DELETE /api/users/{id}`, the row no longer appears in
  `GET /api/users`.
- AC-08c: Successful delete → `204 No Content`; response body empty.
**Edge cases:** delete on non-existent id → `404` (BR-C-07-style envelope), not 204.
**Traceability:** Discovery BR-008 · `delete.php:9`.

---

### BR-C-09 — Delete only via HTTP DELETE verb
**Context:** UserDeletion
**Statement:** No GET endpoint exists that performs deletion. The DELETE verb is the **only**
side-effecting path for removal. This rule directly fixes legacy RF-002 + RF-007.
**Acceptance:**
- AC-09a: `GET /api/users/{id}/delete` → `404` (no such route).
- AC-09b: `GET /api/users/{id}` returns `UserRead` with **no** mutation occurring (assert row
  count unchanged in DB before/after).
- AC-09c: OpenAPI schema lists no DELETE-style operation under a `GET` method.
- AC-09d: React's `DeleteAlertDialog` confirmation button issues
  `fetch(url, { method: 'DELETE' })`; never a navigation or `window.location` assignment.
**Edge cases:** browser link-prefetch or search-engine crawl of any URL does not mutate state
(regression vs. legacy where `<img src="delete.php?id=1">` was sufficient).
**Traceability:** Discovery RF-002 + RF-007 + BR-M05 · `delete.php:6`.

---

### BR-C-10 — UI delete gate preserved (two-step confirmation)
**Context:** UserDeletion
**Statement:** The React UI must require an **explicit second action** to confirm deletion. A
single click on the row's Delete button never deletes; it opens a shadcn `AlertDialog` requiring
a confirmatory click. Pressing ESC, clicking outside the dialog, or clicking Cancel aborts with
no API call.
**Acceptance:**
- AC-10a: Clicking Delete on a row → AlertDialog appears; no `DELETE` request fires (verify via
  network panel / MSW handler).
- AC-10b: Clicking the dialog's "Delete" confirm button → exactly one `DELETE /api/users/{id}`
  request; on `204`, dialog closes and success toast appears.
- AC-10c: Pressing ESC while dialog is open → dialog closes; no request fired.
- AC-10d: Clicking outside the dialog (overlay) → dialog closes; no request fired.
- AC-10e: Dialog title is "Delete user?"; body text contains "This cannot be undone."
- AC-10f: Confirm button uses destructive variant (red); Cancel uses outline/neutral variant.
**Edge cases:** rapid double-click on Delete → only one `DELETE` request (button disabled after
first click until response resolves).
**Traceability:** Discovery BR-012 · `index.php:34` (`onClick=confirm(...)`).

---

### BR-C-11 — Email uniqueness enforced at DB + API
**Context:** UserCreation, UserUpdate
**Statement:** `email` is globally unique across the `users` table. Violations surface as a
deterministic `409 Conflict` with an RFC-9457 envelope, not a 500. The UNIQUE constraint is
defined at the DB layer (canonical truth) and additionally checked optimistically in the API
layer if a duplicate is detected before the INSERT/UPDATE (optional pre-check; the constraint is
the source of truth).
**Acceptance:**
- AC-11a: `POST /api/users` with an email that already exists in the table → `409` with
  `{"type":"about:blank","title":"Email already exists","status":409,"detail":"Email '<x>' is
  already registered.","instance":"/api/users"}`.
- AC-11b: `PUT /api/users/{id}` with another user's email → `409`.
- AC-11c: `PUT /api/users/{id}` with the **same** user's existing email (no change) → `200`
  (self-collision not a conflict).
- AC-11d: DB-layer `IntegrityError` on the UNIQUE index is caught and translated; no `500`
  leaks to the client.
- AC-11e: Alembic migration emits `UNIQUE` constraint named `uq_users_email` on `users.email`.
**Edge cases:** case-folding — MVP treats `Alice@x.com` and `alice@x.com` as distinct (no
`citext`). Lowercasing is **not** auto-applied in MVP; this is documented as a deferred
hardening.
**Traceability:** Discovery BR-M03 · OQ-001 Gate-1 LOCKED.

---

### Coverage matrix — Discovery BRs → BR-C

| Discovery BR | Rule | Consolidated into |
|---|---|---|
| BR-001 | name not empty (create) | BR-C-03 |
| BR-002 | age not empty (create) | BR-C-03 + BR-C-04 |
| BR-003 | email not empty (create) | BR-C-03 |
| BR-004 | name not empty (update) | BR-C-03 |
| BR-005 | age not empty (update) | BR-C-03 + BR-C-04 |
| BR-006 | email not empty (update) | BR-C-03 |
| BR-007 | order by id DESC | BR-C-01 |
| BR-008 | delete permanent | BR-C-08 |
| BR-009 | id surrogate PK | BR-C-07 |
| BR-010 | all fields NOT NULL | BR-C-03 |
| BR-011 | age integer | BR-C-04 |
| BR-012 | delete confirmation | BR-C-10 |
| BR-M01 | email valid format | BR-C-05 |
| BR-M02 | age in 0–150 | BR-C-04 |
| BR-M03 | email unique | BR-C-11 |
| BR-M04 | name ≤ 100 chars | BR-C-06 |
| BR-M05 | no GET-triggered delete | BR-C-09 |

17 fragments → 11 consolidated rules. UserListing has 2 (BR-C-01, 02). UserCreation has 5
(BR-C-03, 04, 05, 06, 11). UserUpdate has 6 (BR-C-03, 04, 05, 06, 07, 11). UserDeletion has 3
(BR-C-08, 09, 10).

---

## 4. API Contract (final)

### 4.1 Routes (5 endpoints — locked)

| # | Method | Path | Request body | Success | Owning context | Legacy parity |
|---|---|---|---|---|---|---|
| 1 | `GET` | `/api/users` | — | `200 OK` → `List[UserRead]` (id DESC) | UserListing | `index.php` |
| 2 | `POST` | `/api/users` | `UserCreate` | `201 Created` → `UserRead` + `Location: /api/users/{id}` | UserCreation | `addAction.php` |
| 3 | `GET` | `/api/users/{id}` | — | `200 OK` → `UserRead` | UserUpdate (read) | `edit.php` (SELECT) |
| 4 | `PUT` | `/api/users/{id}` | `UserUpdate` | `200 OK` → `UserRead` | UserUpdate | `editAction.php` |
| 5 | `DELETE` | `/api/users/{id}` | — | `204 No Content` | UserDeletion | `delete.php` |

Notes:
- **No PATCH** — MVP only supports full-record replacement via PUT (legacy `editAction.php`
  rewrites all three columns; semantics preserved).
- **No bulk endpoints** — MVP has no `POST /api/users/bulk`, no `DELETE /api/users?ids=...`.
- **No pagination params** — OQ-004 Gate-1 deferred to Phase 5; route does not advertise
  `?limit`/`?offset`/`?cursor`.
- **No filtering / search** — out of scope.
- **OpenAPI** is auto-emitted by FastAPI at `/api/docs` (Swagger UI) and `/api/openapi.json`.
- **Route prefix** is `/api` consistently; the React app's Vite dev server proxies `/api/*`
  to `http://localhost:8000`.

### 4.2 Pydantic schemas (sketch — Stage 4 will codify)

```python
# Sketch only — Stage 4 owns the actual code.
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class UserBase(BaseModel):
    name:  str       = Field(..., min_length=1, max_length=100,
                             description="Display name; whitespace stripped.")
    age:   int       = Field(..., ge=0, le=150,
                             description="Age in whole years.")
    email: EmailStr  = Field(..., max_length=100,
                             description="RFC-5322-lite; globally unique.")

    model_config = ConfigDict(str_strip_whitespace=True)

class UserCreate(UserBase):
    """Request body for POST /api/users. No id."""
    pass

class UserUpdate(UserBase):
    """Request body for PUT /api/users/{id}. id comes from path, not body."""
    pass

class UserRead(UserBase):
    """Response body. id always present; assigned by DB."""
    id: int
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

class ProblemDetail(BaseModel):
    """RFC 9457 application/problem+json — used for all error responses."""
    type:     str       = "about:blank"
    title:    str
    status:   int
    detail:   str | None = None
    instance: str | None = None
    # Optional field for 422: per-field error list
    errors:   list[dict] | None = None
```

Notes:
- `model_config = ConfigDict(str_strip_whitespace=True)` ensures BR-C-03 "whitespace-only is
  empty" is enforced consistently for `name`; FastAPI's default Pydantic v2 supports this.
- `EmailStr` requires `pydantic[email]` extra (i.e. `email-validator`).
- `UserUpdate` is **not** PATCH-style (no `Optional[...]` fields). All three fields required.
  This matches legacy `editAction.php` which mandates all three columns on update.

### 4.3 Status code matrix (per route)

| Route | 200 | 201 | 204 | 400 | 404 | 409 | 422 | 500 |
|---|---|---|---|---|---|---|---|---|
| `GET /api/users` | ✅ default | — | — | — | — | — | — | infra only |
| `POST /api/users` | — | ✅ default | — | malformed JSON | — | ✅ duplicate email (BR-C-11) | ✅ schema violations (BR-C-03..06) | infra only |
| `GET /api/users/{id}` | ✅ found | — | — | non-int `id` → 422 | ✅ no such row (BR-C-07) | — | ✅ non-int id at path | infra only |
| `PUT /api/users/{id}` | ✅ updated | — | — | malformed JSON | ✅ no such row (BR-C-07) | ✅ duplicate email (BR-C-11) | ✅ schema violations | infra only |
| `DELETE /api/users/{id}` | — | — | ✅ deleted (BR-C-08) | — | ✅ no such row | — | non-int path id | infra only |

Notes:
- `400 Bad Request` is reserved for genuinely malformed payloads (invalid JSON, wrong
  Content-Type); Pydantic validation errors are `422 Unprocessable Entity` per FastAPI default.
- `500 Internal Server Error` should be exceptional — only for unhandled exceptions; BR-C-11's
  `IntegrityError`-→-`409` translation prevents the most common path to a leaked 500.
- No `401`/`403` — auth is out of scope per OQ-005 Gate-1.

### 4.4 Error response shapes (RFC 9457 ProblemDetail-lite)

All error responses use `Content-Type: application/problem+json` and a body conforming to
`ProblemDetail`.

**404 example (BR-C-07):**
```json
{
  "type": "about:blank",
  "title": "User not found",
  "status": 404,
  "detail": "User 42 not found",
  "instance": "/api/users/42"
}
```

**409 example (BR-C-11):**
```json
{
  "type": "about:blank",
  "title": "Email already exists",
  "status": 409,
  "detail": "Email 'alice@example.com' is already registered.",
  "instance": "/api/users"
}
```

**422 example (BR-C-03 / BR-C-04 / BR-C-05 / BR-C-06):**
```json
{
  "type": "about:blank",
  "title": "Validation error",
  "status": 422,
  "detail": "Request body failed validation.",
  "instance": "/api/users",
  "errors": [
    {"loc": ["body", "name"],  "msg": "String should have at least 1 character", "type": "string_too_short"},
    {"loc": ["body", "age"],   "msg": "Input should be less than or equal to 150", "type": "less_than_equal"},
    {"loc": ["body", "email"], "msg": "value is not a valid email address",         "type": "value_error"}
  ]
}
```

A custom FastAPI `RequestValidationError` handler wraps the default 422 into the shape above so
the React client has a single error envelope to render.

---

## 5. UI Specification (final — frontend codegen depends on this)

This is the load-bearing section for the engagement. CodeGen will derive the React file tree,
the form library wiring, and the modal interaction model directly from §5.1–5.7.

### 5.1 Component tree (locked)

```
src/
├── main.tsx                       ← Vite entry; mounts <App /> + QueryClientProvider + Toaster
├── App.tsx                        ← single route → <UsersPage />
├── pages/
│   └── UsersPage.tsx              ← owns ALL modal state (see §5.2)
├── components/
│   ├── PageHeader.tsx             ← title + "Add User" button (props: onAddClick)
│   ├── UsersDataTable.tsx         ← shadcn DataTable wrapper over TanStack Table
│   │                                 props: rows, onEdit(user), onDelete(user)
│   ├── AddEditDialog.tsx          ← shadcn Dialog wrapping <UserForm />
│   │                                 props: open, mode ("add"|"edit"), user?, onClose, onSubmitted
│   ├── UserForm.tsx               ← react-hook-form + zodResolver(userFormSchema)
│   │                                 props: defaultValues, onSubmit, submitting, error
│   ├── DeleteAlertDialog.tsx      ← shadcn AlertDialog
│   │                                 props: open, user, onCancel, onConfirmed
│   └── EmptyState.tsx             ← rendered when rows.length === 0
├── api/
│   ├── client.ts                  ← fetch wrapper; baseURL from import.meta.env.VITE_API_BASE
│   └── users.ts                   ← listUsers / getUser / createUser / updateUser / deleteUser
├── hooks/
│   └── useUsers.ts                ← TanStack Query: useUsersQuery, useCreateUser, ...
├── lib/
│   ├── schemas.ts                 ← Zod userFormSchema (mirrors Pydantic — see §5.3)
│   └── problem.ts                 ← parse RFC-9457 ProblemDetail into UI-friendly toast text
└── types/
    └── user.ts                    ← TS User type (id, name, age, email)
```

Notes on the tree:
1. **`UsersPage` is the only stateful page.** All modal open/close booleans, the "currently
   selected user" for edit/delete, and the loading-on-mutation flags live in `UsersPage` —
   see §5.2 for rationale.
2. **`UserForm` is reused** by add and edit; the `mode` distinction lives in `AddEditDialog`
   (title text, submit button label) but the form fields/validators are identical (matches
   the API contract: `UserCreate` ≡ `UserUpdate`).
3. **No global Redux/Zustand store.** TanStack Query owns server state; `useState` owns ephemeral
   modal state.
4. **`EmptyState` is a peer component** (not embedded in `UsersDataTable`) so the page header's
   "Add User" CTA can be re-pointed from the empty state without duplicating the button.

### 5.2 State management (decision)

**Decision: a single `useState` cluster in `UsersPage`, NOT delegated to row-level components.**

```ts
// Conceptual — Stage 4 will codify exact useState/useReducer style.
const [addDialogOpen, setAddDialogOpen] = useState(false);
const [editingUser,   setEditingUser]   = useState<User | null>(null);
const [deletingUser,  setDeletingUser]  = useState<User | null>(null);
```

The dialogs derive `open` from these states:
- `<AddEditDialog open={addDialogOpen} mode="add" ... />`
- `<AddEditDialog open={!!editingUser} mode="edit" user={editingUser ?? undefined} ... />`
- `<DeleteAlertDialog open={!!deletingUser} user={deletingUser ?? undefined} ... />`

**Why centralised, not delegated:**

1. **At most one modal is open at a time.** Centralising prevents the bug where clicking
   another row's Edit while a delete dialog is open opens both — `UsersPage` can enforce the
   invariant `(addDialogOpen ? 1 : 0) + (editingUser ? 1 : 0) + (deletingUser ? 1 : 0) ≤ 1`
   trivially.
2. **Focus management is simpler** when one parent decides which dialog to render; shadcn's
   Dialog already handles focus trap per-instance.
3. **TanStack Query mutations are co-located** with the state that triggers them
   (`useCreateUser`, `useUpdateUser`, `useDeleteUser` are invoked from `UsersPage`'s handlers,
   not buried inside row components — easier to coordinate `onSuccess`-triggered toast +
   `invalidateQueries(['users'])`).
4. **Row components stay pure.** `UsersDataTable` accepts `onEdit(user)` and `onDelete(user)`
   callbacks; rows never know modals exist.
5. **Rejected alternative** — a `useReducer` in `UsersPage` was considered. With only 3 boolean-ish
   pieces of state and no inter-state derivation logic, `useState` is simpler and the reducer
   would over-engineer the surface.

A `useReducer` migration becomes attractive when a 4th modal or step-wise wizard is introduced;
this is explicitly **out of scope** for MVP.

### 5.3 Form validation (Pydantic mirror via Zod schemas)

Client-side Zod schema mirrors the Pydantic schema 1:1 so the user sees inline errors *before*
hitting the network, while the server remains the source of truth.

```ts
// src/lib/schemas.ts (sketch)
import { z } from "zod";

export const userFormSchema = z.object({
  name:  z.string().trim().min(1, "Name is required.").max(100, "Name is too long (max 100)."),
  age:   z.coerce.number().int("Age must be a whole number.")
                  .min(0, "Age cannot be negative.")
                  .max(150, "Age cannot exceed 150."),
  email: z.string().trim().email("Enter a valid email.").max(100, "Email is too long (max 100)."),
});

export type UserFormValues = z.infer<typeof userFormSchema>;
```

Pydantic ↔ Zod parity table:

| Field | Pydantic constraint | Zod constraint | Inline message |
|---|---|---|---|
| `name` | `min_length=1, max_length=100, strip_whitespace=True` | `.trim().min(1).max(100)` | "Name is required." / "Name is too long (max 100)." |
| `age` | `int, ge=0, le=150` | `.coerce.number().int().min(0).max(150)` | "Age must be a whole number." / "Age cannot be negative." / "Age cannot exceed 150." |
| `email` | `EmailStr, max_length=100, strip_whitespace=True` | `.trim().email().max(100)` | "Enter a valid email." / "Email is too long (max 100)." |

The form library is `react-hook-form` with `@hookform/resolvers/zod` so per-field error state
plumbs straight into shadcn `<FormMessage>` components — preserving the legacy `<font
color='red'>` per-field feedback pattern (BR-C-03 AC-03e).

**Server-side 422 fallback:** if the server rejects a payload that passed client validation
(rare but possible after a schema drift), `UserForm` displays the server's `errors[]` array
under the respective fields, falling back to a global error banner if `loc` cannot be matched.

### 5.4 Modal behaviour (open/close transitions, focus management, ESC + click-outside)

All three dialogs are shadcn primitives wrapping Radix UI, which gives the following invariants
for free; we document them as test acceptance criteria so they are not regressed:

| Behaviour | AddEditDialog | DeleteAlertDialog |
|---|---|---|
| **Focus on open** | First focusable input (`name`). | The Cancel button (per shadcn AlertDialog default — keeps destructive action one keypress away). |
| **Focus return on close** | Restored to the triggering button ("Add User" or row "Edit"). | Restored to the row "Delete" button. |
| **ESC key** | Closes the dialog; if form is dirty, no warning in MVP. | Closes the dialog (Cancel path). |
| **Click outside (overlay)** | Closes the dialog. | Closes the dialog (Cancel path). |
| **Body scroll lock** | Applied while open. | Applied while open. |
| **Animation** | Radix default fade + slight scale; no bespoke timing. | Same. |
| **Re-open with new data** | On selecting a different row to edit, dialog must re-mount or reset form state so stale values don't bleed across opens (use a `key={editingUser?.id}` on `<AddEditDialog>` to force remount). | N/A — no form state. |

Mutation lifecycle inside `AddEditDialog`:
1. User clicks Save.
2. `react-hook-form` blocks submit if client validation fails (inline errors appear; no network).
3. On valid submit → call `useCreateUser.mutate(values)` (or `useUpdateUser.mutate({id, values})`).
4. While pending → Save button shows spinner + is disabled; ESC + click-outside are **disabled**
   so the user can't close mid-flight (Radix `onOpenChange` ignores `false` while submitting).
5. On `201/200` → dialog closes; success toast `"User added"` / `"User updated"`; TanStack
   `queryClient.invalidateQueries(['users'])`.
6. On `409` (BR-C-11) → keep dialog open; show inline error under `email` ("This email is
   already registered.").
7. On `422` → keep dialog open; project server errors into per-field error state.
8. On any other error → keep dialog open; global error toast `"Could not save user. Please try
   again."`.

Mutation lifecycle inside `DeleteAlertDialog`:
1. User clicks Delete on the row → dialog opens.
2. User clicks Confirm → `useDeleteUser.mutate(id)`; button shows spinner; disabled.
3. On `204` → dialog closes; success toast `"User deleted"`; invalidate `['users']`.
4. On `404` → dialog closes; info toast `"That user was already removed."`; invalidate.
5. On other error → keep dialog open; error toast; restore button to active.

### 5.5 Empty state (when `/api/users` returns `[]`)

When the list query resolves to an empty array:

- `UsersDataTable` is **not** rendered (no empty header row floating above nothing).
- `<EmptyState />` renders in its place with:
  - An illustrative icon (Lucide `Users` icon, muted colour).
  - Headline: "No users yet."
  - Sub-text: "Add your first user to get started."
  - Primary CTA button: "Add User" (identical handler to the page-header button).
- Page header remains visible; its "Add User" button is also operable.

Acceptance:
- AC-EMPTY-01: With seed-DB empty, opening the SPA renders `EmptyState`, not the DataTable.
- AC-EMPTY-02: Clicking either CTA opens `AddEditDialog(mode="add")`.
- AC-EMPTY-03: After successfully adding a user, the DataTable replaces `EmptyState`.

### 5.6 Loading + error states (skeleton, retry button, toast)

The list query has three observable lifecycle states:

| State | Rendering |
|---|---|
| **Loading** (first fetch) | shadcn `<Skeleton>` rows: page header visible; 5 skeleton table rows (height ≈ row height) animate-pulse. |
| **Loading** (refetch after mutation) | Existing table stays visible (TanStack Query default keepPreviousData); a small inline spinner appears next to the page title. |
| **Error** | Header visible; body shows `<ErrorState />`: "Couldn't load users." + a Retry button that calls `refetch()`. |
| **Success — empty** | `<EmptyState />` (§5.5). |
| **Success — non-empty** | `<UsersDataTable />`. |

Toast usage:
- Success toasts (add/update/delete) use shadcn `Toaster` with the `default` variant and a
  3-second auto-dismiss.
- Error toasts use the `destructive` variant and a 5-second auto-dismiss.
- Toasts are dismissible by click.

### 5.7 Accessibility (keyboard nav, ARIA labels for icon-only buttons)

- **Page header "Add User" button** — visible text, default accessible name.
- **Row "Edit" / "Delete" buttons** — when rendered as icon-only (Lucide `Pencil` / `Trash2`),
  each must carry `aria-label={`Edit ${user.name}`}` / `aria-label={`Delete ${user.name}`}`
  to satisfy WCAG 4.1.2.
- **Form inputs** — every `<Input>` has an associated `<Label>` (shadcn's `FormField`
  pattern); per-field error text is wired via `aria-describedby` (handled by shadcn `FormMessage`).
- **AlertDialog** — Radix renders `role="alertdialog"`, `aria-labelledby` (title), and
  `aria-describedby` (body) automatically; no manual wiring required.
- **Keyboard nav**:
  - Tab order through table: row → Edit button → Delete button → next row.
  - Tab order inside form: name → age → email → Cancel → Save.
  - Enter key on a focused row's Edit button activates it.
  - Enter on submit button submits the form; never auto-submits on form-field Enter unless the
    form is valid (default `react-hook-form` behaviour suffices).
- **Colour contrast** — Tailwind `red-600` on white for destructive buttons clears WCAG AA;
  do not change the shadcn defaults without re-checking contrast.
- **Reduced motion** — Radix dialog animations respect `prefers-reduced-motion`; no extra work.

---

## 6. Data Model (locked)

### 6.1 PostgreSQL DDL (final)

```sql
CREATE TABLE users (
    id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  VARCHAR(100) NOT NULL,
    age   SMALLINT     NOT NULL,
    email VARCHAR(100) NOT NULL,
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT ck_users_age_range CHECK (age >= 0 AND age <= 150)
);
```

Notes:
- `GENERATED ALWAYS AS IDENTITY` is the SQL-standard replacement for `SERIAL`.
- `CONSTRAINT ck_users_age_range` is **belt-and-braces** alongside the Pydantic check; if a
  raw SQL insert ever bypasses the API (seed scripts, admin tools), the DB still rejects
  out-of-range ages.
- No `created_at`/`updated_at` columns in MVP — matches legacy schema 1:1 for dual-run parity.
  An audit-column add is recorded as residual OQ-C-001 (§9).

### 6.2 SQLAlchemy model sketch

```python
# Sketch only — Stage 4 owns the implementation.
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, SmallInteger, CheckConstraint, UniqueConstraint, Identity

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id:    Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    name:  Mapped[str] = mapped_column(String(100), nullable=False)
    age:   Mapped[int] = mapped_column(SmallInteger,         nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        UniqueConstraint("email",                   name="uq_users_email"),
        CheckConstraint("age >= 0 AND age <= 150",  name="ck_users_age_range"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
```

### 6.3 Indexes + constraints

| Object | Type | Purpose |
|---|---|---|
| `users_pkey` (implicit) | PK index on `id` | Identity uniqueness + ORDER BY `id DESC` scans |
| `uq_users_email` | UNIQUE index on `email` | BR-C-11 enforcement |
| `ck_users_age_range` | CHECK | BR-C-04 belt-and-braces |

No additional indexes in MVP — there is no search/filter/pagination surface to optimise for.
A non-unique index on `(name)` could be added later if name-search is introduced; that is
out of scope.

---

## 7. Risk-Flag Triage (re-ranked given Gate-1)

Each of Discovery's 8 RFs is re-classified after locking the target stack. **MUST FIX** = needed
for CodeGen/test PASS. **SHOULD FIX** = recommended for production but not a Gate-2 blocker.
**DOCUMENTED-WONT-FIX** = explicitly out of scope; rationale recorded.

| RF | Discovery title | Severity (Disc.) | Triage | Rationale |
|---|---|---|---|---|
| RF-001 | SQL injection in `edit.php` | CRITICAL | **MUST FIX → AUTO-RESOLVED** | Replaced by FastAPI typed path param `id: int` + SQLAlchemy parameterised query. Test: AC-09b + a regression test passing `?id=1;DROP TABLE users` style payload to confirm 422 not 500. |
| RF-002 | SQL injection in `delete.php` | CRITICAL | **MUST FIX → AUTO-RESOLVED** | Same mechanism as RF-001 + DELETE verb (BR-C-09). Regression test: `DELETE /api/users/foo` → 422. |
| RF-003 | Stored XSS via raw echo of `name`/`email` | HIGH | **MUST FIX → AUTO-RESOLVED** | React JSX text-node rendering auto-escapes. CodeGen MUST NOT use `dangerouslySetInnerHTML` anywhere. Test: seed a user whose name is `<script>alert(1)</script>` and assert the rendered table cell contains literal text, not an executed script. |
| RF-004 | Stored XSS in pre-filled form attribute | HIGH | **MUST FIX → AUTO-RESOLVED** | React controlled `value={field.value}` escapes attribute payloads. Same XSS-payload test reused. |
| RF-005 | HTML injection via unquoted `id` attribute | HIGH | **N/A in target** | The legacy bug was `<input ... value=<?php echo $id; ?>>` (unquoted). In target, `id` is a path param and never enters DOM as a raw HTML attribute. No code path can regress this without first re-architecting. Document and close. |
| RF-006 | No CSRF tokens on mutating ops | HIGH | **SHOULD FIX (deferred)** | OQ-005 says auth is out of scope; without auth there is no cookie-bound session, so traditional CSRF is moot. Mitigation: the API is JSON-body REST (cannot be triggered by an `<img src=...>` or HTML form post). When auth lands in Phase 5, SameSite=Strict cookies + double-submit token become MUST FIX. Recorded for Phase 5 handoff. |
| RF-007 | Delete via HTTP GET | MEDIUM | **MUST FIX** | Fixed by BR-C-09 (DELETE verb only). Test: a `GET /api/users/1/delete` URL returns 404, and `GET /api/users/1` does not mutate state. |
| RF-008 | Hardcoded DB credentials in `dbConnection.php` | LOW | **MUST FIX** | Replaced by `pydantic-settings` `BaseSettings` reading `DATABASE_URL` from env. `.env.example` committed; `.env` ignored. Test: backend boots only when env var present; secret never appears in any committed file (greppable assertion). |

Summary:
- 5 MUST FIX (4 auto-resolved by stack choice, 1 actively fixed via BR-C-09)
- 1 N/A
- 1 SHOULD FIX (deferred to Phase 5 with auth)
- 1 DOCUMENTED-WONT-FIX (none — RF-005 closes as N/A; no remaining wont-fix items)

---

## 8. Cross-Cutting Concerns

### 8.1 Environment configuration

Backend (`pydantic-settings` `BaseSettings`):

| Variable | Default (dev) | Production | Notes |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://crud:crud@localhost:5432/crud` | — (required) | asyncpg driver mandatory |
| `CORS_ORIGINS` | `http://localhost:5173` | comma-separated allowlist | Used by `CORSMiddleware` |
| `LOG_LEVEL` | `INFO` | `INFO` | Python logging level |
| `API_PREFIX` | `/api` | `/api` | Mounted on FastAPI app |

Frontend (`import.meta.env` via Vite):

| Variable | Default (dev) | Production |
|---|---|---|
| `VITE_API_BASE` | `/api` (proxied through Vite dev server) | `/api` (same-origin in dual-run) |

Secrets policy: `.env` files committed to `.gitignore`; `.env.example` carries the variable
names but no values. `dual-run/docker-compose.yml` reads from `.env` for orchestration.

### 8.2 Logging conventions

- Python `logging` module, configured at startup; root level from `LOG_LEVEL`.
- Format: `%(asctime)s %(levelname)s %(name)s %(message)s` (production) /
  human-readable colourised in dev (optional `rich` handler — out of scope for MVP).
- Each request gets a correlation id (FastAPI middleware or `starlette-context`) logged on
  every line for the request — recommended but **not required** for Gate 2.
- DB-layer errors (`IntegrityError`, etc.) are logged at WARNING with the offending email
  scrubbed (replaced by `***@***`) before being translated into a 409.
- No PII (full name, email) is written to logs at INFO; only user `id`.

### 8.3 CORS

- Backend at `http://localhost:8000` (dev) and same-origin in the dual-run Docker stack.
- Frontend dev server at `http://localhost:5173` (Vite default).
- FastAPI `CORSMiddleware` allows `CORS_ORIGINS`, methods `GET, POST, PUT, DELETE, OPTIONS`,
  headers `Content-Type, Authorization, Accept`. No credentials (`allow_credentials=False`)
  since OQ-005 means no cookies.

### 8.4 Dev vs prod build modes for the frontend

| Mode | Command | Output | Notes |
|---|---|---|---|
| **Dev** | `npm run dev` | Vite dev server on :5173 | HMR + source maps; `/api/*` proxied to :8000 via `vite.config.ts` server.proxy. |
| **Prod** | `npm run build` → `npm run preview` (or static-serve) | `dist/` (static assets) | Hashed filenames; production React minification; sourcemaps optional. |
| **Dual-run** | Built `dist/` mounted into nginx (or served by FastAPI's `StaticFiles`) on same origin as `/api` | — | No CORS needed in this mode; CSP `default-src 'self'` viable. |

The cockpit re-skin (Stage 8) consumes the built `dist/` for the "after" half of the side-by-side
visual.

---

## 9. Open Questions (residual)

Gate 1 closed OQ-001 through OQ-005. Consolidation surfaced exactly one new residual:

| ID | Question | Default | Owner | Decision deadline |
|---|---|---|---|---|
| OQ-C-001 | Should `users` carry `created_at`/`updated_at` timestamp columns for audit, even though legacy has none? | **NO — defer to Phase 5.** Adding now would diverge from legacy and complicate dual-run row comparison. | HITL | Phase 5 kickoff |

Items intentionally **not** raised as OQs (handled in BR-Cs):
- Email case-folding (BR-C-11 documents as MVP-deferred).
- Stale-data dialog reopens (§5.4 prescribes `key={user.id}` remount; not an OQ).
- Bulk operations (§4.1 explicitly out of scope).

---

## 10. Handoff to Planning

Planning should derive the React file tree directly from §5.1 (8 component files, 1 hooks file,
1 schemas file, 1 problem-parser, 1 types file, 1 api/client + api/users — ~13 frontend files
total) and the FastAPI router/service/model layout from §4 + §6. The 11 BR-Cs in §3 give a
1:1 testable target for Stage 6 TestGen — expect ~30–40 backend tests (one happy + 2–3 sad per
BR-C) plus ~12–18 frontend interaction tests (Vitest + Testing Library) covering BR-C-10 (delete
gate), BR-C-01 (DataTable order), §5.5 EmptyState, and §5.6 loading/error states. The
risk-flag triage in §7 means CodeGen has only **two** active fixes to engineer (BR-C-09 DELETE
verb + `pydantic-settings` env config); the remaining six RFs are auto-resolved by stack choice
and only need regression tests, not new code.

---
