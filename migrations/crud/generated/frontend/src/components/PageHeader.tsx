// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: n/a — presentational
// LEGACY: source/index.php:15-18 (h2 + Add link)
// COMPONENT: components/PageHeader
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import { Loader2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";

interface PageHeaderProps {
  refetching?: boolean;
  onAddClick: () => void;
}

export function PageHeader({ refetching, onAddClick }: PageHeaderProps) {
  return (
    <header className="flex items-center justify-between border-b pb-4">
      <div className="flex items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight">Users</h1>
        {refetching ? (
          <Loader2
            className="h-4 w-4 animate-spin text-muted-foreground"
            aria-label="Refreshing"
          />
        ) : null}
      </div>
      <Button onClick={onAddClick} className="gap-2">
        <Plus className="h-4 w-4" aria-hidden="true" />
        Add User
      </Button>
    </header>
  );
}

export default PageHeader;
