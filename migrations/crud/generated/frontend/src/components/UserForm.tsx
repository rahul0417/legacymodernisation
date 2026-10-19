// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-03, BR-C-04, BR-C-05, BR-C-06, BR-C-11
// LEGACY: source/add.php:12-31, source/edit.php:29-48, source/addAction.php:18-32
// COMPONENT: components/UserForm
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// react-hook-form + zodResolver(userFormSchema). The Zod schema in
// `src/lib/schemas.ts` mirrors backend Pydantic 1:1; on server 422 we
// project per-field `errors[]` into RHF setError so inline error text
// appears under the same input (BR-C-03 AC-03e — preserves legacy
// per-field red-font feedback).

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { userFormSchema, type UserFormValues } from "@/lib/schemas";
import type { ProblemDetailParsed } from "@/lib/problem";

export interface UserFormProps {
  defaultValues?: Partial<UserFormValues>;
  submitting: boolean;
  error?: ProblemDetailParsed | null;
  submitLabel?: string;
  onCancel?: () => void;
  onSubmit: (values: UserFormValues) => void;
}

const VALID_FIELDS = new Set<keyof UserFormValues>(["name", "age", "email"]);

export function UserForm({
  defaultValues,
  submitting,
  error,
  submitLabel = "Save",
  onCancel,
  onSubmit,
}: UserFormProps) {
  const form = useForm<UserFormValues>({
    resolver: zodResolver(userFormSchema),
    mode: "onBlur",
    defaultValues: {
      name: defaultValues?.name ?? "",
      age: defaultValues?.age ?? 0,
      email: defaultValues?.email ?? "",
    },
  });

  // Server-side error projection: when `error?.errors` arrives, route
  // each entry to the matching RHF field. Fields not in our schema
  // surface via FormMessage on the form root.
  useEffect(() => {
    if (!error) return;
    // 409 (BR-C-11) — backend returns title "Email already exists" without
    // a per-field errors[]; project that into the email field manually.
    // Must run BEFORE the empty-errors early-return below or 409s with no
    // errors[] would never reach the inline FormMessage.
    if (error.status === 409) {
      form.setError("email", {
        type: "server",
        message: error.detail ?? "This email is already registered.",
      });
    }
    if (error.errors.length === 0) return;
    for (const fieldErr of error.errors) {
      const key = fieldErr.field as keyof UserFormValues;
      if (VALID_FIELDS.has(key)) {
        form.setError(key, { type: "server", message: fieldErr.message });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [error]);

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="space-y-4"
        noValidate
      >
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Name</FormLabel>
              <FormControl>
                <Input
                  autoFocus
                  type="text"
                  maxLength={100}
                  placeholder="Jane Doe"
                  disabled={submitting}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="age"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Age</FormLabel>
              <FormControl>
                <Input
                  type="number"
                  min={0}
                  max={150}
                  step={1}
                  placeholder="30"
                  disabled={submitting}
                  {...field}
                  value={
                    field.value === undefined || field.value === null
                      ? ""
                      : field.value
                  }
                  onChange={(e) =>
                    field.onChange(
                      e.target.value === "" ? "" : Number(e.target.value),
                    )
                  }
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input
                  type="email"
                  maxLength={100}
                  placeholder="jane@example.com"
                  disabled={submitting}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="flex justify-end gap-2 pt-2">
          {onCancel ? (
            <Button
              type="button"
              variant="outline"
              onClick={onCancel}
              disabled={submitting}
            >
              Cancel
            </Button>
          ) : null}
          <Button type="submit" disabled={submitting} className="gap-2">
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : null}
            {submitLabel}
          </Button>
        </div>
      </form>
    </Form>
  );
}

export default UserForm;
