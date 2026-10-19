# CRUD Users — React 18 + Vite + shadcn/ui frontend

This is the **MWU-CRUD-001 Stage 4 (CodeGen)** frontend output of the
modernisation pipeline. SPA companion to the FastAPI backend in
`../backend/`. Implemented against `planning-001.md §9` (locked).

## Stack

| Layer | Choice |
|---|---|
| Build | Vite 5 |
| Language | TypeScript 5 strict |
| UI runtime | React 18 |
| Components | shadcn/ui (Radix + Tailwind) |
| Styling | Tailwind 3 |
| Server state | TanStack Query v5 |
| Forms | react-hook-form + @hookform/resolvers + zod |
| Test runner | Vitest + Testing Library + MSW |

## Run locally

```bash
npm install
npm run dev      # Vite dev server on :5173, /api/* proxied to :8000
npm run build    # tsc --noEmit && vite build (outputs dist/)
npm test         # vitest
```

## File layout

```
src/
  main.tsx                # Vite entry — QueryClient + Toaster + <App/>
  App.tsx                 # Single-route shell → <UsersPage/>
  pages/UsersPage.tsx     # The only stateful page (modal cluster, mutations)
  components/
    PageHeader.tsx        # Title + spinner + Add User CTA
    UsersDataTable.tsx    # shadcn Table over rows (BR-C-01: server-sorted)
    AddEditDialog.tsx     # shadcn Dialog + remount-by-key
    UserForm.tsx          # RHF + zodResolver + 422/409 projection
    DeleteAlertDialog.tsx # shadcn AlertDialog (BR-C-10 two-step gate)
    EmptyState.tsx
    ErrorState.tsx
    LoadingSkeleton.tsx
    ui/                   # shadcn primitives — button, dialog, alert-dialog,
                          #   input, label, form, table, toast, toaster,
                          #   use-toast, skeleton
  api/
    client.ts             # fetch wrapper + ProblemDetail parser + ApiError
    users.ts              # 5 typed wrappers
  hooks/useUsers.ts       # TanStack Query: useUsersQuery + 3 mutations
  lib/
    schemas.ts            # Zod userFormSchema — mirrors Pydantic 1:1
    problem.ts            # parseProblemDetail → ProblemDetailParsed
    utils.ts              # cn() helper
  types/user.ts           # User interface
tests/
  setup.ts                # MSW bootstrap
  msw/{handlers,server}.ts
  UsersDataTable.test.tsx
  AddEditDialog.test.tsx
  DeleteAlertDialog.test.tsx
  UsersPage.test.tsx
  api-client.test.ts
```

## Layer firewall (Planning §1.3)

- Components MUST go through `src/hooks/*` — never call `src/api/*` directly.
- `src/api/*` MUST NOT import React.
- `src/lib/*` and `src/types/*` are pure (no React, no fetch).
- No raw `<table>` outside the shadcn `<Table>` primitive.
- No `dangerouslySetInnerHTML` anywhere — text-node escaping is the
  auto-resolution for RF-003 / RF-004.

## Phase 5 handoff items

- OQ-P-001: `openapi-typescript` auto-gen of `src/types/user.ts` from
  the backend's `/api/openapi.json`. Currently hand-written (one
  field-list).
- Stage 6 TestGen will expand `tests/*` to the full Planning §11.2
  matrix (~16 frontend interaction tests).
