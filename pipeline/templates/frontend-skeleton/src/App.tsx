// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: n/a — single-route shell
// LEGACY: n/a — scaffold (PHP had per-file routes)
// COMPONENT: App
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import UsersPage from "@/pages/UsersPage";

// Single route — Gate-2 lock: no React Router.
export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <UsersPage />
    </div>
  );
}
