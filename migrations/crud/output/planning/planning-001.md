# MWU-CRUD-001 — Planning Report

**Classification:** APPROVED-CANDIDATE (awaits Gate 3)
**Generated:** 2026-05-14
**Agent:** planner_agent (Opus · code-architect)
**Upstream:** comprehension-001.md · gate-1.md · gate-2.md

---

## 1. Architecture overview

Two-codebase migration: Python 3.12 + FastAPI 0.110 + SQLAlchemy 2.x async + PostgreSQL 16 (backend) and React 18 + TypeScript + shadcn/ui + Tailwind + Vite + TanStack Query (frontend). Communication via five JSON HTTP endpoints under `/api/users`. No SSR, no shared templates — clean API ↔ SPA boundary.

### 1.1 Backend layers (4-tier, mirrors shorty's proven split)

- **Model** (`app/modules/users/models.py`) — SQLAlchemy `DeclarativeBase`, `Mapped[T]`, constraints. Imports only `sqlalchemy` + `app.db.base.Base`. No FastAPI, no Pydantic.
- **Schema** (`app/modules/users/schemas.py`) — Pydantic v2 DTOs. The wire contract. No SQLAlchemy.
- **Service** (`app/modules/users/service.py`) — `UserService` class, 5 async methods, raises domain exceptions. NO FastAPI imports.
- **Router** (`app/modules/users/router.py`) — `APIRouter`, `Depends`, catches domain exceptions → `ProblemDetail`. Does NOT import sqlalchemy except `AsyncSession` as a type.

Plus `errors.py` (`UsersError`, `UserNotFound`, `EmailAlreadyExists`) and `dependencies.py` (`get_user_service`, `init_user_service`).

### 1.2 Frontend layers (5-tier, strict downward imports)

1. **Pages** (`src/pages/`) — `UsersPage`. Owns ephemeral UI state via `useState`. Composes components.
2. **Components** (`src/components/`) — presentational + interactive, wrap shadcn primitives. Pure props-in / events-out. Never call API directly.
3. **Hooks** (`src/hooks/`) — TanStack Query wrappers. Own server state, cache keys, mutation lifecycle.
4. **API client** (`src/api/`) — typed fetch wrappers. Translates RFC-9457 envelopes. Owns `VITE_API_BASE`.
5. **Lib / types** (`src/lib/`, `src/types/`) — pure utilities. No React, no fetch.

### 1.3 Layer firewall (non-negotiable)

| Firewall | Enforcement |
|---|---|
| `service.py` ≠ `from fastapi/starlette` | grep returns zero |
| `router.py` ≠ `from sqlalchemy` (except `AsyncSession` typing) | All SQL via UserService |
| `models.py` ≠ `from fastapi/pydantic` | Persistence decoupled |
| `schemas.py` ≠ `from sqlalchemy` | Wire decoupled |
| Components ≠ `from "@/api/"` directly | Always via hooks |
| `src/lib/` & `src/types/` ≠ React imports | Pure, testable, tree-shakeable |
| `src/api/` ≠ React imports | Plain fetch, vitest+msw-friendly |

### 1.4 Async + Pydantic v2 + SQLAlchemy 2.x conventions

- Every route + service method `async def`. No sync paths.
- Engine: `create_async_engine("postgresql+asyncpg://...", pool_pre_ping=True)`.
- Sessions: `async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)`.
- `Mapped[T]` + `mapped_column(...)` only.
- Pydantic v2: `ConfigDict(from_attributes=True, str_strip_whitespace=True)` for response; `ConfigDict(extra="forbid")` for request.
- `model_dump()`, `model_validate()`, `EmailStr` (requires `pydantic[email]`).
- Queries via `select(...)`, `update(...)`, `delete(...)` — no raw SQL strings.

### 1.5 Frontend toolchain (locked)

| Layer | Choice | Version |
|---|---|---|
| Build | Vite | 5.x |
| Language | TypeScript (strict) | 5.x |
| UI runtime | React | 18.x |
| Components | shadcn/ui (Radix + Tailwind) | latest |
| Styling | Tailwind CSS | 3.x |
| Server state | TanStack Query | v5 |
| Forms | react-hook-form + @hookform/resolvers | latest |
| Client validation | Zod | 3.x |
| Table | @tanstack/react-table (via shadcn DataTable wrapper) | 8.x |
| Test runner | Vitest + Testing Library | latest |
| Mock server | MSW | 2.x |

NOT introduced (Gate-2 lock): Redux, Zustand, Next.js, React Router (single route), styled-components, axios.

---

## 2. File tree (final — both sides)

```
migrations/crud/generated/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                          # FastAPI app factory + lifespan + exception handlers
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py                    # Settings (pydantic-settings)
│   │   │   └── logging.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                      # DeclarativeBase
│   │   │   ├── engine.py                    # init_engine / dispose_engine / get_session
│   │   │   └── migrations/
│   │   │       ├── env.py                   # Alembic env (async)
│   │   │       ├── script.py.mako
│   │   │       └── versions/0001_init_users.py
│   │   └── modules/
│   │       ├── __init__.py
│   │       └── users/
│   │           ├── __init__.py
│   │           ├── models.py                # SQLAlchemy User
│   │           ├── schemas.py               # Pydantic DTOs
│   │           ├── errors.py                # UserNotFound, EmailAlreadyExists
│   │           ├── service.py               # UserService
│   │           ├── router.py                # 5 endpoints
│   │           └── dependencies.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── unit/{test_schemas.py, test_service.py}
│   │   ├── integration/{test_list_users.py, test_create_user.py, test_get_user.py,
│   │   │                test_update_user.py, test_delete_user.py, test_health.py}
│   │   └── regression/test_security_regressions.py
│   ├── alembic.ini · pyproject.toml · requirements.txt · Dockerfile · docker-compose.yml · .env.example · README.md
│   └── (~38 files total)
└── frontend/
    ├── src/
    │   ├── main.tsx · App.tsx · index.css · vite-env.d.ts
    │   ├── pages/UsersPage.tsx
    │   ├── components/
    │   │   ├── PageHeader.tsx
    │   │   ├── UsersDataTable.tsx
    │   │   ├── AddEditDialog.tsx · UserForm.tsx
    │   │   ├── DeleteAlertDialog.tsx
    │   │   ├── EmptyState.tsx · ErrorState.tsx · LoadingSkeleton.tsx
    │   │   └── ui/ (shadcn primitives: button, dialog, alert-dialog, input, label, form,
    │   │           table, toast, toaster, skeleton, use-toast)
    │   ├── api/{client.ts, users.ts}
    │   ├── hooks/useUsers.ts
    │   ├── lib/{schemas.ts, problem.ts, utils.ts}
    │   └── types/user.ts
    ├── tests/
    │   ├── setup.ts · msw/{handlers.ts, server.ts}
    │   ├── UsersPage.test.tsx
    │   ├── UsersDataTable.test.tsx
    │   ├── AddEditDialog.test.tsx
    │   ├── DeleteAlertDialog.test.tsx
    │   └── api-client.test.ts
    ├── public/favicon.svg · index.html
    ├── package.json · tsconfig.json · tsconfig.node.json · vite.config.ts
    ├── tailwind.config.ts · postcss.config.js · components.json · vitest.config.ts
    ├── .env.example · .eslintrc.cjs · .prettierrc · Dockerfile · README.md
    └── (~53 files total)
```

**Counts:** Backend 38 files (14 logic + 10 tests + 14 scaffold). Frontend 53 files (9 custom components/pages + 9 logic + 11 shadcn primitives + 7 tests + 17 scaffold). **Grand total: 91 files**, of which **23 are load-bearing logic** (14 backend + 9 frontend).

---

## 3. PostgreSQL schema + Alembic migration

### 3.1 Target DDL (matches Comprehension §6.1)

```sql
CREATE TABLE users (
    id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  VARCHAR(100) NOT NULL,
    age   SMALLINT     NOT NULL,
    email VARCHAR(100) NOT NULL,
    CONSTRAINT uq_users_email     UNIQUE (email),
    CONSTRAINT ck_users_age_range CHECK (age >= 0 AND age <= 150)
);
```

### 3.2 Alembic env.py (async)

- Imports `app.db.base.Base` + `app.modules.users.models` (registers User on metadata).
- Reads `CRUD_DATABASE_URL` env var; falls back to `alembic.ini`.
- Online mode: async via `async_engine_from_config`, `connection.run_sync(do_run_migrations)`.
- `target_metadata = Base.metadata`. `compare_type=True`, `compare_server_default=True`.

### 3.3 `0001_init_users.py`

Upgrade:
1. `op.create_table("users", ...)` — 4 cols + Identity PK.
2. `op.create_unique_constraint("uq_users_email", "users", ["email"])`.
3. `op.create_check_constraint("ck_users_age_range", "users", "age >= 0 AND age <= 150")`.

Downgrade reverses. Mandatory traceability header at top citing BR-C-04, BR-C-06, BR-C-11.

---

## 4. SQLAlchemy User model

`app/modules/users/models.py`:

| Attribute | Type | Column args | BR-C |
|---|---|---|---|
| `id` | `Mapped[int]` | `mapped_column(Integer, Identity(always=True), primary_key=True)` | BR-C-07 |
| `name` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` | BR-C-06 |
| `age` | `Mapped[int]` | `mapped_column(SmallInteger, nullable=False)` | BR-C-04 |
| `email` | `Mapped[str]` | `mapped_column(String(100), nullable=False)` | BR-C-05, BR-C-11 |

`__tablename__ = "users"`. `__table_args__ = (UniqueConstraint("email", name="uq_users_email"), CheckConstraint("age >= 0 AND age <= 150", name="ck_users_age_range"))`.

`__repr__` returns `f"<User id={self.id} email={self.email!r}>"`. 8-line traceability header citing BR-C-04, 05, 06, 07, 11.

---

## 5. Pydantic schemas

`app/modules/users/schemas.py`:

### 5.1 `UserBase` — `ConfigDict(str_strip_whitespace=True, extra="forbid")`

| Field | Constraint |
|---|---|
| `name: str` | `Field(..., min_length=1, max_length=100)` |
| `age: int` | `Field(..., ge=0, le=150, strict=True)` |
| `email: EmailStr` | `Field(..., max_length=100)` |

### 5.2-5.4

- `UserCreate(UserBase)` — for `POST /api/users`
- `UserUpdate(UserBase)` — for `PUT /api/users/{id}` — `extra="forbid"` rejects body-side `id`
- `UserRead(UserBase)` — adds `id: int`; `ConfigDict(from_attributes=True, str_strip_whitespace=True)`

### 5.5 `ProblemDetail` (RFC 9457) — `ConfigDict(extra="allow")`

| Field | Type | Default |
|---|---|---|
| `type` | `str` | `"about:blank"` |
| `title` | `str` | required |
| `status` | `int` | required |
| `detail` | `str \| None` | None |
| `instance` | `str \| None` | None |
| `errors` | `list[dict] \| None` | None (only on 422) |

### 5.6 `HealthResponse` — `status: Literal["ok"]`, `service="crud"`, `version: str`

---

## 6. UserService (business-logic layer)

`app/modules/users/service.py` — class `UserService`, constructor takes logger; `AsyncSession` per call. Traceability header cites BR-C-01, 02, 03, 04, 05, 06, 07, 08, 11.

### 6.1 `list_users(self, db: AsyncSession) -> list[User]`
- SQL: `select(User).order_by(User.id.desc())`; `.scalars().all()`.
- BR-C: 01, 02.

### 6.2 `create_user(self, payload: UserCreate, db: AsyncSession) -> User`
1. Construct `User(...)`. `db.add(user)`. `await db.flush()` (forces UNIQUE check).
2. On `IntegrityError` (uq_users_email): `await db.rollback()`; raise `EmailAlreadyExists(payload.email)`.
3. `await db.commit()`; `await db.refresh(user)`; return user.
- Errors: `EmailAlreadyExists` → 409.
- BR-C: 11.

### 6.3 `get_user(self, user_id: int, db: AsyncSession) -> User`
- `result = await db.execute(select(User).where(User.id == user_id))`. `scalar_one_or_none()`. If None, raise `UserNotFound(user_id)`.
- BR-C: 07.

### 6.4 `update_user(self, user_id: int, payload: UserUpdate, db: AsyncSession) -> User`
1. Fetch via `get_user` — propagates `UserNotFound`.
2. Assign 3 fields (never `id`).
3. `await db.flush()`. On `IntegrityError`: rollback; re-fetch row by email; if it's the same `user_id` → not a conflict (self-collision per AC-11c); else raise `EmailAlreadyExists`.
4. Commit + refresh + return.
- BR-C: 03, 04, 05, 06, 07, 11.

### 6.5 `delete_user(self, user_id: int, db: AsyncSession) -> None`
- Fetch via `get_user`; `await db.delete(user)`; `await db.commit()`.
- BR-C: 08.

### 6.6 `errors.py`
```python
class UsersError(Exception): ...
class UserNotFound(UsersError):
    def __init__(self, user_id: int): ...
class EmailAlreadyExists(UsersError):
    def __init__(self, email: str): ...
```
Each carries `.title`, `.status`, `.detail` properties.

---

## 7. FastAPI router

`app/modules/users/router.py` — `router = APIRouter(prefix="/api/users", tags=["users"])`. Traceability header cites BR-C-01, 02, 07, 08, 09, 11.

### 7.1 `GET /api/users` → 200, `list[UserRead]`. BR-C 01, 02.
### 7.2 `POST /api/users` → 201, `UserRead`, sets `Location` header. Errors 409, 422. BR-C 03, 04, 05, 06, 11.
### 7.3 `GET /api/users/{user_id}` → 200, `UserRead`. 404. BR-C 07.
### 7.4 `PUT /api/users/{user_id}` → 200, `UserRead`. 404, 409, 422. BR-C 03–07, 11.
### 7.5 `DELETE /api/users/{user_id}` → 204 No Content. 404. BR-C 08, 09.

### 7.6 Exception handlers (registered on `app` in `main.py`)

- `UserNotFound` → 404 ProblemDetail (title `"User not found"`).
- `EmailAlreadyExists` → 409 ProblemDetail (title `"Email already exists"`).
- `RequestValidationError` → 422 ProblemDetail with `errors=[{loc, msg, type}]` from `exc.errors()`.
- Fallback `Exception` → 500 ProblemDetail (no stack-trace leakage).

`GET /api/healthz` → `HealthResponse` registered on the `app` (not the users router).

---

## 8. Configuration + bootstrap

### 8.1 `Settings` (`app/core/config.py`)

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRUD_", env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://crud:crud@localhost:5432/crud"
    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"
    api_prefix: str = "/api"
    version: str = "0.1.0"
    json_logs: bool = False
```

Validator: `database_url` must start with `postgresql+asyncpg://` or `sqlite+aiosqlite://`.

### 8.2 `core/logging.py` — `configure_logging(level, json_logs)`.

### 8.3 `db/engine.py` — module-level engine + sessionmaker. `init_engine`, `dispose_engine`, `get_sessionmaker`. `get_session()` is the FastAPI dependency (`AsyncIterator[AsyncSession]` with rollback on exception).

### 8.4 `db/base.py` — `class Base(DeclarativeBase): pass`.

### 8.5 `modules/users/dependencies.py` — `init_user_service`, `get_user_service`, `set_settings` (for tests).

### 8.6 `app/main.py` — `create_app(settings)`:
- `FastAPI(title="CRUD Users", openapi_url="/api/openapi.json", docs_url="/api/docs", lifespan=_lifespan)`
- `CORSMiddleware(allow_origins=settings.cors_origins, allow_methods=["GET","POST","PUT","DELETE","OPTIONS"], allow_headers=["Content-Type","Accept"])`
- Register exception handlers, include router, register `/api/healthz`.
- Module-level `app = create_app()` for `uvicorn app.main:app`.

---

## 9. React frontend

### 9.2 Component specs

#### 9.2.1 `UsersPage` (`src/pages/UsersPage.tsx`)
State (single useState cluster per Comprehension §5.2):
```ts
const [addDialogOpen, setAddDialogOpen] = useState<boolean>(false);
const [editingUser,   setEditingUser]   = useState<User | null>(null);
const [deletingUser,  setDeletingUser]  = useState<User | null>(null);
```
Hooks: `useUsersQuery`, `useCreateUser`, `useUpdateUser`, `useDeleteUser`, `useToast`.

Render:
- `isLoading` → `<LoadingSkeleton rows={5}/>`
- `isError` → `<ErrorState onRetry={refetch}/>`
- `data.length === 0` → `<EmptyState onAddClick={handleAddClick}/>`
- else → `<UsersDataTable rows={data} onEdit onDelete/>` + `<AddEditDialog key={editingUser?.id ?? "add"} .../>` + `<DeleteAlertDialog .../>`

#### 9.2.2 `PageHeader` — `<h1>Users</h1>` + spinner if refetching + `<Button>Add User</Button>`.

#### 9.2.3 `UsersDataTable` — wraps shadcn `<Table>` + `@tanstack/react-table`. Columns: id, name, age, email, actions. Default sort `[{id:"id", desc:true}]`. Action buttons have `aria-label="Edit ${name}"` / `aria-label="Delete ${name}"`.

#### 9.2.4 `AddEditDialog`
```ts
interface AddEditDialogProps {
  open: boolean;
  mode: "add" | "edit";
  user?: User;
  submitting: boolean;
  serverError?: ProblemDetailParsed | null;
  onClose: () => void;
  onSubmit: (values: UserFormValues) => void;
}
```
- Wraps shadcn `<Dialog>` + `<DialogContent>` + `<DialogHeader>` + `<DialogTitle>` + `<DialogDescription>`.
- Title "Add user" or "Edit user" by mode.
- Body: `<UserForm defaultValues={...} onSubmit={onSubmit} submitting={submitting} error={serverError}/>`.
- When `submitting`, `onOpenChange` blocks `false` (ESC/overlay can't dismiss).
- Parent forces remount via `key={editingUser?.id ?? "add"}` — Gate-2 priority #4.

#### 9.2.5 `UserForm`
```ts
interface UserFormProps {
  defaultValues?: Partial<UserFormValues>;
  submitting: boolean;
  error?: ProblemDetailParsed | null;
  onSubmit: (values: UserFormValues) => void;
}
```
- `useForm<UserFormValues>({ resolver: zodResolver(userFormSchema), defaultValues, mode: "onBlur" })`.
- 3 `<FormField>` rows: `name` (text, maxLength=100), `age` (number, min=0, max=150, step=1), `email` (email, maxLength=100).
- On server `error?.errors`: `useEffect` calls `setError(loc[1], { message })` per field.
- Submit button shows spinner when `submitting`.

#### 9.2.6 `DeleteAlertDialog`
```ts
interface DeleteAlertDialogProps {
  open: boolean;
  user: User | null;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}
```
- Wraps shadcn `<AlertDialog>` + footer with Cancel + destructive-variant Confirm.
- Description: `"Are you sure you want to delete ${user.name}? This cannot be undone."` (BR-C-10 AC-10e).
- Destructive button uses `bg-destructive`. Both disabled when `submitting`.

#### 9.2.7-9 `EmptyState`, `ErrorState`, `LoadingSkeleton` — Lucide icons, headlines, CTAs.

### 9.3 API client (`src/api/users.ts`)

```ts
import { request } from "./client";
import type { User } from "@/types/user";
import type { UserFormValues } from "@/lib/schemas";

export async function listUsers(): Promise<User[]>;
export async function getUser(id: number): Promise<User>;
export async function createUser(values: UserFormValues): Promise<User>;
export async function updateUser(id: number, values: UserFormValues): Promise<User>;
export async function deleteUser(id: number): Promise<void>;
```

`client.ts::request<T>(method, path, body?)` parses RFC-9457 `application/problem+json` into typed `ApiError(status, title, detail, errors)`. Returns `undefined` on 204.

### 9.4 React Query setup (`src/hooks/useUsers.ts`)

Query keys: `users.all = ["users"] as const`. Query: `useUsersQuery`. Mutations: `useCreateUser`, `useUpdateUser`, `useDeleteUser`. All mutations `onSuccess` → `queryClient.invalidateQueries({ queryKey: users.all })`. `useUsersQuery` uses `keepPreviousData: true`.

### 9.5 Zod schema (`src/lib/schemas.ts`) — mirrors Pydantic 1:1

```ts
export const userFormSchema = z.object({
  name:  z.string().trim().min(1, "Name is required.").max(100, "Name is too long (max 100)."),
  age:   z.coerce.number({ invalid_type_error: "Age must be a whole number." })
              .int("Age must be a whole number.")
              .min(0, "Age cannot be negative.")
              .max(150, "Age cannot exceed 150."),
  email: z.string().trim().email("Enter a valid email.").max(100, "Email is too long (max 100)."),
});
export type UserFormValues = z.infer<typeof userFormSchema>;
```

### 9.6 Hand-written TS types (`src/types/user.ts`)

```ts
export interface User { id: number; name: string; age: number; email: string; }
```

`ProblemDetailParsed` (in `src/lib/problem.ts`):
```ts
export interface ProblemFieldError { field: string; message: string; type: string; }
export interface ProblemDetailParsed { status: number; title: string; detail?: string; instance?: string; errors: ProblemFieldError[]; }
export function parseProblemDetail(body: unknown, status: number): ProblemDetailParsed;
```

`openapi-typescript` auto-gen deferred (OQ-P-001).

### 9.7 shadcn install commands

```bash
npx shadcn@latest init
npx shadcn@latest add button dialog alert-dialog input label form table toast skeleton
```

`tailwind.config.ts` extends with shadcn `theme.extend.colors`. `vite.config.ts` configures `@` → `src` alias and dev-proxy `/api` → `http://localhost:8000`.

---

## 10. Build order

### Backend phases
- **A1** Foundation: pyproject, requirements, Dockerfile, docker-compose, .env.example, README, init markers, core/config, core/logging, db/base.
- **A2** Persistence: modules/users/models, db/engine, alembic.ini, env.py, script.py.mako, 0001_init_users.py.
- **B1** Schemas + errors: schemas.py, errors.py.
- **B2** Service: service.py.
- **C1** Router + deps: dependencies.py, router.py.
- **C2** App composition: main.py.
- **T1** Tests: conftest, unit, integration, regression.

### Frontend phases
- **F1** Toolchain: package.json, tsconfig, vite.config, tailwind/postcss config, components.json, index.html, main.tsx shell, index.css, vitest.config, eslint/prettier. Run `npx shadcn add ...`.
- **F2** Logic (no JSX): types/user, lib/schemas, lib/problem, lib/utils, api/client, api/users, hooks/useUsers.
- **F3** Components + page: PageHeader → EmptyState → ErrorState → LoadingSkeleton → UserForm → AddEditDialog → DeleteAlertDialog → UsersDataTable → UsersPage → App → main.tsx wiring.
- **F4** Tests: setup.ts, msw/handlers, msw/server, 5 test files.

Backend and frontend parallel after A2 (API contract locked in §7 + form schema in §9.5).

---

## 11. Test plan

### 11.1 Backend

Runner: pytest + pytest-asyncio (auto) + httpx.AsyncClient against `create_app(test_settings)`. Test DB sqlite+aiosqlite:///:memory: for unit/integration. PG only for parity in CI.

Fixtures: `event_loop`, `settings`, `app`, `client`, `seed_users`.

Test files (per BR-C):
- `test_list_users.py`: empty list, ORDER BY id DESC, no side effect, content-type — BR-C-01, 02
- `test_create_user.py`: happy + Location header, 422 missing/whitespace/age-range/email-format/length boundaries, 409 dup email, ProblemDetail shape — BR-C-03, 04, 05, 06, 11 (18 cases)
- `test_get_user.py`: existing, missing (404), non-int id (422) — BR-C-07
- `test_update_user.py`: happy, missing (404), other-email (409), own-email (200 self-collision), id-in-body (422), full validation matrix — BR-C-03..07, 11
- `test_delete_user.py`: happy (204 no body), missing (404), get-after-delete (404), list-excludes-row, GET-on-delete-route (404), no-mutation-on-GET — BR-C-08, 09
- `test_health.py`: 200 ok
- `test_security_regressions.py`: SQL-injection in path id (422), XSS payload stored literally (RF-003), GET /delete (404)
- Unit: `test_schemas.py`, `test_service.py` (mock AsyncSession)

### 11.2 Frontend

Runner: vitest + jsdom + Testing Library + MSW.

- `UsersDataTable.test.tsx`: rows ordered desc, edit/delete buttons fire correct callbacks, aria-labels present
- `AddEditDialog.test.tsx`: title by mode, initial focus on name, Zod errors per field, age boundaries, server 422 → inline errors, server 409 → email inline error, ESC blocked when submitting
- `DeleteAlertDialog.test.tsx`: not auto-confirmed, Cancel/Confirm callbacks, ESC fires Cancel, double-click idempotent, destructive variant red, "cannot be undone" text
- `UsersPage.test.tsx`: composite — MSW empty → EmptyState, create flow → invalidate + close, MSW 500 → ErrorState + retry
- `api-client.test.ts`: 200 parse, 204 → undefined, ProblemDetail → ApiError, parseProblemDetail field mapping

### 11.3 BR-C coverage matrix (11/11)

| BR-C | Backend test | Frontend test |
|---|---|---|
| BR-C-01 newest-first | test_list_orders_by_id_desc | UsersDataTable::renders desc |
| BR-C-02 list side-effect-free | test_list_no_side_effect | (indirect via api-client) |
| BR-C-03 fields mandatory + non-blank | test_create_missing_*, _whitespace_name | AddEditDialog::empty form |
| BR-C-04 age [0,150] | test_create_age_* (6 cases) | AddEditDialog::age=-1, =151 |
| BR-C-05 email format + length | test_create_email_* (3 cases) | AddEditDialog::invalid email |
| BR-C-06 name ≤100 | test_create_name_*_chars | AddEditDialog::maxLength smoke |
| BR-C-07 update preserves id; 404 on miss | test_get_missing, test_update_missing | UsersPage::404 toast |
| BR-C-08 delete permanent | test_delete_happy, test_delete_then_get_404 | UsersPage::delete success |
| BR-C-09 DELETE verb only | test_get_delete_route_404 | DeleteAlertDialog::confirm fires DELETE |
| BR-C-10 UI delete gate | N/A — UI rule | DeleteAlertDialog::two-step gate |
| BR-C-11 email UNIQUE → 409 | test_create_dup_email, test_update_other/own | AddEditDialog::409 inline |

---

## 12. Dual-run harness contract

### 12.1 Input matrix

| # | Scenario | Legacy URL | New API call |
|---|---|---|---|
| H1 | List 3 seed users | GET /index.php | GET /api/users |
| H2 | Add user "Alice 30 a@b.com" | POST /addAction.php | POST /api/users |
| H3 | Edit user 2 | POST /editAction.php | PUT /api/users/2 |
| H4 | Delete user 3 | GET /delete.php?id=3 | DELETE /api/users/3 |
| E1 | Empty name | POST /addAction.php | POST /api/users |
| E2 | Duplicate email | POST /addAction.php | POST /api/users (→409) |
| E3 | Edit nonexistent 99 | POST /editAction.php | PUT /api/users/99 (→404) |
| E4 | SQL injection in delete | GET /delete.php?id=1;DROP TABLE | DELETE /api/users/<bad> (→422) |

### 12.2 Screenshot capture (load-bearing demo artefact)

**Legacy frames** (Playwright against PHP container):
1. `legacy_01_index_3rows.png` — populated table
2. `legacy_02_add_form.png` — bare HTML form
3. `legacy_03_add_success.png` — green `<font>` success
4. `legacy_04_edit_form_id2.png` — pre-filled inputs
5. `legacy_05_edit_success.png`
6. `legacy_06_delete_confirm.png` — JS confirm() dialog
7. `legacy_07_index_after_delete.png`
8. `legacy_08_validation_error.png` — red `<font>`

**New-stack frames** (Playwright against React app):
1. `new_01_list_3rows.png` — populated DataTable
2. `new_02_empty_state.png` — EmptyState with CTA
3. `new_03_add_dialog_open.png`
4. `new_04_add_validation_inline.png` — Zod errors visible
5. `new_05_edit_dialog_with_data.png` — pre-filled via key={id}
6. `new_06_delete_alert_open.png` — shadcn AlertDialog
7. `new_07_toast_after_delete.png`
8. `new_08_email_conflict_inline.png` — 409 inline

Storage: `migrations/crud/screenshots/{legacy,new}/*.png`.

### 12.3 Disposition

- **Legacy** = baseline (golden) — for mosaic only, not byte-compared.
- **New** = transformation; success qualitative (shadcn-skinned, dialog-driven).
- **What's byte-compared:** API response payloads. For each happy-path scenario, harness records `(legacy_html_extract, new_json_payload)`. BeautifulSoup pulls `<td>` cells from legacy; `json.loads` on new payload; compare as sets of `(name, age, email)` tuples.
- **Gate 6 acceptance:**
  - 16 screenshots captured
  - 4 happy-path payloads match modulo formatting
  - 4 error cases produce documented envelopes on new stack
  - Mosaic ≤4 MiB

### 12.4 Harness execution

`docker-compose.dualrun.yml` brings up: postgres:16, mysql:8, crud-backend, crud-frontend (nginx serving dist/), php:8.2 with source RO-mounted. Both DBs seeded from `dual-run/seed.sql` and `seed-pg.sql` (5 deterministic rows).

`screenshot-runner.py` (Playwright) orchestrates: bring stack up → drive 8 legacy + 8 new scenarios → render mosaic → assert payload parity → write `reports/dual-run-001.json`.

---

## 13. Cockpit playback contract

Per-stage `doneMeta`:
```json
{
  "stage": "planning",
  "artefact": "output/planning/planning-001.md",
  "loc": 1480,
  "backend_files": 38,
  "frontend_files": 53,
  "br_mapped": 11,
  "self_check": "PASS",
  "before_screenshot": null,
  "after_screenshot": null
}
```

For Stage 7, `doneMeta.screenshot_pairs[]` has 8 entries `{scenario, legacy, new, payload_match}`. Cockpit "before/after" panel renders these pairs.

For Stage 4 (CodeGen), `doneMeta` adds `files_generated`, `traceability_headers_present`.

For Stage 6 (TestGen), `doneMeta` adds `tests_generated`, `assertions`, `br_c_per_test_avg`.

Single `cockpit/manifest.json` aggregates all stages.

---

## 14. Self-check matrix

### 14.1 BR-C coverage (11/11 PASS)

| BR-C | Backend location | Frontend location | Test | Result |
|---|---|---|---|---|
| BR-C-01 | service.py::list_users + router.py::list_users_route | UsersDataTable.tsx default sort + useUsersQuery | test_list_orders_by_id_desc + UsersDataTable.test.tsx | ✅ |
| BR-C-02 | service.py::list_users (pure SELECT) | useUsersQuery (GET only) | test_list_no_side_effect | ✅ |
| BR-C-03 | schemas.py::UserBase (min_length=1, str_strip_whitespace) | lib/schemas.ts (trim().min(1)) + UserForm errors | test_create_missing_* + AddEditDialog.test.tsx | ✅ |
| BR-C-04 | schemas.py::UserBase.age (ge=0, le=150, strict) + DB CheckConstraint | lib/schemas.ts.age + Input min/max | test_create_age_* (6 cases) + AddEditDialog | ✅ |
| BR-C-05 | schemas.py::UserBase.email (EmailStr, max_length=100) | lib/schemas.ts.email + Input type=email | test_create_email_* + AddEditDialog | ✅ |
| BR-C-06 | schemas.py::UserBase.name (max_length=100) + DB VARCHAR(100) | lib/schemas.ts.name.max(100) + maxLength | test_create_name_*_chars | ✅ |
| BR-C-07 | service.py::update_user + get_user + errors.UserNotFound | useUpdateUser invalidation + UsersPage 404 toast | test_update_missing_user_404 + test_get_missing_404 | ✅ |
| BR-C-08 | service.py::delete_user | useDeleteUser invalidates | test_delete_happy + test_delete_then_get_404 | ✅ |
| BR-C-09 | router.py::delete_user_route (only DELETE) | api/users.ts::deleteUser method DELETE | test_get_delete_route_does_not_exist | ✅ |
| BR-C-10 | N/A — UI rule (BR-C-09 is prerequisite) | DeleteAlertDialog + UsersPage state gate | DeleteAlertDialog.test.tsx (5 cases) | ✅ |
| BR-C-11 | models.py UNIQUE + service.py IntegrityError → 409 | UserForm 409 → inline email | test_create_dup_email + test_update_other/own + AddEditDialog | ✅ |

### 14.2 Risk-flag coverage (8 / 8)

| RF | Disposition | Implementation | Regression test |
|---|---|---|---|
| RF-001 SQL injection edit | Auto-resolved | FastAPI typed `id: int` + SQLAlchemy params | test_sql_injection_payload_in_path_id |
| RF-002 SQL injection delete | Auto-resolved | Same | Same |
| RF-003 Stored XSS list | Auto-resolved | React text-node escaping | test_xss_payload_stored_literally |
| RF-004 Stored XSS form attr | Auto-resolved | React controlled value={...} | Same |
| RF-005 HTML inj unquoted id | N/A | id is path param, never DOM | Documented |
| RF-006 CSRF | Deferred (Phase 5 with auth) | n/a | Recorded |
| RF-007 Delete via GET | Active fix | router only registers DELETE | test_get_delete_route_404 |
| RF-008 Hardcoded creds | Active fix | pydantic-settings + .env.example | test_config.py::test_database_url_from_env |

### 14.3 Gate-1 + Gate-2 locks honoured

| Lock | Honoured |
|---|---|
| email UNIQUE | §3 DDL, §4 model, §6 service, §7 router 409 |
| age 0..150 | §3 CHECK, §4 SmallInteger, §5 Field(ge=0, le=150) |
| table=users | §3, §4 __tablename__ |
| no pagination | §7 no ?limit/?offset; §9.3 no pagination param |
| no auth | No middleware, no JWT, no login |
| no created_at/updated_at | §3 DDL, §4 model (4 columns only) |

**Self-check: 37/37 PASS** (11 BR-C × 3 cells + 8 RF rows + 6 locks).

---

## 15. Open Questions (residual)

| OQ | Question | Default |
|---|---|---|
| OQ-P-001 | Auto-gen TS types from OpenAPI via `openapi-typescript`? | Defer to Phase 5; hand-written User type is one field-list |
| OQ-P-002 | Cockpit per-file legacy/new diff view? | Defer to Stage 8 design |
| OQ-P-003 | UserUpdate body-side `id` — silently drop vs 422-reject? | Keep `extra="forbid"` (stricter; matches REST hygiene) |

---

## 16. Handoff to CodeGen

Start with **Phase A1** — no encode module to seed (unlike shorty); first artefacts are pyproject + core/config + db/base, then models in A2. After A2, backend and frontend may proceed in parallel — frontend F1 has zero dependency on backend B1+ because the API contract is locked in §7 and the form schema in §9.5. Self-Review runs after every phase and rejects any file missing its 8-line traceability header or any layer-firewall violation per §1.3. The dual-run screenshot harness in §12 is the demo's load-bearing artefact — CodeGen must NOT introduce any `dangerouslySetInnerHTML`, raw `<table>` outside the shadcn `<Table>` primitive, or non-controlled form inputs.
