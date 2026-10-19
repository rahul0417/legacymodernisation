# MWU-CRUD-001 — Self-Review Report
**Date:** 2026-05-14
**Reviewer:** feature-dev:code-reviewer (Sonnet) — adversarial static review
**Classification:** CONDITIONAL_PASS
**Verdict:** Generated code is functionally correct and secure; 2 small fixes required before Stage 6 — a double-prefixed CORS env-var alias and the deprecated `JSX.Element` type usage.

---

## 1. Verdict Summary

| Category | PASS | WARN | FAIL | CRITICAL |
|---|---|---|---|---|
| A — BR-C Completeness (11 BR-Cs) | 11 | 0 | 0 | 0 |
| B — Behavioural Equivalence (5 routes) | 5 | 0 | 0 | 0 |
| C — Backend Code Quality (10 checks) | 9 | 1 | 0 | 0 |
| C2 — Frontend Code Quality (10 checks) | 9 | 1 | 0 | 0 |
| D — Test Adequacy (11 BR-Cs) | 10 | 1 | 0 | 0 |
| E — Traceability (logic-carrying files) | 23 | 0 | 0 | 0 |
| S — CRUD adversarial (13 checks) | 11 | 1 | 1 | 1 |
| Config | 0 | 0 | 1 | 1 |
| **Totals** | **78** | **4** | **2** | **2** |

**Total checks: 84. PASS: 78. WARN: 4. FAIL: 2. CRITICAL: 2.**

The generated code faithfully implements all 11 BR-Cs, all 5 API routes, the AC-11c self-collision logic, and the full RFC-9457 error envelope. The backend layer firewall is perfectly maintained. The frontend component tree, state management, and shadcn wiring are all correct. The two blocking issues are: (1) a double-prefix alias bug on `cors_origins` in `config.py` that will silently mis-route the `CRUD_CORS_ORIGINS` env var, and (2) a deprecated `JSX.Element` type usage that will break `tsc --noEmit` under TypeScript 5.x strict mode.

---

## 2. Category A — Business Rule Completeness

### BR-C-01 — Newest-first ordering on list
- **A1 Backend:** `service.py:58` — `select(User).order_by(User.id.desc())`. PASS.
- **A2 Frontend:** `hooks/useUsers.ts:43-45` — `placeholderData: (prev) => prev` (TQ v5 keepPreviousData equivalent). No client-side re-sort introduced. PASS.
- **A3 Edge cases:** Empty array returns `[]` not `null` — `router.py:53` `response_model=list[UserRead]` guarantees array. PASS.

### BR-C-02 — List read is side-effect-free
- **A1 Backend:** `service.py:52-60` — pure `SELECT`, no flush/commit/delete. PASS.
- **A2 Frontend:** `hooks/useUsers.ts:38-46` — `useQuery` (GET-only). PASS.
- **A3 Edge cases:** No `last_seen_at` mutation (no such column exists in `models.py`). PASS.

### BR-C-03 — All three editable fields mandatory and non-blank
- **A1 Backend:** `schemas.py:38-55` — `min_length=1`, `str_strip_whitespace=True` on `UserBase`. PASS.
- **A2 Frontend:** `lib/schemas.ts:18-22` — `.trim().min(1, "Name is required.")`. PASS.
- **A3 Edge cases:** `age=0` is valid (separate from missing) — `schemas.py:44` `ge=0` allows zero. PASS.

### BR-C-04 — Age integer [0, 150]
- **A1 Backend:** `schemas.py:44-50` — `Field(..., ge=0, le=150, strict=True)`. Belt-and-braces: `models.py:53-55` `CheckConstraint("age >= 0 AND age <= 150")`. PASS.
- **A2 Frontend:** `lib/schemas.ts:23-27` — `.int().min(0).max(150)`. `UserForm.tsx:120-122` — `<Input type="number" min={0} max={150} step={1}>`. PASS.
- **A3 Edge cases:** `strict=True` rejects floats (AC-04f). `age=0` accepted (AC-04c). PASS.

### BR-C-05 — Email format + length
- **A1 Backend:** `schemas.py:51-55` — `EmailStr`, `max_length=100`. PASS.
- **A2 Frontend:** `lib/schemas.ts:29-32` — `.trim().email("Enter a valid email.").max(100)`. PASS.
- **A3 Edge cases:** No normalisation (case-folding deferred per BR-C-11 docs). PASS.

### BR-C-06 — Name length ≤ 100
- **A1 Backend:** `schemas.py:38-43` — `max_length=100`. `models.py:49-51` `String(100)`. PASS.
- **A2 Frontend:** `lib/schemas.ts:19-22` — `.max(100)`. `UserForm.tsx:101` — `maxLength={100}`. PASS.
- **A3 Edge cases:** 100-char name accepted. PASS.

### BR-C-07 — Update preserves id; 404 on miss
- **A1 Backend:** `service.py:124` — `get_user` propagates `UserNotFound`. `service.py:126-128` — only name/age/email updated (never id). `schemas.py:64-70` — `extra="forbid"` rejects body-side id. PASS.
- **A2 Frontend:** `hooks/useUsers.ts:67-79` — `mutationFn: ({ id, values }) => updateUser(id, values)`. PASS.
- **A3 Edge cases:** Concurrent delete-then-update → 404 returned (no 500). PASS.

### BR-C-08 — Delete permanent, no soft-delete
- **A1 Backend:** `service.py:169-176` — `db.delete(user)` + `db.commit()`. No `deleted_at` column. PASS.
- **A2 Frontend:** `hooks/useUsers.ts:81-93` — `mutationFn: deleteUser` (HTTP DELETE). PASS.
- **A3 Edge cases:** Delete on non-existent id → `UserNotFound` → 404 (AC-08 edge case). PASS.

### BR-C-09 — DELETE verb only
- **A1 Backend:** `router.py:146` — only `@router.delete(...)` registered for removal. PASS.
- **A2 Frontend:** `api/users.ts:38-40` — `request<void>("DELETE", ...)`. No `window.location` navigation. PASS.
- **A3 Edge cases:** `GET /api/users/{id}` returns read-only `UserRead`, never deletes. PASS.

### BR-C-10 — UI delete gate (two-step)
- **A1 Backend:** N/A — UI rule.
- **A2 Frontend:** `DeleteAlertDialog.tsx:45-50` — `handleOpenChange` blocks close during submission. `DeleteAlertDialog.tsx:67-72` — `e.preventDefault()` stops auto-close on Action click. `DeleteAlertDialog.tsx:64` — `AlertDialogCancel disabled={submitting}`. PASS.
- **A3 Edge cases:** Double-click guarded by `disabled={submitting}`. AC-10f destructive variant: `buttonVariants({ variant: "destructive" })` at `DeleteAlertDialog.tsx:75`. PASS.

### BR-C-11 — Email UNIQUE → 409
- **A1 Backend:** `models.py:63` — `UniqueConstraint("email", name="uq_users_email")`. `service.py:93-98` — `IntegrityError` → `EmailAlreadyExists`. AC-11c self-collision: `service.py:138-158` — re-fetch by email, compare ids. PASS.
- **A2 Frontend:** `UserForm.tsx:76-80` — 409 response → `setError("email", { message: error.detail ?? "This email is already registered." })`. PASS.
- **A3 Edge cases:** AC-11c correctly returns 200 for self-collision (same user resubmits own email). PASS.

---

## 3. Category B — Behavioural Equivalence

### Route 1: GET /api/users → 200 list[UserRead]
- **B1 Inputs/outputs:** `router.py:51-66` — no params; returns `list[UserRead]` via `UserRead.model_validate(row)`. PASS.
- **B2 Status codes:** `status_code=status.HTTP_200_OK` at `router.py:54`. PASS.
- **B3 Error shapes:** No errors defined for this route; exception handler covers unexpected 500. PASS.
- **B4 Contract:** `Content-Type: application/json` (FastAPI default). Empty table → `[]`. PASS.

### Route 2: POST /api/users → 201 UserRead + Location
- **B1 Inputs/outputs:** `router.py:73-93` — takes `UserCreate` body; returns `UserRead`. Location header set at `router.py:92`. PASS.
- **B2 Status codes:** `status_code=status.HTTP_201_CREATED` at `router.py:76`. 409 from `EmailAlreadyExists` handler, 422 from `RequestValidationError` handler. PASS.
- **B3 Error shapes:** Both 409 and 422 produce `ProblemDetail` envelope per `main.py:127-173`. PASS.
- **B4 Contract:** `Location: /api/users/{id}` present on success (`router.py:92`). PASS.

### Route 3: GET /api/users/{id} → 200 UserRead
- **B1 Inputs/outputs:** `router.py:100-113` — path `user_id: int, Path(ge=1)`. Returns `UserRead`. PASS.
- **B2 Status codes:** 200 on found, 404 on miss (via `UserNotFound`), 422 on non-int path. PASS.
- **B3 Error shapes:** 404 ProblemDetail with `"User {id} not found"` detail. PASS.
- **B4 Contract:** `instance` set to request path in handler (`main.py:121`). PASS.

### Route 4: PUT /api/users/{id} → 200 UserRead
- **B1 Inputs/outputs:** `router.py:120-139` — path `user_id`, body `UserUpdate`. Returns updated `UserRead`. PASS.
- **B2 Status codes:** 200/404/409/422 all handled. PASS.
- **B3 Error shapes:** All via ProblemDetail envelope. AC-11c (self-collision → 200) implemented correctly in `service.py:138-158`. PASS.
- **B4 Contract:** `id` never changes (service assigns to name/age/email only). PASS.

### Route 5: DELETE /api/users/{id} → 204 No Content
- **B1 Inputs/outputs:** `router.py:146-164` — path `user_id`. Returns `Response(status_code=204)`. PASS.
- **B2 Status codes:** 204 on success, 404 on miss. PASS.
- **B3 Error shapes:** 404 ProblemDetail. PASS.
- **B4 Contract:** Response body empty. PASS.

---

## 4. Category C — Code Quality (BACKEND)

- **C1 Type hints:** All function signatures fully typed. `service.py:52,64,78,106,169` all return-typed. `router.py` uses `Annotated[T, Depends(...)]`. PASS.
- **C2 Async only on I/O:** All 5 service methods are `async def`. `_log_email_conflict` sync (no I/O — correct). `configure_logging` sync (startup only). PASS.
- **C3 Layer firewall:**
  - `service.py`: imports `sqlalchemy`, `sqlalchemy.exc`, `sqlalchemy.ext.asyncio` — no `fastapi`. PASS.
  - `router.py`: imports `AsyncSession` as typing-only surface. No raw SQL. PASS.
  - `models.py`: no `fastapi`, no `pydantic`. PASS.
  - `schemas.py`: no `sqlalchemy`. PASS.
- **C4 No global mutable state:** Module-level singletons in `dependencies.py:26-27` and `engine.py:35-36` are intentional, protected by `if _engine is None` guards. WARN: technically mutable module-level state, acceptable as documented singleton pattern.
- **C5 No print(); uses logger:** Zero `print()` calls. All observability via `logger.warning/error/info`. PASS.
- **C6 Types appropriate:** `age` uses `SmallInteger` (SMALLINT). `email`/`name` use `String(100)`. `id` uses `Identity(always=True)`. PASS.
- **C7 Service commits; router doesn't:** `service.py:100,163,176` — `db.commit()` in service only. Router never commits/flushes. PASS.
- **C8 ProblemDetail shape:** `main.py:117-194` produces `type`, `title`, `status`, `detail`, `instance`, `errors`. Media type `application/problem+json`. PASS.
- **C9 No SQL string concat:** No raw SQL strings. All via `select(User).where(...)`. Alembic uses `op.create_table(...)` with column objects. PASS.
- **C10 Test fixtures match plan:** `conftest.py` provides `event_loop`, `settings`, `db_engine`, `db_session_factory`, `db_session`, `app_instance`, `client`, `seeded_users` per §11.1. PASS.

---

## 5. Category C2 — Code Quality (FRONTEND)

- **C2-1 TS strict mode:** `tsconfig.json:14` — `"strict": true`. PASS.
- **C2-2 Functional components only:** All custom components are functional. PASS.
- **C2-3 No direct fetch outside api/:** Grep for `from "@/api"` in `components/` returns zero. PASS.
- **C2-4 React Query for all server state:** `hooks/useUsers.ts` covers list/create/update/delete via TQ. PASS.
- **C2-5 react-hook-form + zod everywhere:** `UserForm.tsx:52-59` only form, uses `zodResolver(userFormSchema)`. PASS.
- **C2-6 shadcn primitives only:** All UI surfaces route through `src/components/ui/` shadcn. No MUI/Bootstrap. PASS.
- **C2-7 Tailwind utility classes only:** No inline `style={{...}}` props in custom components. PASS.
- **C2-8 Component prop types match Planning §9.2:** AddEditDialog, UsersDataTable, DeleteAlertDialog, UserForm all match. PASS.
- **C2-9 useState lifted per Comprehension §5.2:** `UsersPage.tsx:53-57` owns all modal/server-error state. PASS.
- **C2-10 a11y:** `aria-label` on icon buttons (`UsersDataTable.tsx:66,72`). `role="status"` on loading skeleton. Radix AlertDialog provides `role="alertdialog"`. WARN: `JSX.Element` deprecated type at `UsersPage.tsx:165` — will trip strict TS deprecation warnings.

---

## 6. Category D — Test Adequacy

| BR-C | Backend test | Frontend test |
|---|---|---|
| BR-C-01 | `test_list_users.py:25-39` + `test_service.py:38-43` | `UsersDataTable.test.tsx:23-31` + `UsersPage.test.tsx:35-49` |
| BR-C-02 | `test_list_users.py:41-49` | (indirect via api-client) |
| BR-C-03 | `test_schemas.py:38-46`, `test_create_user.py:33-48` | `AddEditDialog.test.tsx:50-66` |
| BR-C-04 | `test_schemas.py:47-67`, `test_create_user.py:51-61` | `AddEditDialog.test.tsx:68-87` |
| BR-C-05 | `test_schemas.py:68-71`, `test_create_user.py:63-68` | `AddEditDialog.test.tsx:89-107` |
| BR-C-06 | `test_schemas.py:72-78`, `test_create_user.py:70-75` | (maxLength smoke via happy path) |
| BR-C-07 | `test_get_user.py:32-38`, `test_update_user.py:40-45`, `test_service.py:47-54` | `UsersPage.test.tsx` (indirect) |
| BR-C-08 | `test_delete_user.py:28-57` + `test_service.py:102-110` | `api-client.test.ts:25-29` |
| BR-C-09 | `test_security_regressions.py:36-45` | confirmed `deleteUser` uses DELETE at `api/users.ts:38` |
| BR-C-10 | N/A | `DeleteAlertDialog.test.tsx` (5 cases) |
| BR-C-11 | `test_create_user.py:87-102`, `test_update_user.py:47-63`, `test_service.py:64-98` | `AddEditDialog.test.tsx:109-131`, `api-client.test.ts:31-53` |

WARN: `api-client.test.ts` does NOT test `parseProblemDetail` field mapping directly (Planning §11.2 calls for it). Stage 6 TestGen should fill the gap.

---

## 7. Category E — Traceability

All 23 logic-carrying files have the mandatory 8-line traceability header. No phantom BR references found. No TODO markers present (Stage 4 responsibility met). PASS (23/23).

---

## 8. CRUD-specific adversarial checks

- **S1 Status codes:** GET 200, POST 201, DELETE 204, 404 via `UserNotFound`, 422 via FastAPI default. PASS.
- **S2 ProblemDetail shape:** `schemas.py:88-105`, media type `application/problem+json`. PASS.
- **S3 AddEditDialog key:** WARN — `UsersPage.tsx:204` uses ``editingUser ? `edit-${editingUser.id}` : "add"`` instead of `editingUser?.id ?? "add"` verbatim. Functionally equivalent (remount on row switch + mode switch) but does not match Gate-3 lock #2 verbatim. Non-blocking.
- **S4 DeleteAlertDialog explicit click:** `DeleteAlertDialog.tsx:67-72` — `e.preventDefault()` blocks auto-close, parent owns timing. PASS.
- **S5 Newest-first ordering:** `service.py:58` `ORDER BY id DESC`. DataTable preserves server order. PASS.
- **S6 Email UNIQUE + AC-11c:** DB constraint + service translation + AC-11c branch all present. PASS.
- **S7 Age range 0–150:** Pydantic strict + Zod int + DB CheckConstraint. PASS.
- **S8 CORS:** FAIL — see CRITICAL-1.
- **S9 No dangerouslySetInnerHTML:** Grep zero hits. PASS.
- **S10 DELETE verb purity:** `router.py:146` only `@router.delete`. PASS.
- **S11 Hand-written shadcn primitives:** button/dialog/alert-dialog/form/skeleton match canonical templates. PASS.
- **S12 ApiError export:** `api/client.ts:25-41` exported; `hooks/useUsers.ts:32` re-exported. PASS.
- **S13 Zod ↔ Pydantic message parity:** `age` and `email` messages match §9.5 verbatim. PASS.

---

## 9. Hallucinations

No phantom BRs. No unrequested features. The `db_echo: bool` setting in `config.py:60` is a benign operational addition. `_log_email_conflict` in `service.py:180-194` implements the PII scrubbing specified in Comprehension §8.2. The `submitLabel` prop on `UserForm` (not in Planning §9.2.5) is a straightforward UX improvement. No contradictions.

---

## 10. Critical Issues (BLOCKING — must fix before Stage 6)

### CRITICAL-1: cors_origins double-prefix alias bug
**File:** `app/core/config.py:51-55`
**Issue:** Field `cors_origins` has both `env_prefix="CRUD_"` (in `SettingsConfigDict`) and `alias="CRUD_CORS_ORIGINS"` (on the Field). In pydantic-settings, env var lookup for an aliased field applies the prefix to the alias: the effective env var becomes `CRUD_CRUD_CORS_ORIGINS`. With `populate_by_name=True`, the field-name path (`CRUD_CORS_ORIGINS`) works, but the alias creates a confusing and broken override path.
**Fix:** Remove the `alias` from the `cors_origins` Field.
```python
cors_origins: list[str] = Field(
    default_factory=lambda: ["http://localhost:5173"],
    description="Allowed CORS origins (CSV in env; list in code).",
)
```

### CRITICAL-2: `JSX.Element` deprecated type in strict TypeScript
**File:** `src/pages/UsersPage.tsx:165`
**Issue:** `let body: JSX.Element;` uses the deprecated global `JSX` namespace. With `"jsx": "react-jsx"` and `strict: true` in `tsconfig.json`, TypeScript 5.3 emits a deprecation error: `'JSX.Element' is deprecated`. This will break `tsc --noEmit` in `npm run build`.
**Fix:** `let body: React.ReactElement;`

---

## 11. Recommendations (NON-BLOCKING)

1. **AddEditDialog key deviation from spec verbatim** (`UsersPage.tsx:204`) — update to `key={editingUser?.id ?? "add"}` to match Gate-3 lock #2 verbatim.
2. **`parseProblemDetail` direct unit test missing** — Stage 6 TestGen should add a direct unit test for `loc[last]` → field extraction.
3. **`pool_size`/`max_overflow` not guarded for SQLite** (`engine.py:50-51`) — acceptable because tests bypass `init_engine`; consider guarding for forward-safety.
4. **`useMemo` on rows** (`UsersPage.tsx:61`) — minor over-memoization; not a bug.
5. **`conftest.py:43`** — redundant `pytest_plugins = ["pytest_asyncio"]` listing; harmless.

---

## 12. Verdict

**CONDITIONAL_PASS**

Conditions for PASS:
1. Fix `app/core/config.py:53` — remove `alias="CRUD_CORS_ORIGINS"` from the `cors_origins` Field (CRITICAL-1).
2. Fix `src/pages/UsersPage.tsx:165` — replace `JSX.Element` with `React.ReactElement` (CRITICAL-2).

Once these two fixes are applied, all 11 BR-Cs are correctly implemented, all 5 API routes match the contract, the layer firewall is maintained, shadcn primitives are correct, the AC-11c self-collision logic is properly implemented, the RFC-9457 ProblemDetail envelope is correct, and the test suite provides adequate coverage. The code is ready for Stage 6 TestGen after the two fixes.
