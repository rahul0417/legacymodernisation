# Discovery Report — MWU-CRUD-001
**Source:** chapagain/crud-php-simple
**Engagement:** PNS-CRUD-001
**Stage:** 1 — Discovery
**Agent:** code-explorer (claude-sonnet-4-6)
**Date:** 2026-05-14
**Status:** DRAFT — awaiting Gate 1 HITL approval

---

## §1. Engagement Context

### What is chapagain/crud-php-simple?

chapagain/crud-php-simple is a minimal, educational PHP CRUD application written in classic procedural style against a single MySQL `users` table with four columns: `id`, `name`, `age`, and `email`. The entire codebase is 222 lines across seven PHP files, one SQL DDL script, and a README. It implements four distinct screens — a record list, an add form, an edit form, and a direct-delete handler — using bare HTML 3.2-era markup (`<table border=0 bgcolor='#DDDDDD'>`, `<font color='red'>`) with no CSS framework, no templating layer, and no MVC separation. Database access is handled via the `mysqli_*` procedural extension with inline SQL strings. It was published as a blog-post companion piece illustrating the simplest possible PHP CRUD, and as such it makes no attempt at production hardening: there are no CSRF tokens, no input type validation, minimal XSS protection, and two confirmed SQL injection vectors. It is exactly the kind of file-per-page PHP legacy that enterprises accumulated between 1999 and 2010 and that modernisation pipelines exist to replace.

### Why migrate?

The application has multiple critical security vulnerabilities that would be unacceptable in any customer-facing or internal-production deployment: two direct SQL injection vectors (`edit.php` and `delete.php` both use unescaped GET parameters directly in SQL), stored XSS via unescaped column values echoed into HTML, and no CSRF protection on any mutating operation. Beyond security, the user experience is trapped in the 1990s — four separate full-page navigations for simple CRUD, JavaScript `window.confirm()` for delete confirmation, and `<font>` tags for error feedback. The target stack (FastAPI + React 18 + shadcn/ui + Tailwind) replaces all of this with a single-page application offering a modern DataTable, modal-driven add/edit flows, an AlertDialog for delete confirmation, and Toast notifications — delivering a visually compelling "old vs new" contrast that is the primary demo artefact for this engagement.

### Complexity rating: LOW

Rationale: one table, four columns, four operations (CRUD), no joins, no transactions, no business logic beyond empty-field validation, no authentication, no multi-tenancy, no file uploads, no pagination. The complexity of this migration lies entirely in the security remediations and the UI transformation, not in business logic fidelity. The backend API surface is five endpoints (list, create, read-one, update, delete). The React SPA is one route with two modals and one alert dialog.

---

## §2. File Inventory

| File | Lines | Purpose | Key constructs | HTML emitted |
|---|---|---|---|---|
| `dbConnection.php` | 8 | MySQL connection bootstrap | `mysqli_connect()`, hardcoded credentials (`root`/`root`, db `test`) | None |
| `database.sql` | 11 | MySQL DDL | `CREATE TABLE users`, `auto_increment`, `int(11)` PK, `varchar(100)`, `int(3)` | None |
| `index.php` | 40 | List all users | `mysqli_query()`, `mysqli_fetch_assoc()`, `SELECT * FROM users ORDER BY id DESC` | `<html>`, `<table width='80%' border=0>`, header row `bgcolor='#DDDDDD'`, data rows with Edit/Delete links, inline `onClick="return confirm(...)"` |
| `add.php` | 33 | Add-user form (pure HTML) | No PHP logic | `<form action="addAction.php" method="post">`, 3 `<input type="text">` for name/age/email, submit button |
| `addAction.php` | 47 | Add-user POST handler | `mysqli_real_escape_string()`, empty-check, `INSERT INTO users`, success/error echo | `<font color='red'>` error messages, `<font color='green'>` success, link back to `index.php` |
| `edit.php` | 51 | Edit-user form + record fetch | `$_GET['id']` — **unescaped** in SQL; `mysqli_fetch_assoc()` | `<form action="editAction.php" method="post">`, 3 pre-filled `<input type="text">`, hidden `<input name="id">` with **unquoted attribute value** |
| `editAction.php` | 34 | Edit-user POST handler | `mysqli_real_escape_string()` on POST fields, `UPDATE users SET ... WHERE id = $id` — `$id` unquoted in SQL | `<font color='red'>` errors, `<font color='green'>` success |
| `delete.php` | 13 | Delete-user handler (GET) | `$_GET['id']` — **no escaping**, bare `DELETE FROM users WHERE id = $id`, then `header("Location:index.php")` | None (redirect only) |
| `README.md` | 10 | Author docs | Link to blog post | None |

---

## §3. Data Model

### §3.1 MySQL schema (verbatim)

```sql
create database test;
use test;
CREATE TABLE `users` (
  `id` int(11) NOT NULL auto_increment,
  `name` varchar(100) NOT NULL,
  `age` int(3) NOT NULL,
  `email` varchar(100) NOT NULL,
  PRIMARY KEY  (`id`)
);
```

Note: `int(3)` and `int(11)` are MySQL display-width annotations only; they do not constrain stored value range. Both columns store standard 4-byte signed integers.

### §3.2 PostgreSQL target schema

```sql
CREATE TABLE users (
    id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name    VARCHAR(100)    NOT NULL,
    age     SMALLINT        NOT NULL,
    email   VARCHAR(100)    NOT NULL
);
```

### §3.3 Type mapping

| MySQL column | MySQL type | PostgreSQL type | Python type | Rationale |
|---|---|---|---|---|
| `id` | `int(11) NOT NULL auto_increment` | `INTEGER GENERATED ALWAYS AS IDENTITY` | `int` | Standard identity PK |
| `name` | `varchar(100) NOT NULL` | `VARCHAR(100) NOT NULL` | `str` | Direct mapping |
| `age` | `int(3) NOT NULL` | `SMALLINT NOT NULL` | `int` | Valid age fits SMALLINT (-32768..32767); saves 2 bytes |
| `email` | `varchar(100) NOT NULL` | `VARCHAR(100) NOT NULL` | `str` | Direct mapping; add UNIQUE (see OQ-001) |

### §3.4 Naming

Recommendation: **keep `users`**. Generic enough; renaming adds noise without benefit.

---

## §4. Business Rules

| ID | Rule | Source | Enforced in legacy? |
|---|---|---|---|
| BR-001 | `name` must not be empty (create) | `addAction.php:18-21` | Yes — server-side |
| BR-002 | `age` must not be empty (create) | `addAction.php:23-26` | Yes — no numeric check |
| BR-003 | `email` must not be empty (create) | `addAction.php:28-31` | Yes — no format check |
| BR-004 | `name` must not be empty (update) | `editAction.php:13-16` | Yes |
| BR-005 | `age` must not be empty (update) | `editAction.php:18-21` | Yes |
| BR-006 | `email` must not be empty (update) | `editAction.php:22-25` | Yes |
| BR-007 | Records listed newest-first | `index.php:6` (`ORDER BY id DESC`) | Yes |
| BR-008 | Delete is permanent with no soft-delete or undo | `delete.php:9` | Yes |
| BR-009 | `id` is surrogate PK; uniqueness DB-enforced | `database.sql:9` | Yes |
| BR-010 | All four columns are mandatory (NOT NULL) | `database.sql:6-9` | Yes — DB-enforced |
| BR-011 | Age stored as integer | `database.sql:8` | Partial — accepts any int |
| BR-012 | Delete requires explicit confirmation | `index.php:34` (`onClick=confirm`) | Yes — client-side JS only (bypassable) |

**Rules missing in legacy that should be added in target:**

| ID | Missing rule | Recommended enforcement |
|---|---|---|
| BR-M01 | `email` must match valid format | Pydantic `EmailStr` + HTML `type="email"` |
| BR-M02 | `age` in sensible range (0–150) | Pydantic `Field(ge=0, le=150)` + `SmallInteger` |
| BR-M03 | `email` should be unique per user | `UNIQUE` constraint (see OQ-001) |
| BR-M04 | `name` ≤ 100 chars (surfaced) | Pydantic `Field(max_length=100)` |
| BR-M05 | Delete not triggerable by GET / link prefetch | Use HTTP `DELETE /api/users/{id}` |

---

## §5. UI / API Contract

### §5.1 Legacy screens

#### Screen 1 — User List (`index.php`)
- HTTP: `GET /index.php`
- Query: `SELECT * FROM users ORDER BY id DESC`
- HTML: full doc; `<table width='80%' border=0>` with `<tr bgcolor='#DDDDDD'>` header; one row per user
- Columns: Name, Age, Email, Action
- Actions: `<a href="edit.php?id={id}">Edit</a> | <a href="delete.php?id={id}" onClick="return confirm(...)">Delete</a>`
- Add link: `<a href="add.php">Add New Data</a>`
- XSS protection: NONE — `$res['name']` / `$res['email']` echoed raw (`index.php:30-31`)

#### Screen 2 — Add Form (`add.php`)
- HTTP: `GET /add.php` (display) → `POST /addAction.php` (submit)
- Fields: `name` (text), `age` (text), `email` (text) — all plain `type="text"`, no required attr
- Submit: `<input type="submit" name="submit" value="Add">`
- Back: `<a href="index.php">Home</a>`
- Validation: NONE client-side

#### Screen 3 — Add Handler (`addAction.php`)
- HTTP: `POST /addAction.php`
- Input: `$_POST['name']`, `$_POST['age']`, `$_POST['email']`
- Escaping: `mysqli_real_escape_string()` on all three (`addAction.php:13-15`)
- Validation: `empty()` check only — no type or format
- Success: `INSERT INTO users` + inline green `<font>` + link to index
- Error: inline red `<font>` per field + `<a href='javascript:self.history.back();'>`
- HTTP status: **always 200** (no 201, no 400)

#### Screen 4 — Edit Form (`edit.php`)
- HTTP: `GET /edit.php?id={id}`
- Fetch SQL: `SELECT * FROM users WHERE id = $id` — **`$id` is raw `$_GET['id']`** (`edit.php:9`) — **SQL injection**
- Fields: pre-filled `<input type="text" value="<?php echo $name; ?>">` — **all unescaped**
- Hidden: `<input type="hidden" name="id" value=<?php echo $id; ?>>` — **attribute value unquoted** — HTML injection
- Submit: `<input type="submit" name="update" value="Update">`

#### Screen 5 — Edit Handler (`editAction.php`)
- HTTP: `POST /editAction.php`
- Escaping: `mysqli_real_escape_string()` on POST fields (`editAction.php:7-10`)
- SQL: `UPDATE users SET ... WHERE id = $id` — `$id` escaped but unquoted in WHERE
- Success/error: same inline-`<font>` pattern as `addAction.php`
- HTTP status: always 200

#### Screen 6 — Delete Handler (`delete.php`)
- HTTP: `GET /delete.php?id={id}` — **GET with side effects (anti-REST)**
- Input: `$_GET['id']` — **no escaping** (`delete.php:6`)
- SQL: `DELETE FROM users WHERE id = $id` — **SQL injection**
- Success: `header("Location:index.php")` — 302 redirect
- CSRF: NONE

---

### §5.2 Proposed modernised React SPA

```
App
└── UsersPage
    ├── PageHeader ("Users")
    │   └── Button ("Add User") → opens AddEditDialog(mode="add")
    ├── UsersDataTable          ← shadcn DataTable + TanStack Table
    │   ├── columns: Name | Age | Email | Actions
    │   └── per-row: Button("Edit") → AddEditDialog(mode="edit", user)
    │              Button("Delete") → DeleteAlertDialog(userId)
    ├── AddEditDialog           ← shadcn Dialog
    │   └── UserForm
    │       ├── Input name="name"   (type="text",  required, maxLength=100)
    │       ├── Input name="age"    (type="number", min=0, max=150, required)
    │       ├── Input name="email"  (type="email",  required)
    │       └── Button("Save" / "Update")
    ├── DeleteAlertDialog       ← shadcn AlertDialog
    │   ├── "Are you sure? This cannot be undone."
    │   └── Button("Delete") / Button("Cancel")
    └── Toaster                 ← shadcn Toaster (success + error toasts)
```

### §5.3 API contract — FastAPI endpoints

| Method | Path | Request | Response | Legacy equivalent |
|---|---|---|---|---|
| `GET` | `/api/users` | — | `200 List[UserRead]` (ordered `id DESC`) | `index.php` SELECT |
| `POST` | `/api/users` | `UserCreate` | `201 UserRead` | `addAction.php` INSERT |
| `GET` | `/api/users/{id}` | path `id: int` | `200 UserRead` or `404` | `edit.php` SELECT |
| `PUT` | `/api/users/{id}` | `UserUpdate` | `200 UserRead` or `404` | `editAction.php` UPDATE |
| `DELETE` | `/api/users/{id}` | path `id: int` | `204 No Content` or `404` | `delete.php` DELETE |

### §5.4 Pydantic schemas

```python
from pydantic import BaseModel, EmailStr, Field

class UserBase(BaseModel):
    name:  str = Field(..., min_length=1, max_length=100)
    age:   int = Field(..., ge=0, le=150)
    email: EmailStr

class UserCreate(UserBase): pass
class UserUpdate(UserBase): pass

class UserRead(UserBase):
    id: int
    model_config = {"from_attributes": True}
```

### §5.5 Modal behaviour spec

| Modal | Trigger | On success | On cancel | On error |
|---|---|---|---|---|
| AddEditDialog (add) | "Add User" button | Close + refresh table + success Toast | Close, no API call | Error Toast |
| AddEditDialog (edit) | Row "Edit" button | Close + refresh table + success Toast | Close, no API call | Error Toast |
| DeleteAlertDialog | Row "Delete" button | Close + refresh table + success Toast | Close, no API call | Error Toast |

---

## §6. Dependencies

### PHP constructs → Python/SQLAlchemy/FastAPI

| PHP | File:line | Equivalent |
|---|---|---|
| `mysqli_connect()` | `dbConnection.php:8` | `create_async_engine("postgresql+asyncpg://...")` + `AsyncSession` |
| `mysqli_query()` | many | `await session.execute(select(...))` |
| `mysqli_fetch_assoc()` | `index.php:28`, `edit.php:12` | `result.mappings().all()` / `scalar_one_or_none()` |
| `mysqli_real_escape_string()` | `addAction.php:13-15`, `editAction.php:7-10` | **Not needed** — SQLAlchemy parameterised queries |
| `$_GET['id']` | `edit.php:6`, `delete.php:6` | FastAPI path param `id: int` (typed + validated) |
| `$_POST[...]` | `addAction.php:13-15`, `editAction.php:7-10` | Pydantic request body schema |
| `header("Location:...")` | `delete.php:12` | `return Response(status_code=204)` — React handles refresh |
| `empty()` | many | Pydantic `Field(min_length=1)` / `Field(ge=0)` |

### External libraries (legacy)
None. No composer, no npm.

### Target stack
| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.110.x | API framework |
| sqlalchemy[asyncio] | 2.x | Async ORM |
| asyncpg | latest | PG async driver |
| pydantic[email] | 2.x | Validation + EmailStr |
| alembic | latest | Migrations |
| react | 18.x | UI |
| @tanstack/react-table | 8.x | DataTable headless |
| @radix-ui/react-dialog + react-alert-dialog | latest | shadcn primitives |
| react-hook-form + zod | latest | Forms + client validation |
| tailwindcss | 3.x | Styling |
| vite | 5.x | Build |
| vitest | latest | Frontend tests |

---

## §7. Risk Flags

| ID | Severity | Category | Location | Description | Recommended fix |
|---|---|---|---|---|---|
| RF-001 | **CRITICAL** | SQL Injection | `edit.php:9` | `$id = $_GET['id']` used directly in `SELECT * FROM users WHERE id = $id` with zero escaping. Attacker can inject arbitrary SQL via the URL. | FastAPI path param `id: int` is type-coerced; SQLAlchemy parameterised query eliminates injection. |
| RF-002 | **CRITICAL** | SQL Injection | `delete.php:6,9` | `$_GET['id']` used directly in `DELETE FROM users WHERE id = $id`. Crafted URL can delete all rows or drop tables. | Same as RF-001: `DELETE /api/users/{id}` with `id: int` + SQLAlchemy `session.delete()`. |
| RF-003 | HIGH | Stored XSS | `index.php:30-31` | `$res['name']` / `$res['email']` echoed unescaped into HTML. Stored XSS payload executes on every page load. | React renders text nodes safely by default; no `dangerouslySetInnerHTML` anywhere. |
| RF-004 | HIGH | Stored XSS | `edit.php:33-34,41` | Pre-filled form values echoed unescaped into `value=` attributes. | React controlled components (`value={field.value}`) escape attribute values. |
| RF-005 | HIGH | HTML Injection | `edit.php:44` | `value=<?php echo $id; ?>` — attribute value **unquoted**. Crafted `id` injects arbitrary HTML attributes. | `id` becomes path parameter, never embedded in HTML. |
| RF-006 | HIGH | CSRF | All mutating ops | No CSRF tokens on any form. Delete is GET — `<img src="delete.php?id=1">` is enough to destroy data. | JSON-body REST API + SameSite=Strict cookies (when auth is added). Delete becomes proper HTTP DELETE. |
| RF-007 | MEDIUM | Unsafe HTTP Semantics | `delete.php:6` | Delete triggered by GET. Browser prefetch, search-engine crawlers, bookmark navigation can delete records. | `DELETE /api/users/{id}` requires explicit fetch call from React AlertDialog. |
| RF-008 | LOW | Hardcoded Credentials | `dbConnection.php:2-5` | DB password committed to source. | Env vars via `pydantic-settings` `BaseSettings`; `.env` in `.gitignore`. |

---

## §8. Open Questions

| ID | Question | Default | For |
|---|---|---|---|
| OQ-001 | Should `email` have UNIQUE constraint? | YES (add UNIQUE; flag any duplicate-email rows during migration) | HITL |
| OQ-002 | Valid age range? | 0–150 (Pydantic `Field(ge=0, le=150)`) | HITL |
| OQ-003 | Table name — keep `users` or rename? | Keep `users` | HITL |
| OQ-004 | Add pagination? | Defer to Phase 5; demo seeds < 20 rows | Planning |
| OQ-005 | Add authentication? | Out of scope for this demo | HITL |

---

## §9. Recommended Next Step

Comprehension Agent should prioritise:

1. **Formalise the five API endpoint contracts** with full Pydantic schemas including all validation rules from §4 (BRs + BR-M01..M05).
2. **Resolve OQ-001 (email UNIQUE) and OQ-002 (age range)** before Planning so the SQLAlchemy model + Alembic migration are correct from the start.
3. **Lock the React component tree** from §5.2. Decide whether `UsersPage` owns all modal state in a single `useState` or delegates to row components — affects 80% of frontend code structure.
4. **Carry forward 8 risk flags** to Planning's security checklist.
5. **Frontend codegen note:** the visual before/after is the demo's key artefact. Plan screenshot capture in Stage 7.

**3 most important UI elements to preserve:**

1. **Delete confirmation gate (BR-012):** legacy `onClick="return confirm()"` is the only safeguard before permanent delete. The target `DeleteAlertDialog` must preserve a two-step confirmation pattern — explicit "Delete" button click, never auto-dismissed.

2. **Newest-first list ordering (BR-007):** `ORDER BY id DESC` is the only display rule. DataTable default sort must be descending by `id`.

3. **All-fields-mandatory validation (BR-001..BR-006, BR-010):** field-level validation errors must appear inline (not just global toasts), preserving the per-field feedback pattern the legacy `<font color='red'>` provides.
