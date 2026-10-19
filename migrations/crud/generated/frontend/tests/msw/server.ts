// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: n/a — test scaffolding
// LEGACY: n/a — scaffold
// COMPONENT: tests/msw/server
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
