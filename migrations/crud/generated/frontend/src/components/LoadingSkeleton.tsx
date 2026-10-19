// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: n/a — UI affordance (Comprehension §5.6)
// LEGACY: n/a — PHP blocked on synchronous render
// COMPONENT: components/LoadingSkeleton
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import { Skeleton } from "@/components/ui/skeleton";

interface LoadingSkeletonProps {
  rows?: number;
}

export function LoadingSkeleton({ rows = 5 }: LoadingSkeletonProps) {
  return (
    <div className="space-y-2" role="status" aria-label="Loading users">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}

export default LoadingSkeleton;
