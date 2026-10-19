// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-08, BR-C-11
// LEGACY: source/dbConnection.php (replaced by HTTP boundary)
// COMPONENT: tests/api-client
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

import { describe, expect, it, beforeEach } from "vitest";

import { listUsers, deleteUser, createUser } from "@/api/users";
import { ApiError } from "@/api/client";
import { resetStore, seed } from "./msw/handlers";

describe("api-client", () => {
  beforeEach(() => resetStore());

  it("listUsers returns parsed JSON", async () => {
    seed([{ name: "Alice", age: 30, email: "a@b.co" }]);
    const rows = await listUsers();
    expect(rows).toHaveLength(1);
    expect(rows[0].email).toBe("a@b.co");
  });

  it("BR-C-08: deleteUser resolves with undefined on 204", async () => {
    const [u] = seed([{ name: "Alice", age: 30, email: "a@b.co" }]);
    const result = await deleteUser(u.id);
    expect(result).toBeUndefined();
  });

  it("BR-C-11: 409 ProblemDetail surfaces as ApiError", async () => {
    seed([{ name: "Alice", age: 30, email: "dup@example.com" }]);
    await expect(
      createUser({
        name: "Imposter",
        age: 40,
        email: "dup@example.com",
      }),
    ).rejects.toBeInstanceOf(ApiError);

    try {
      await createUser({
        name: "Imposter",
        age: 40,
        email: "dup@example.com",
      });
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const ae = err as ApiError;
      expect(ae.status).toBe(409);
      expect(ae.title).toBe("Email already exists");
    }
  });
});
