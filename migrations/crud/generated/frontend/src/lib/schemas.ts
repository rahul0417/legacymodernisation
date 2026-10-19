// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-03, BR-C-04, BR-C-05, BR-C-06
// LEGACY: source/addAction.php:13-31, source/editAction.php:7-25
// COMPONENT: lib/schemas
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// Zod schema mirroring backend Pydantic UserCreate/UserUpdate 1:1.
// Planning §9.5 parity table is the verbatim source for messages.
//
// Drift between this file and backend `schemas.py` breaks BR-C-03/04/05/06
// acceptance criteria — keep them aligned.

import { z } from "zod";

export const userFormSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Name is required.")
    .max(100, "Name is too long (max 100)."),
  age: z.coerce
    .number({ invalid_type_error: "Age must be a whole number." })
    .int("Age must be a whole number.")
    .min(0, "Age cannot be negative.")
    .max(150, "Age cannot exceed 150."),
  email: z
    .string()
    .trim()
    .email("Enter a valid email.")
    .max(100, "Email is too long (max 100)."),
});

export type UserFormValues = z.infer<typeof userFormSchema>;
