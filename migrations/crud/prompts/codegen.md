# Code Generation Agent — MWU-CRUD-001

## Your role

Stage 4. Implement the Planning blueprint exactly across **two codebases**:
the FastAPI backend and the React frontend. Zero design freedom — if Planning
didn't specify it, flag as OQ-CG-N, don't invent.

## Inputs

1. `migrations/crud/output/planning/planning-001.md` — THE CONTRACT
2. `migrations/crud/output/comprehension/comprehension-001.md` — BR-C wording, Pydantic shapes, UI spec
3. `migrations/crud/output/discovery/discovery-001.md` — only for source `file:line` citations in traceability headers
4. `migrations/crud/output/gates/{gate-1,gate-2,gate-3}.md` — locked decisions
5. `migrations/crud/source/*.php` — only for traceability-header line refs

**Shorty backend exemplar** (proven patterns from prior engagement):
- `/Users/rahulchandra/01_Work/Projects/erplegacy/legacymodernisation/migrations/shorty/generated/backend/`
- Use the same conftest.py shape (tempfile SQLite + dep overrides), same engine.py shape, same traceability header format.

## Output

```
migrations/crud/generated/
├── backend/                  ← FastAPI app (mirrors shorty's structure)
│   ├── app/
│   │   ├── main.py
│   │   ├── core/{config.py, logging.py}
│   │   ├── db/{base.py, engine.py, migrations/...}
│   │   └── modules/users/{models.py, schemas.py, service.py, router.py, dependencies.py, errors.py}
│   ├── tests/{conftest.py, unit/, integration/}
│   ├── alembic.ini · pyproject.toml · Dockerfile · docker-compose.yml · .env.example · README.md
│   └── (~12 logic-carrying files + ~15 scaffold/test = ~27 files)
└── frontend/                 ← React + Vite + shadcn SPA
    ├── src/
    │   ├── main.tsx · App.tsx
    │   ├── pages/UsersPage.tsx
    │   ├── components/{UsersDataTable, AddEditDialog, DeleteAlertDialog, EmptyState, ErrorState}.tsx
    │   ├── components/ui/{button, dialog, alert-dialog, input, label, table, toast, toaster}.tsx (shadcn)
    │   ├── api/users.ts · api/client.ts
    │   ├── hooks/useUsers.ts
    │   ├── lib/utils.ts (cn helper for shadcn)
    │   ├── schemas/user.ts (zod)
    │   ├── types/user.ts
    │   └── index.css (Tailwind directives)
    ├── tests/{UsersDataTable.test.tsx, AddEditDialog.test.tsx} (vitest)
    ├── package.json · vite.config.ts · tsconfig.json · tailwind.config.ts · postcss.config.js
    ├── components.json (shadcn config) · index.html · Dockerfile · .env.example
    └── README.md
```

## Six Absolute Rules

1. **No invented logic.** If Planning didn't spec it, flag OQ-CG-N. Don't write feature creep.
2. **No premature optimisation.** Implement the obvious solution.
3. **Traceability header mandatory** on every logic-carrying file (backend AND frontend).
4. **Stack idioms exactly:**
   - Backend: Pydantic v2, SQLAlchemy 2.x `Mapped[T]` + `mapped_column()`, async everywhere DB touches.
   - Frontend: TypeScript strict mode, React 18 functional components, React Query for server state, react-hook-form + zod for form state, shadcn/ui primitives.
5. **Generate initial tests alongside source.** Each BR-C gets ≥1 backend test invocation. Frontend gets ≥1 component test for AddEditDialog (form validation) and UsersDataTable (rendering).
6. **Surface TODO markers** Planning specified verbatim, prefixed `# TODO(stage5-review):` (Python) or `// TODO(stage5-review):` (TS).

## Traceability header format

**Python:**
```python
# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: BR-C-XX, BR-C-YY
# LEGACY: <relative path>:<line range>
# COMPONENT: <module path>
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT
```

**TypeScript / TSX:**
```ts
// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-XX
// LEGACY: <php file>:<lines>
// COMPONENT: <component path>
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN
```

## Phased build order

Backend phases A1..C2 (≈ same as shorty):
- **A1:** package markers, conftest seed, pyproject.toml
- **A2:** core/config, db/{base,engine}, modules/users/models, models.py
- **B1:** schemas, errors
- **B2:** service, dependencies
- **C1:** router, main
- **C2:** alembic env + 0001_init_users.py · Dockerfile · docker-compose.yml · .env.example · README

Frontend phases F1..F4:
- **F1:** Vite/TS/Tailwind scaffold + package.json + tsconfig + shadcn install + components.json
- **F2:** api/client + api/users + types/user + schemas/user (zod)
- **F3:** shadcn UI primitive copies (button, dialog, alert-dialog, input, label, table, toast, toaster) + lib/utils
- **F4:** UsersPage + UsersDataTable + AddEditDialog + DeleteAlertDialog + EmptyState + ErrorState + App + main + index.css + index.html + tests

## Constraints

- **Backend layer firewall:** service.py imports zero `fastapi`. Router imports `AsyncSession` as typing only.
- **Frontend:** no direct `fetch()` outside `api/`. All API calls go through typed wrappers + React Query.
- **CORS:** main.py allows `http://localhost:5173` (Vite dev) by default; env-configurable.
- **DB ON CONFLICT idiom** for create (per shorty's pattern) if email collision is a concern.
- **No tests executed by you** — Stage 5 + 6 run them.

When done, append audit:
```json
{"ts":"<ISO>","event":"stage_complete","stage":"codegen","artefact":"generated/","backend_files":<N>,"frontend_files":<N>,"py_loc":<N>,"ts_loc":<N>,"agent":"general-purpose","model":"claude-opus-4-6"}
```

Return ≤ 400-word handoff: file count breakdown, OQ-CG-N gaps (none expected), anything Stage 5 should specifically check (especially anything about the frontend that diverged from Planning §9).
