// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-01, BR-C-07, BR-C-08, BR-C-09, BR-C-11
// LEGACY: source/index.php, source/addAction.php, source/editAction.php, source/delete.php
// COMPONENT: api/users
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// Typed wrappers around the 5 backend endpoints.
//
// BR-C-09: deleteUser issues `method: 'DELETE'` only — never a GET,
// never a window.location assignment (kills the legacy delete-via-GET
// foot-gun for good).

import { request } from "./client";
import type { User } from "@/types/user";
import type { UserFormValues } from "@/lib/schemas";

export async function listUsers(): Promise<User[]> {
  return request<User[]>("GET", "/users");
}

export async function getUser(id: number): Promise<User> {
  return request<User>("GET", `/users/${id}`);
}

export async function createUser(values: UserFormValues): Promise<User> {
  return request<User>("POST", "/users", values);
}

export async function updateUser(
  id: number,
  values: UserFormValues,
): Promise<User> {
  return request<User>("PUT", `/users/${id}`, values);
}

export async function deleteUser(id: number): Promise<void> {
  await request<void>("DELETE", `/users/${id}`);
}
