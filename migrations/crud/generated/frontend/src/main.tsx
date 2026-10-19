// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: n/a — Vite entry
// LEGACY: n/a — scaffold (PHP had no SPA mount)
// COMPONENT: main
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import { Toaster } from "@/components/ui/toaster";
import "./index.css";

// Single QueryClient for the whole app. Defaults follow TanStack
// guidance: no aggressive refetching, retries off for mutations.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
    mutations: {
      retry: 0,
    },
  },
});

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Root element #root missing from index.html");
}

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster />
    </QueryClientProvider>
  </React.StrictMode>,
);
