// MIGRATION TRACEABILITY
// MWU: MWU-CRUD-001
// RULES: BR-C-07, BR-C-11
// LEGACY: source/addAction.php:18-32 (red-font validation), source/editAction.php:13-25
// COMPONENT: lib/problem
// GENERATED: 2026-05-14
// STRATEGY: REWRITE_REACT_SHADCN

// RFC-9457 ProblemDetail parser. Maps the backend's per-field `errors[]`
// (loc tuples like ["body", "email"]) into a flat `ProblemFieldError[]`
// keyed by leaf field name so react-hook-form's `setError(name, ...)`
// can consume them directly.

export interface ProblemFieldError {
  field: string;
  message: string;
  type: string;
}

export interface ProblemDetailParsed {
  status: number;
  title: string;
  detail?: string;
  instance?: string;
  errors: ProblemFieldError[];
}

// Type guard for the raw envelope coming off the wire.
interface RawProblem {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  errors?: Array<{
    loc?: Array<string | number>;
    msg?: string;
    type?: string;
  }>;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function parseProblemDetail(
  body: unknown,
  statusFallback: number,
): ProblemDetailParsed {
  if (!isObject(body)) {
    return {
      status: statusFallback,
      title: "Error",
      detail: undefined,
      errors: [],
    };
  }

  const raw = body as RawProblem;
  const errors: ProblemFieldError[] = (raw.errors ?? [])
    .map((err) => {
      const locArr = err.loc ?? [];
      // Pydantic returns ["body", "<field>"] — drop the leading "body".
      const leaf =
        locArr.length > 0 ? String(locArr[locArr.length - 1]) : "_root";
      return {
        field: leaf,
        message: err.msg ?? "Invalid value",
        type: err.type ?? "value_error",
      };
    });

  return {
    status: typeof raw.status === "number" ? raw.status : statusFallback,
    title: raw.title ?? "Error",
    detail: raw.detail,
    instance: raw.instance,
    errors,
  };
}
