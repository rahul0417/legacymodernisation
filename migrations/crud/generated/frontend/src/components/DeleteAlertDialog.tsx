// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-09, BR-C-10
// LEGACY: source/index.php:34 (onClick=confirm(...))
// COMPONENT: components/DeleteAlertDialog
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// shadcn AlertDialog — BR-C-10 two-step gate. The destructive Confirm
// button triggers `onConfirm` only on an EXPLICIT second click; ESC,
// overlay, and Cancel all route through onCancel without firing the
// API request (AC-10a/c/d).

import { Loader2 } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { User } from "@/types/user";

export interface DeleteAlertDialogProps {
  open: boolean;
  user: User | null;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function DeleteAlertDialog({
  open,
  user,
  submitting,
  onCancel,
  onConfirm,
}: DeleteAlertDialogProps) {
  const handleOpenChange = (next: boolean) => {
    if (!next) {
      if (submitting) return;
      onCancel();
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete user?</AlertDialogTitle>
          <AlertDialogDescription>
            {user
              ? `Are you sure you want to delete ${user.name}? This cannot be undone.`
              : "Are you sure? This cannot be undone."}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel} disabled={submitting}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => {
              // Don't auto-close — the parent decides when to close on success.
              e.preventDefault();
              if (submitting) return;
              onConfirm();
            }}
            disabled={submitting}
            className={cn(
              buttonVariants({ variant: "destructive" }),
              "gap-2",
            )}
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : null}
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default DeleteAlertDialog;
