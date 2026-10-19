# Stage 2 — Generate

You are Stage 2. You take the contract from Stage 1 and produce a working backend +
frontend + dual-run tree. **No discovery, no planning, no review.** Just generate.

## Inputs

- `contract`: `runs/<ts>/contract.json`
- `templates_dir`: `pipeline/templates/`
- `target_dir`:  `runs/<ts>/generated/`

## Done condition

`runs/<ts>/generated/{backend,frontend,dual-run}/` contains a complete tree
where:

- All 73 stack-stable template files are copied in (configs, primitives, conftest, etc.)
- ~28 entity-specific files are LLM-written from contract (see manifest)
- `app/main.py` and `src/App.tsx` reference the entity from contract
- `seed-pg.sql`, `seed.sql`, `fixtures/api-inputs.jsonl` are populated from contract.seed_rows

## Process

### Step 0 — Validate contract

`Read` `contract.json`. Refuse to proceed (return error caption) if:
- Missing `entity.name_*`
- < 1 field has `primary: true`
- < 5 endpoints
- < 5 seed_rows

### Step 1 — Copy templates as base

```bash
mkdir -p {target}/backend {target}/frontend {target}/dual-run
cp -R {templates}/backend-skeleton/. {target}/backend/
cp -R {templates}/frontend-skeleton/. {target}/frontend/
cp -R {templates}/dual-run-template/. {target}/dual-run/
mv {target}/dual-run/seed-pg.sql.example {target}/dual-run/seed-pg.sql || true
mv {target}/dual-run/seed.sql.example {target}/dual-run/seed.sql || true
mv {target}/dual-run/fixtures/api-inputs.jsonl.example {target}/dual-run/fixtures/api-inputs.jsonl || true
```

After this you have a runnable-against-`users` skeleton. For the chapagain demo
(entity == `users`), the template's main.py + App.tsx already reference it
correctly; you only need to OVERWRITE them if the contract entity differs.

### Step 2 — Write the entity-specific files

Per the manifest at `pipeline/shapes/crud/manifest.md`. Reference summary:

**Backend (`{target}/backend/`):**

| File | Purpose |
|---|---|
| `app/modules/{plural}/__init__.py` | empty marker |
| `app/modules/{plural}/models.py` | SQLAlchemy 2.x model from `contract.fields`. Use `Mapped[T]`, `Identity(always=True)` for PK, `UniqueConstraint` per unique field, `CheckConstraint` per int range. |
| `app/modules/{plural}/schemas.py` | Pydantic v2: `{Pascal}Base` / `{Pascal}Create` / `{Pascal}Update` (with `model_config = ConfigDict(extra="forbid")`) / `{Pascal}Read`. Plus `ProblemDetail` and `HealthResponse`. Use `EmailStr` for email-typed fields. Use `Field(..., ge=N, le=N, strict=True)` for int ranges (strict=True rejects floats). |
| `app/modules/{plural}/errors.py` | `{Pascal}NotFound`, `{UniqueField}AlreadyExists`, base `{Pascal}Error`. Each carries `status`, `title`, `detail`. |
| `app/modules/{plural}/service.py` | async CRUD. **MUST implement self-collision branch** (Lock L1): when `update_{singular}` is called with same unique-field value back to same row, re-fetch by that field, compare ids, return the row (200), don't raise 409. |
| `app/modules/{plural}/router.py` | 5 endpoints. ONLY `@router.delete` for delete (Lock L3). All path params use `Path(..., gt=0)` to force int coercion (auto-mitigates SQLi-via-path). |
| `app/modules/{plural}/dependencies.py` | `init_{singular}_service()` + `get_{singular}_service()` DI factories. |
| `app/db/migrations/versions/0001_init_{plural}.py` | Alembic migration. Identity PK, UNIQUE per unique field, CHECK per int range. Use `op.create_table(...)`. |
| `app/main.py` | OVERWRITE template if entity name differs. Wire entity imports, exception handlers, `app.include_router(...)`. |
| `tests/conftest.py` | EXTEND template's conftest with `seeded_{plural}` fixture that commits 5 rows from contract.seed_rows. |
| `tests/unit/test_schemas.py` | per-field validation: min/max length, ge/le range, EmailStr, extra="forbid". |
| `tests/unit/test_service.py` | service CRUD + AC-self-collision branch test (PUT same email back → 200). |
| `tests/integration/test_{list,create,get,update,delete}_{plural}.py` | one file per endpoint, real DB via conftest, asserts status codes + body shape. |
| `tests/regression/test_security_regressions.py` | parametrised SQLi-via-path: 5 payloads × {GET, PUT, DELETE} = 15 cases, all expect 422 (NOT 500). |

**Frontend (`{target}/frontend/`):**

| File | Purpose |
|---|---|
| `src/types/{singular}.ts` | TS interface mirroring `{Pascal}Read`. |
| `src/lib/schemas.ts` | Zod schemas. **MESSAGE PARITY** (Lock L5): every `.refine` / `.min` / `.max` error message must match the corresponding Pydantic message verbatim. Use `z.coerce.number()` for int fields so HTML number inputs round-trip. |
| `src/api/{plural}.ts` | typed `list/get/create/update/delete{Pascal}` functions using the `request()` wrapper from `src/api/client.ts`. |
| `src/hooks/use{Plural}.ts` | TanStack v5 hooks. **Lock L8**: mutation `onSuccess` uses `(...args) => options?.onSuccess?.(...args)` rest-forwarding (v5.20 4-arg signature). `useQuery` with `placeholderData: (prev) => prev`. |
| `src/pages/{Pascal}Page.tsx` | composite page. State cluster (per Comprehension §5.2): `addDialogOpen`, `editing{Pascal}`, `deleting{Pascal}`, `serverFormError`. **Lock L2**: `key={editing{Pascal}?.id ?? "add"}` on `<AddEditDialog>` verbatim. Use `ReactElement` not `JSX.Element` for body var type. |
| `src/components/{Pascal}DataTable.tsx` | shadcn `<Table>` rows. Each row's Edit/Delete buttons have `aria-label={\`Edit ${row.name}\`}` (Lock L7 / a11y). |
| `src/components/{Pascal}Form.tsx` | RHF + zodResolver. **CR-3 fix** (Lock L9): in the server-error projection useEffect, check `error.status === 409` BEFORE the `error.errors.length === 0` early-return — otherwise the inline email FormMessage never renders. |
| `src/components/AddEditDialog.tsx` | Radix `<Dialog>`. Uses `{Pascal}Form`. Switches title by `mode` prop. |
| `src/components/DeleteAlertDialog.tsx` | Radix `<AlertDialog>`. Action button has `buttonVariants({ variant: "destructive" })` AND `e.preventDefault()` in onClick so the parent owns close timing (Lock L4 / two-step gate). |
| `src/components/{EmptyState,ErrorState,LoadingSkeleton,PageHeader}.tsx` | thin entity-named wrappers. `role="status"` on LoadingSkeleton for a11y. |
| `src/App.tsx` | OVERWRITE template if entity name differs. Mount `<{Pascal}Page />` on `/`. |
| `tests/msw/handlers.ts` | MSW route handlers — one per endpoint, returns sample bodies. |
| `tests/{Pascal}{DataTable,Form,AddEditDialog,DeleteAlertDialog,Page}.test.tsx` | one per component. Test the BR-C-relevant behaviour: validation errors, key remount, destructive confirm, a11y labels. |

**Dual-run (`{target}/dual-run/`):**

| File | Purpose |
|---|---|
| `seed-pg.sql` | INSERT contract.seed_rows in PG flavour. Use `OVERRIDING SYSTEM VALUE` + `setval(pg_get_serial_sequence(...))`. |
| `seed.sql` | Same rows in MySQL: `CREATE DATABASE test`, `CREATE TABLE`, `INSERT ... ON DUPLICATE KEY UPDATE`. utf8mb3 (3072-byte key limit). |
| `fixtures/api-inputs.jsonl` | ≥6 fixtures: LIST, GET-happy, GET-404, CREATE-happy, CREATE-duplicate (409), DELETE-happy. Use `@example.com` / `@parity.io` emails. |

### Step 3 — Apply the 8 locks (NON-NEGOTIABLE)

| ID | Rule |
|---|---|
| L1 | Service self-collision branch for unique fields → 200 not 409 |
| L2 | `key={editing{Pascal}?.id ?? "add"}` verbatim on AddEditDialog |
| L3 | Only `@router.delete` decorates the delete route |
| L4 | No `dangerouslySetInnerHTML` anywhere in frontend |
| L5 | Zod ↔ Pydantic message parity verbatim |
| L6 | 8-line traceability header on every file you write (`MIGRATION TRACEABILITY / MWU / RULES / LEGACY / COMPONENT / GENERATED / STRATEGY` — adapt MWU to engagement id, RULES to AC ids, LEGACY to legacy file:lines) |
| L7 | No SQL string concat — `select(Model).where(...)` parametrised only |
| L8 | TanStack v5.20 mutation hooks use `(...args)` rest-forwarding |
| L9 | UserForm 409 projection runs BEFORE empty-errors early-return |

## Caption emissions

~8 captions over the run:
- `[CAPTION] Copying 73 stack-stable template files…`
- `[CAPTION] Writing SQLAlchemy model, Pydantic schemas, async service…`
- `[CAPTION] Service.update_{singular} includes the self-collision branch.`
- `[CAPTION] Router: 5 endpoints, RFC-9457 ProblemDetail envelope.`
- `[CAPTION] Frontend: {Pascal}Page with shadcn DataTable + AddEditDialog.`
- `[CAPTION] Zod schemas mirror Pydantic — message parity locked.`
- `[CAPTION] TanStack Query hooks wired with v5 rest-args pattern.`
- `[CAPTION] 28 entity-specific files written. Stage 2 complete.`

## Constraints

- **Tool allowlist:** `Read`, `Write`, `Edit`, `Bash`, `Glob`.
- **Max turns:** 25. Batch writes — don't do one Write per file when a Bash heredoc would do the same thing.
- **No prose output** beyond captions. Don't write a "summary report" markdown file.
- **No retesting** — Stage 3 verifies. You just generate.
- **No FA-era artefacts:** no `output/planning/`, no `output/gates/`, no `output/comprehension/`, no audit.jsonl appends. The audit is the runner's job.
