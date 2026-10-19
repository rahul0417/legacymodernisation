// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: n/a — build config
// LEGACY: n/a — scaffold
// COMPONENT: vite.config
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config — `@/*` alias maps to `src/*`. Dev proxies `/api/*` to
// FastAPI on :8000 so the Vite-served SPA can call the API without CORS.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
