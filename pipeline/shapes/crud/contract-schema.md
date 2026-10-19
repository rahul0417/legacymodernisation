# Contract schema — `runs/<ts>/contract.json`

Produced by Stage 1 (Extract), consumed by Stage 2 (Generate) and Stage 3 (Verify).
**Single source of truth** for everything entity-specific in the generated code.

## Top-level shape

```json
{
  "schema_version": 1,
  "entity": {
    "name_singular": "user",
    "name_plural":   "users",
    "name_pascal":   "User"
  },
  "table": {
    "name":      "users",
    "comment":   "(optional) human description"
  },
  "fields":              [<field>, ...],
  "endpoints":           [<endpoint>, ...],
  "acceptance_criteria": ["AC-1 …", "AC-2 …", ...],
  "risk_flags":          [<risk>, ...],
  "seed_rows":           [<row>, ...],
  "legacy": {
    "source_dir":   "migrations/crud/source",
    "files":        ["index.php", "add.php", "...", "dbConnection.php"],
    "loc":          222,
    "framework":    "none",
    "db_layer":     "mysqli procedural"
  }
}
```

## `<field>`

```json
{
  "name":          "email",
  "type":          "email",        // str | int | email | bool | date | datetime
  "required":      true,
  "max_length":    100,            // for str/email
  "min_length":    1,              // for str/email
  "min":           0,              // for int (use null if none)
  "max":           150,            // for int (use null if none)
  "unique":        true,           // generates UNIQUE constraint
  "primary":       false,
  "auto_increment": false,         // primary keys; uses Identity(always=True) in PG
  "nullable":      false,
  "default":       null,           // python-literal default if any
  "py_type":       "EmailStr",     // explicit hint for codegen (optional)
  "ts_type":       "string"        // explicit hint for codegen (optional)
}
```

## `<endpoint>`

```json
{
  "name":            "update_user",
  "method":          "PUT",
  "path":            "/api/users/{id}",
  "status_success":  200,
  "status_errors":   [404, 409, 422],
  "request_body":    "UserUpdate",       // schema name
  "response_body":   "UserRead",
  "idempotent":      true,
  "uses_path_id":    true,
  "service_method":  "update_user"
}
```

## `<risk>`

```json
{
  "id":              "RF-001",
  "file":            "edit.php",
  "line":            9,
  "class":           "SQL_INJECTION",  // SQL_INJECTION | XSS | CSRF | OPEN_REDIRECT | etc.
  "severity":        "CRITICAL",
  "snippet":         "$query = \"SELECT * FROM users WHERE id=$id\";",
  "auto_resolved_by": "Path(..., gt=0) coerces id to int; non-int → 422"
}
```

## `<row>` (one per `seed_rows[]` entry)

```json
{ "id": 1, "name": "Alice Anderson", "age": 34, "email": "alice@example.com" }
```

Use `@example.com` / `@example.org` — Pydantic `EmailStr` rejects `.test` per RFC 2606.

## Validation

Stage 2 will refuse to start if `contract.json`:
- Missing `entity.name_singular` / `name_plural` / `name_pascal`
- Fewer than 1 field marked `primary: true`
- Endpoints with `uses_path_id: true` but no path param `{id}`
- Any seed row missing a non-nullable field
- Any `email`-typed field with default values using reserved TLDs (`.test`, `.example`, `.invalid`)
