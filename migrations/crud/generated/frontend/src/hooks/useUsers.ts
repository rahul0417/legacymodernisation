// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-01, BR-C-02, BR-C-07, BR-C-08, BR-C-11
// LEGACY: source/index.php, source/addAction.php, source/editAction.php, source/delete.php
// COMPONENT: hooks/useUsers
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// TanStack Query hooks owning server state.
// Components MUST go through these — never call `api/*` directly
// (Planning §1.3 frontend firewall).

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";

import {
  createUser,
  deleteUser,
  listUsers,
  updateUser,
} from "@/api/users";
import { ApiError } from "@/api/client";
import type { User } from "@/types/user";
import type { UserFormValues } from "@/lib/schemas";

// Re-export ApiError so components / pages can `instanceof`-check
// without crossing the `src/api/*` firewall directly (Planning §1.3).
export { ApiError };

export const users = {
  all: ["users"] as const,
} as const;

export function useUsersQuery() {
  return useQuery<User[], ApiError>({
    queryKey: users.all,
    queryFn: listUsers,
    // BR-C-01: data is server-sorted; we never re-sort client-side
    // for the default view.
    placeholderData: (prev) => prev,
  });
}

export function useCreateUser(
  options?: UseMutationOptions<User, ApiError, UserFormValues>,
) {
  const qc = useQueryClient();
  return useMutation<User, ApiError, UserFormValues>({
    mutationFn: createUser,
    ...options,
    onSuccess: (...args) => {
      void qc.invalidateQueries({ queryKey: users.all });
      options?.onSuccess?.(...args);
    },
  });
}

export interface UpdateUserVariables {
  id: number;
  values: UserFormValues;
}

export function useUpdateUser(
  options?: UseMutationOptions<User, ApiError, UpdateUserVariables>,
) {
  const qc = useQueryClient();
  return useMutation<User, ApiError, UpdateUserVariables>({
    mutationFn: ({ id, values }) => updateUser(id, values),
    ...options,
    onSuccess: (...args) => {
      void qc.invalidateQueries({ queryKey: users.all });
      options?.onSuccess?.(...args);
    },
  });
}

export function useDeleteUser(
  options?: UseMutationOptions<void, ApiError, number>,
) {
  const qc = useQueryClient();
  return useMutation<void, ApiError, number>({
    mutationFn: deleteUser,
    ...options,
    onSuccess: (...args) => {
      void qc.invalidateQueries({ queryKey: users.all });
      options?.onSuccess?.(...args);
    },
  });
}
