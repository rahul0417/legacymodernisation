// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-01, BR-C-07, BR-C-08, BR-C-11
// LEGACY: source/index.php
// COMPONENT: tests/UsersPage
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import UsersPage from "@/pages/UsersPage";
import { resetStore, seed } from "./msw/handlers";

function renderWithClient(node: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>{node}</QueryClientProvider>,
  );
}

describe("UsersPage", () => {
  beforeEach(() => {
    resetStore();
  });

  it("renders EmptyState when the backend returns []", async () => {
    renderWithClient(<UsersPage />);
    expect(await screen.findByText(/No users yet/i)).toBeInTheDocument();
  });

  it("renders the DataTable when rows exist (BR-C-01: id DESC)", async () => {
    seed([
      { name: "Alice", age: 30, email: "alice@example.com" },
      { name: "Bob", age: 45, email: "bob@example.com" },
      { name: "Charlie", age: 22, email: "charlie@example.com" },
    ]);
    renderWithClient(<UsersPage />);
    // Charlie was seeded last → highest id → appears first.
    const charlieCell = await screen.findByText("Charlie");
    expect(charlieCell).toBeInTheDocument();
    const rows = await screen.findAllByRole("row");
    // header + 3
    expect(rows.length).toBeGreaterThanOrEqual(4);
    expect(rows[1]).toHaveTextContent("Charlie");
  });
});
