// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-07, BR-C-09, BR-C-11
// LEGACY: source/dbConnection.php (replaced by HTTP boundary)
// COMPONENT: api/client
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// Thin fetch wrapper.
// - Owns VITE_API_BASE.
// - Parses 4xx/5xx ProblemDetail envelopes into a typed ApiError.
// - Returns `undefined` on 204 (BR-C-08: DELETE happy path).
//
// Frontend firewall (Planning §1.3): this module is the ONLY place where
// raw fetch() is allowed. Hooks consume `request()`; components never
// touch the network directly.

import { parseProblemDetail, type ProblemDetailParsed } from "@/lib/problem";

const API_BASE: string =
  (import.meta.env?.VITE_API_BASE as string | undefined) ?? "/api";

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";

export class ApiError extends Error {
  readonly status: number;
  readonly title: string;
  readonly detail?: string;
  readonly errors: ProblemDetailParsed["errors"];
  readonly problem: ProblemDetailParsed;

  constructor(problem: ProblemDetailParsed) {
    super(problem.detail ?? problem.title);
    this.name = "ApiError";
    this.status = problem.status;
    this.title = problem.title;
    this.detail = problem.detail;
    this.errors = problem.errors;
    this.problem = problem;
  }
}

function joinUrl(base: string, path: string): string {
  if (!path.startsWith("/")) {
    return `${base}/${path}`;
  }
  // path is like "/users" — base may end in "/api" or "/api/".
  const trimmedBase = base.endsWith("/") ? base.slice(0, -1) : base;
  // Strip the leading "/api" from `path` if `base` already supplies it.
  if (trimmedBase.endsWith("/api") && path.startsWith("/api/")) {
    return `${trimmedBase}${path.slice(4)}`;
  }
  return `${trimmedBase}${path}`;
}

async function readProblem(
  resp: Response,
): Promise<ProblemDetailParsed> {
  let body: unknown = null;
  try {
    body = await resp.json();
  } catch {
    body = null;
  }
  return parseProblemDetail(body, resp.status);
}

export async function request<T>(
  method: HttpMethod,
  path: string,
  body?: unknown,
): Promise<T> {
  const url = joinUrl(API_BASE, path);
  const init: RequestInit = {
    method,
    headers: {
      Accept: "application/json, application/problem+json",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  const resp = await fetch(url, init);

  if (resp.status === 204) {
    // BR-C-08: DELETE returns no content.
    return undefined as unknown as T;
  }

  if (!resp.ok) {
    const problem = await readProblem(resp);
    throw new ApiError(problem);
  }

  // 2xx with body — assume JSON.
  return (await resp.json()) as T;
}
