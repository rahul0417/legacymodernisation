// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-07
// LEGACY: source/database.sql:5-11
// COMPONENT: types/user
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// Hand-written TS type mirroring the backend UserRead schema.
// OQ-P-001: openapi-typescript auto-gen deferred to Phase 5.

export interface User {
  id: number;
  name: string;
  age: number;
  email: string;
}
