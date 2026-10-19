// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: n/a — UI utility helper
// LEGACY: n/a — scaffold
// COMPONENT: lib/utils
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// shadcn-canonical `cn` helper — merges Tailwind class names with
// last-write-wins precedence. Every shadcn primitive imports from here.

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
