// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: n/a — UI affordance (Comprehension §5.6)
// LEGACY: n/a — PHP failed silently on DB errors
// COMPONENT: components/ErrorState
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

interface ErrorStateProps {
  onRetry: () => void;
  message?: string;
}

export function ErrorState({ onRetry, message }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-md border border-destructive/40 bg-destructive/5 py-16 text-center">
      <AlertTriangle
        className="mb-4 h-12 w-12 text-destructive"
        aria-hidden="true"
      />
      <h2 className="text-lg font-semibold">Couldn&apos;t load users.</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        {message ?? "Something went wrong. Please try again."}
      </p>
      <Button onClick={onRetry} variant="outline" className="mt-4">
        Retry
      </Button>
    </div>
  );
}

export default ErrorState;
