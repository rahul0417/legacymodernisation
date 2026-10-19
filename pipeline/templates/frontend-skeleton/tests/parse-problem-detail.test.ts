// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-03, BR-C-04, BR-C-05, BR-C-06, BR-C-07, BR-C-11
// LEGACY: source/addAction.php:18-32 (per-field red-font feedback)
// COMPONENT: tests/parse-problem-detail
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN
//
// Stage-6 R-2 — direct unit test for `parseProblemDetail` field-mapping
// (Planning §11.2, Gate-4 carried item). Verifies:
//   1. `loc[last]` → `field` extraction (drops Pydantic's leading "body").
//   2. Multiple-error case routes each to its own field entry.
//   3. "No errors" fallback returns an empty array, not undefined.
//   4. Non-object body falls back to status + generic title.
//   5. Deeply nested loc and numeric loc indices still resolve to the leaf.

import { describe, expect, it } from "vitest";

import { parseProblemDetail } from "@/lib/problem";

describe("parseProblemDetail — field mapping", () => {
  it("extracts loc[last] as the field name and drops leading 'body'", () => {
    const parsed = parseProblemDetail(
      {
        type: "about:blank",
        title: "Validation error",
        status: 422,
        detail: "Request body failed validation.",
        instance: "/api/users",
        errors: [
          {
            loc: ["body", "email"],
            msg: "value is not a valid email address",
            type: "value_error",
          },
        ],
      },
      422,
    );

    expect(parsed.status).toBe(422);
    expect(parsed.title).toBe("Validation error");
    expect(parsed.errors).toHaveLength(1);
    expect(parsed.errors[0].field).toBe("email");
    expect(parsed.errors[0].message).toBe("value is not a valid email address");
    expect(parsed.errors[0].type).toBe("value_error");
  });

  it("handles multiple per-field errors with distinct loc tuples", () => {
    const parsed = parseProblemDetail(
      {
        title: "Validation error",
        status: 422,
        errors: [
          { loc: ["body", "name"], msg: "Name is required", type: "string_too_short" },
          { loc: ["body", "age"], msg: "Age must be <= 150", type: "less_than_equal" },
          { loc: ["body", "email"], msg: "Bad email", type: "value_error" },
        ],
      },
      422,
    );

    expect(parsed.errors).toHaveLength(3);
    const byField = Object.fromEntries(
      parsed.errors.map((e) => [e.field, e.message]),
    );
    expect(byField.name).toBe("Name is required");
    expect(byField.age).toBe("Age must be <= 150");
    expect(byField.email).toBe("Bad email");
  });

  it("returns an empty errors[] (NOT undefined) when none provided — UserForm relies on .length", () => {
    const parsed = parseProblemDetail(
      {
        title: "Email already exists",
        status: 409,
        detail: "Email 'dup@example.com' is already registered.",
      },
      409,
    );

    expect(parsed.errors).toEqual([]);
    expect(Array.isArray(parsed.errors)).toBe(true);
    expect(parsed.status).toBe(409);
    expect(parsed.title).toBe("Email already exists");
    expect(parsed.detail).toContain("already registered");
  });

  it("falls back to statusFallback + 'Error' title when body is not an object", () => {
    const parsed = parseProblemDetail("oops, plain string", 500);
    expect(parsed.status).toBe(500);
    expect(parsed.title).toBe("Error");
    expect(parsed.errors).toEqual([]);
  });

  it("falls back to statusFallback when body lacks a numeric status", () => {
    const parsed = parseProblemDetail(
      { title: "Server exploded" },
      503,
    );
    expect(parsed.status).toBe(503);
    expect(parsed.title).toBe("Server exploded");
  });

  it("uses last segment of a deeply-nested loc tuple", () => {
    const parsed = parseProblemDetail(
      {
        title: "Validation error",
        status: 422,
        errors: [
          {
            loc: ["body", "user", "contact", "email"],
            msg: "nested",
            type: "value_error",
          },
        ],
      },
      422,
    );
    expect(parsed.errors[0].field).toBe("email");
  });

  it("coerces numeric loc indices to strings as the leaf field", () => {
    const parsed = parseProblemDetail(
      {
        title: "Validation error",
        status: 422,
        errors: [
          { loc: ["body", "items", 0], msg: "bad", type: "value_error" },
        ],
      },
      422,
    );
    expect(parsed.errors[0].field).toBe("0");
  });

  it("returns '_root' field when loc is empty (defensive)", () => {
    const parsed = parseProblemDetail(
      {
        title: "Validation error",
        status: 422,
        errors: [{ msg: "global", type: "value_error" }],
      },
      422,
    );
    expect(parsed.errors[0].field).toBe("_root");
  });

  it("provides safe defaults for missing msg/type on the wire entry", () => {
    const parsed = parseProblemDetail(
      {
        title: "Validation error",
        status: 422,
        errors: [{ loc: ["body", "name"] }],
      },
      422,
    );
    expect(parsed.errors[0].field).toBe("name");
    expect(parsed.errors[0].message).toBe("Invalid value");
    expect(parsed.errors[0].type).toBe("value_error");
  });
});
