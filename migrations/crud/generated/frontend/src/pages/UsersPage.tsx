// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-01, BR-C-02, BR-C-07, BR-C-08, BR-C-10, BR-C-11
// LEGACY: source/index.php (composite list + dispatch)
// COMPONENT: pages/UsersPage
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// Single stateful page. Owns ALL modal state via a centralised useState
// cluster (Comprehension §5.2 — at most one modal open at a time).
//
// Hooks own server state; this component only orchestrates open/close
// transitions, callback wiring, and toast emissions.

import { useMemo, useState, type ReactElement } from "react";

import { PageHeader } from "@/components/PageHeader";
import { UsersDataTable } from "@/components/UsersDataTable";
import { AddEditDialog } from "@/components/AddEditDialog";
import { DeleteAlertDialog } from "@/components/DeleteAlertDialog";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useToast } from "@/components/ui/use-toast";
import { parseProblemDetail, type ProblemDetailParsed } from "@/lib/problem";
import {
  ApiError,
  useCreateUser,
  useDeleteUser,
  useUpdateUser,
  useUsersQuery,
} from "@/hooks/useUsers";
import type { UserFormValues } from "@/lib/schemas";
import type { User } from "@/types/user";

// Translate any thrown error to a ProblemDetailParsed-like envelope.
function asProblem(err: unknown, fallbackStatus = 500): ProblemDetailParsed {
  if (err instanceof ApiError) return err.problem;
  if (err && typeof err === "object" && "message" in err) {
    return parseProblemDetail(
      { title: "Network error", status: fallbackStatus, detail: String((err as Error).message) },
      fallbackStatus,
    );
  }
  return parseProblemDetail(
    { title: "Network error", status: fallbackStatus },
    fallbackStatus,
  );
}

export default function UsersPage() {
  // ── Modal state cluster (Comprehension §5.2 / Planning §9.2.1) ──
  const [addDialogOpen, setAddDialogOpen] = useState<boolean>(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [deletingUser, setDeletingUser] = useState<User | null>(null);
  const [serverFormError, setServerFormError] =
    useState<ProblemDetailParsed | null>(null);

  const { toast } = useToast();
  const usersQuery = useUsersQuery();
  const rows = useMemo(() => usersQuery.data ?? [], [usersQuery.data]);

  // ── Mutations ───────────────────────────────────────────────────
  const createMutation = useCreateUser({
    onSuccess: () => {
      toast({ title: "User added" });
      setAddDialogOpen(false);
      setServerFormError(null);
    },
    onError: (err) => {
      const problem = asProblem(err);
      setServerFormError(problem);
      if (problem.status >= 500) {
        toast({
          title: "Could not save user.",
          description: "Please try again.",
          variant: "destructive",
        });
      }
    },
  });

  const updateMutation = useUpdateUser({
    onSuccess: () => {
      toast({ title: "User updated" });
      setEditingUser(null);
      setServerFormError(null);
    },
    onError: (err) => {
      const problem = asProblem(err);
      setServerFormError(problem);
      if (problem.status === 404) {
        // Row vanished — close dialog, refetch, info toast (AC-07d).
        setEditingUser(null);
        toast({
          title: "User not found",
          description: "That user no longer exists.",
        });
        void usersQuery.refetch();
      } else if (problem.status >= 500) {
        toast({
          title: "Could not save user.",
          description: "Please try again.",
          variant: "destructive",
        });
      }
    },
  });

  const deleteMutation = useDeleteUser({
    onSuccess: () => {
      toast({ title: "User deleted" });
      setDeletingUser(null);
    },
    onError: (err) => {
      const problem = asProblem(err);
      if (problem.status === 404) {
        // Row already gone — close dialog, info toast (Comprehension §5.4).
        setDeletingUser(null);
        toast({
          title: "Already removed",
          description: "That user was already removed.",
        });
        void usersQuery.refetch();
      } else {
        toast({
          title: "Couldn't delete user.",
          description: "Please try again.",
          variant: "destructive",
        });
      }
    },
  });

  // ── Handlers ────────────────────────────────────────────────────
  const handleAddClick = () => {
    setServerFormError(null);
    setAddDialogOpen(true);
  };

  const handleEditClick = (u: User) => {
    setServerFormError(null);
    setEditingUser(u);
  };

  const handleDeleteClick = (u: User) => setDeletingUser(u);

  const handleAddSubmit = (values: UserFormValues) => {
    setServerFormError(null);
    createMutation.mutate(values);
  };

  const handleEditSubmit = (values: UserFormValues) => {
    if (!editingUser) return;
    setServerFormError(null);
    updateMutation.mutate({ id: editingUser.id, values });
  };

  const handleDeleteConfirm = () => {
    if (!deletingUser) return;
    deleteMutation.mutate(deletingUser.id);
  };

  // ── Render ──────────────────────────────────────────────────────
  let body: ReactElement;
  if (usersQuery.isPending) {
    body = <LoadingSkeleton rows={5} />;
  } else if (usersQuery.isError) {
    body = (
      <ErrorState
        onRetry={() => void usersQuery.refetch()}
        message={
          usersQuery.error instanceof ApiError
            ? usersQuery.error.detail ?? usersQuery.error.title
            : undefined
        }
      />
    );
  } else if (rows.length === 0) {
    body = <EmptyState onAddClick={handleAddClick} />;
  } else {
    body = (
      <UsersDataTable
        rows={rows}
        onEdit={handleEditClick}
        onDelete={handleDeleteClick}
      />
    );
  }

  // `key={editingUser?.id ?? "add"}` on AddEditDialog forces remount on
  // every selection so stale values never bleed across opens (Gate-2
  // priority #4 — Gate-3 lock #2).
  return (
    <main className="container mx-auto max-w-5xl space-y-6 py-10">
      <PageHeader
        refetching={usersQuery.isFetching && !usersQuery.isPending}
        onAddClick={handleAddClick}
      />

      {body}

      <AddEditDialog
        key={editingUser?.id ?? "add"}
        open={addDialogOpen || editingUser !== null}
        mode={editingUser ? "edit" : "add"}
        user={editingUser}
        submitting={createMutation.isPending || updateMutation.isPending}
        serverError={serverFormError}
        onClose={() => {
          if (createMutation.isPending || updateMutation.isPending) return;
          setAddDialogOpen(false);
          setEditingUser(null);
          setServerFormError(null);
        }}
        onSubmit={editingUser ? handleEditSubmit : handleAddSubmit}
      />

      <DeleteAlertDialog
        open={deletingUser !== null}
        user={deletingUser}
        submitting={deleteMutation.isPending}
        onCancel={() => {
          if (deleteMutation.isPending) return;
          setDeletingUser(null);
        }}
        onConfirm={handleDeleteConfirm}
      />
    </main>
  );
}
