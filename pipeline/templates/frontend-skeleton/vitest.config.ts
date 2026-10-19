// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: n/a — test runner config
// LEGACY: n/a — scaffold
// COMPONENT: vitest.config
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import path from "node:path";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    coverage: {
      reporter: ["text", "json", "html"],
    },
  },
});
