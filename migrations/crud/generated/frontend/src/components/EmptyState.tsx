// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: n/a — UI affordance (Comprehension §5.5)
// LEGACY: n/a — legacy index.php rendered empty <table> rows
// COMPONENT: components/EmptyState
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import { Users as UsersIcon } from "lucide-react";

import { Button } from "@/components/ui/button";

interface EmptyStateProps {
  onAddClick: () => void;
}

export function EmptyState({ onAddClick }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-md border border-dashed py-16 text-center">
      <UsersIcon
        className="mb-4 h-12 w-12 text-muted-foreground"
        aria-hidden="true"
      />
      <h2 className="text-lg font-semibold">No users yet.</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Add your first user to get started.
      </p>
      <Button onClick={onAddClick} className="mt-4">
        Add User
      </Button>
    </div>
  );
}

export default EmptyState;
