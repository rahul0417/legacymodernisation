// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-01, BR-C-07, BR-C-08, BR-C-11
// LEGACY: source/index.php, source/addAction.php, source/editAction.php, source/delete.php
// COMPONENT: tests/msw/handlers
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// MSW handlers — Stage 6 will enrich with the full Planning §11.2 matrix.
// CodeGen ships a minimal in-memory store so smoke tests can drive the
// happy path + a couple of error envelopes.

import { http, HttpResponse } from "msw";

import type { User } from "@/types/user";

const PROBLEM_CT = "application/problem+json";

let nextId = 1;
let store: User[] = [];

export function seed(users: Array<Omit<User, "id">>): User[] {
  store = users.map((u) => ({ id: nextId++, ...u }));
  return [...store];
}

export function resetStore() {
  nextId = 1;
  store = [];
}

const BASE = "/api/users";

export const handlers = [
  http.get(BASE, () => {
    const sorted = [...store].sort((a, b) => b.id - a.id);
    return HttpResponse.json(sorted);
  }),

  http.get(`${BASE}/:id`, ({ params }) => {
    const id = Number(params.id);
    const row = store.find((u) => u.id === id);
    if (!row) {
      return HttpResponse.json(
        {
          type: "about:blank",
          title: "User not found",
          status: 404,
          detail: `User ${id} not found`,
          instance: `${BASE}/${id}`,
        },
        { status: 404, headers: { "content-type": PROBLEM_CT } },
      );
    }
    return HttpResponse.json(row);
  }),

  http.post(BASE, async ({ request }) => {
    const body = (await request.json()) as Omit<User, "id">;
    if (store.some((u) => u.email === body.email)) {
      return HttpResponse.json(
        {
          type: "about:blank",
          title: "Email already exists",
          status: 409,
          detail: `Email '${body.email}' is already registered.`,
          instance: BASE,
        },
        { status: 409, headers: { "content-type": PROBLEM_CT } },
      );
    }
    const created: User = { id: nextId++, ...body };
    store.push(created);
    return HttpResponse.json(created, {
      status: 201,
      headers: { Location: `${BASE}/${created.id}` },
    });
  }),

  http.put(`${BASE}/:id`, async ({ params, request }) => {
    const id = Number(params.id);
    const body = (await request.json()) as Omit<User, "id">;
    const target = store.find((u) => u.id === id);
    if (!target) {
      return HttpResponse.json(
        {
          type: "about:blank",
          title: "User not found",
          status: 404,
          detail: `User ${id} not found`,
          instance: `${BASE}/${id}`,
        },
        { status: 404, headers: { "content-type": PROBLEM_CT } },
      );
    }
    const clash = store.find((u) => u.email === body.email && u.id !== id);
    if (clash) {
      return HttpResponse.json(
        {
          type: "about:blank",
          title: "Email already exists",
          status: 409,
          detail: `Email '${body.email}' is already registered.`,
          instance: `${BASE}/${id}`,
        },
        { status: 409, headers: { "content-type": PROBLEM_CT } },
      );
    }
    Object.assign(target, body);
    return HttpResponse.json(target);
  }),

  http.delete(`${BASE}/:id`, ({ params }) => {
    const id = Number(params.id);
    const before = store.length;
    store = store.filter((u) => u.id !== id);
    if (store.length === before) {
      return HttpResponse.json(
        {
          type: "about:blank",
          title: "User not found",
          status: 404,
          detail: `User ${id} not found`,
          instance: `${BASE}/${id}`,
        },
        { status: 404, headers: { "content-type": PROBLEM_CT } },
      );
    }
    return new HttpResponse(null, { status: 204 });
  }),
];
