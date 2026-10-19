// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-03, BR-C-04, BR-C-05, BR-C-06, BR-C-07, BR-C-11
// LEGACY: source/add.php, source/edit.php
// COMPONENT: components/AddEditDialog
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// shadcn Dialog wrapping <UserForm/>. Parent forces remount via
// `key={editingUser?.id ?? "add"}` so stale values never bleed across
// opens (Gate-2 priority #4).

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { UserForm } from "@/components/UserForm";
import type { User } from "@/types/user";
import type { ProblemDetailParsed } from "@/lib/problem";
import type { UserFormValues } from "@/lib/schemas";

export interface AddEditDialogProps {
  open: boolean;
  mode: "add" | "edit";
  user?: User | null;
  submitting: boolean;
  serverError?: ProblemDetailParsed | null;
  onClose: () => void;
  onSubmit: (values: UserFormValues) => void;
}

export function AddEditDialog({
  open,
  mode,
  user,
  submitting,
  serverError,
  onClose,
  onSubmit,
}: AddEditDialogProps) {
  const title = mode === "add" ? "Add user" : "Edit user";
  const description =
    mode === "add"
      ? "Create a new user record."
      : "Update this user's name, age, or email.";
  const submitLabel = mode === "add" ? "Add" : "Update";

  // Block ESC / overlay close while submitting (Comprehension §5.4 step 4).
  const handleOpenChange = (next: boolean) => {
    if (!next) {
      if (submitting) return;
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        onEscapeKeyDown={(e) => {
          if (submitting) e.preventDefault();
        }}
        onPointerDownOutside={(e) => {
          if (submitting) e.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <UserForm
          defaultValues={
            user
              ? { name: user.name, age: user.age, email: user.email }
              : undefined
          }
          submitting={submitting}
          error={serverError}
          submitLabel={submitLabel}
          onCancel={onClose}
          onSubmit={onSubmit}
        />
      </DialogContent>
    </Dialog>
  );
}

export default AddEditDialog;
