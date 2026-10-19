// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-09, BR-C-10
// LEGACY: source/index.php:34 (onClick=confirm(...))
// COMPONENT: tests/DeleteAlertDialog
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DeleteAlertDialog } from "@/components/DeleteAlertDialog";

const TARGET = { id: 1, name: "Alice", age: 30, email: "alice@example.com" };

describe("DeleteAlertDialog (BR-C-10 two-step gate)", () => {
  it("AC-10e: shows 'cannot be undone' wording", () => {
    render(
      <DeleteAlertDialog
        open
        user={TARGET}
        submitting={false}
        onCancel={() => {}}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getByText(/Delete user\?/i)).toBeInTheDocument();
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument();
    expect(screen.getByText(/Alice/)).toBeInTheDocument();
  });

  it("AC-10a: does NOT auto-fire onConfirm just because it opened", () => {
    const onConfirm = vi.fn();
    render(
      <DeleteAlertDialog
        open
        user={TARGET}
        submitting={false}
        onCancel={() => {}}
        onConfirm={onConfirm}
      />,
    );
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("Cancel fires onCancel", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <DeleteAlertDialog
        open
        user={TARGET}
        submitting={false}
        onCancel={onCancel}
        onConfirm={() => {}}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("AC-10b: explicit Delete click fires onConfirm exactly once", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <DeleteAlertDialog
        open
        user={TARGET}
        submitting={false}
        onCancel={() => {}}
        onConfirm={onConfirm}
      />,
    );
    await user.click(screen.getByRole("button", { name: /^Delete$/i }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("submitting=true disables both buttons (BR-C-10 rapid double-click guard)", () => {
    render(
      <DeleteAlertDialog
        open
        user={TARGET}
        submitting={true}
        onCancel={() => {}}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /Cancel/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Delete/i })).toBeDisabled();
  });
});
