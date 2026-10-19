// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-01, BR-C-10
// LEGACY: source/index.php:19-37
// COMPONENT: tests/UsersDataTable
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { UsersDataTable } from "@/components/UsersDataTable";
import type { User } from "@/types/user";

const ROWS: User[] = [
  { id: 3, name: "Charlie", age: 22, email: "charlie@example.com" },
  { id: 2, name: "Bob", age: 45, email: "bob@example.com" },
  { id: 1, name: "Alice", age: 30, email: "alice@example.com" },
];

describe("UsersDataTable", () => {
  it("BR-C-01: renders rows in supplied (descending) order", () => {
    render(<UsersDataTable rows={ROWS} onEdit={() => {}} onDelete={() => {}} />);
    const rowEls = screen.getAllByRole("row");
    // header + 3 rows = 4
    expect(rowEls).toHaveLength(4);
    expect(rowEls[1]).toHaveTextContent("Charlie");
    expect(rowEls[2]).toHaveTextContent("Bob");
    expect(rowEls[3]).toHaveTextContent("Alice");
  });

  it("Edit/Delete buttons carry per-row aria-label", () => {
    render(<UsersDataTable rows={ROWS} onEdit={() => {}} onDelete={() => {}} />);
    expect(screen.getByLabelText("Edit Alice")).toBeInTheDocument();
    expect(screen.getByLabelText("Delete Alice")).toBeInTheDocument();
    expect(screen.getByLabelText("Edit Charlie")).toBeInTheDocument();
  });

  it("a11y: every row's action buttons expose a concrete aria-label (WCAG 4.1.2)", () => {
    // Stage-6 a11y guard — guarantees no icon-only Edit/Delete button on
    // any rendered row is missing an aria-label attribute. Failing this
    // means an icon-only control would be unannounced by screen readers.
    render(<UsersDataTable rows={ROWS} onEdit={() => {}} onDelete={() => {}} />);
    for (const row of ROWS) {
      const editBtn = screen.getByLabelText(`Edit ${row.name}`);
      const delBtn = screen.getByLabelText(`Delete ${row.name}`);
      expect(editBtn).toBeInTheDocument();
      expect(delBtn).toBeInTheDocument();
      expect(editBtn.getAttribute("aria-label")).toBe(`Edit ${row.name}`);
      expect(delBtn.getAttribute("aria-label")).toBe(`Delete ${row.name}`);
    }
  });

  it("Edit button fires onEdit with the right user", async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn();
    render(
      <UsersDataTable rows={ROWS} onEdit={onEdit} onDelete={() => {}} />,
    );
    await user.click(screen.getByLabelText("Edit Bob"));
    expect(onEdit).toHaveBeenCalledOnce();
    expect(onEdit).toHaveBeenCalledWith(
      expect.objectContaining({ id: 2, name: "Bob" }),
    );
  });

  it("Delete button fires onDelete with the right user", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(
      <UsersDataTable rows={ROWS} onEdit={() => {}} onDelete={onDelete} />,
    );
    await user.click(screen.getByLabelText("Delete Charlie"));
    expect(onDelete).toHaveBeenCalledOnce();
    expect(onDelete).toHaveBeenCalledWith(
      expect.objectContaining({ id: 3, name: "Charlie" }),
    );
  });
});
