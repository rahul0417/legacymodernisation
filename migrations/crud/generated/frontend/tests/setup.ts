// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: n/a — test scaffolding
// LEGACY: n/a — scaffold
// COMPONENT: tests/setup
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./msw/server";

// Establish API mocking before tests, reset handlers between tests,
// close server after the suite. Standard MSW pattern.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
