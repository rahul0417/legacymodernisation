#!/usr/bin/env bash
# self-review.sh — replaces the v1 Self-Review agent (478 events) with 12
# deterministic checks that take milliseconds. Run by Stage 3 before pytest.
#
# Usage: self-review.sh <generated_dir>
#
# Exit codes:
#   0 — all 12 checks PASS
#   1 — one or more checks FAIL
#   2 — usage error / generated_dir missing
#
# Each check is bash-only (no node, no python, no installed deps). The heavier
# tsc/ruff/pytest checks happen later in Stage 3, after deps are installed.

set -u

# ─── Args + setup ────────────────────────────────────────────────────────────

GEN="${1:-}"
if [[ -z "$GEN" || ! -d "$GEN" ]]; then
  echo "usage: $0 <generated_dir>" >&2
  echo "       generated_dir should contain backend/ and frontend/ subdirs" >&2
  exit 2
fi
GEN="${GEN%/}"  # strip trailing slash

if [[ -t 1 ]]; then
  G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; D=$'\033[2m'; B=$'\033[1m'; X=$'\033[0m'
else
  G=''; R=''; Y=''; D=''; B=''; X=''
fi

PASSES=0
FAILS=0
declare -a FAILURES=()

pass() { PASSES=$((PASSES+1)); printf "  ${G}✓${X} %s\n" "$1"; }
fail() {
  FAILS=$((FAILS+1))
  FAILURES+=("$1")
  printf "  ${R}✗${X} %s\n" "$1"
  if [[ -n "${2:-}" ]]; then
    printf "    ${D}%s${X}\n" "$2"
  fi
}
hdr() { printf "\n${B}%s${X}\n" "$1"; }

printf "${B}Self-Review · %s${X}\n" "$GEN"
printf "${D}─────────────────────────────────────────────────────────────${X}\n"

# Pre-flight: ensure expected top-level dirs exist
[[ -d "$GEN/backend" ]] || { fail "backend/ dir missing under $GEN"; exit 1; }
[[ -d "$GEN/frontend" ]] || { fail "frontend/ dir missing under $GEN"; exit 1; }

BACKEND="$GEN/backend"
FRONTEND="$GEN/frontend"

# ─── 1. Layer firewall ──────────────────────────────────────────────────────
hdr "1. Layer firewall — service.py must not import fastapi"
violations=$(grep -ln "^from fastapi\|^import fastapi" "$BACKEND"/app/modules/*/service.py 2>/dev/null || true)
if [[ -z "$violations" ]]; then
  pass "no service file imports fastapi"
else
  fail "service file(s) import fastapi" "$violations"
fi

# ─── 2. No dangerouslySetInnerHTML ──────────────────────────────────────────
hdr "2. No dangerouslySetInnerHTML anywhere in frontend src/"
hits=$(grep -rn "dangerouslySetInnerHTML" "$FRONTEND/src" 2>/dev/null || true)
if [[ -z "$hits" ]]; then
  pass "0 occurrences across $(find "$FRONTEND/src" -type f \( -name '*.tsx' -o -name '*.ts' \) 2>/dev/null | wc -l | tr -d ' ') files"
else
  fail "dangerouslySetInnerHTML used" "$hits"
fi

# ─── 3. Key remount pattern on AddEditDialog ────────────────────────────────
hdr "3. AddEditDialog key remount — key={editing*?.id ?? \"add\"} verbatim"
# BRE handles { } as literal but is fragile; compose two simple greps instead.
match=$(grep -rln 'key={editing' "$FRONTEND/src" 2>/dev/null | xargs -I {} grep -Hln -F '?.id ?? "add"' {} 2>/dev/null || true)
if [[ -n "$match" ]]; then
  pass "found in $(echo "$match" | head -1 | sed "s|$GEN/||")"
else
  fail "key={editing*?.id ?? \"add\"} not found" "expected somewhere in $FRONTEND/src/pages/"
fi

# ─── 4. Service self-collision branch ───────────────────────────────────────
hdr "4. Service self-collision branch (PUT same unique-field → 200, not 409)"
service_files=$(find "$BACKEND/app/modules" -name 'service.py' 2>/dev/null)
if [[ -z "$service_files" ]]; then
  fail "no service.py found under app/modules/"
else
  has_integrity=0
  has_refetch=0
  for f in $service_files; do
    if grep -q "IntegrityError" "$f"; then has_integrity=1; fi
    # heuristic: a re-fetch by unique field then compare ids
    if grep -qE 'existing.*\.id\s*==|same.user|AC-11c|self.collision|existing_by_email' "$f"; then has_refetch=1; fi
  done
  if [[ $has_integrity -eq 1 && $has_refetch -eq 1 ]]; then
    pass "IntegrityError catch + re-fetch/id-compare both present"
  else
    fail "self-collision branch not fully present" \
         "has IntegrityError: $has_integrity · has re-fetch/id-compare: $has_refetch"
  fi
fi

# ─── 5. ProblemDetail shape (RFC-9457) ──────────────────────────────────────
hdr "5. ProblemDetail schema — 5 required fields"
schemas=$(find "$BACKEND/app/modules" -name 'schemas.py' 2>/dev/null | head -1)
if [[ -z "$schemas" ]]; then
  fail "no schemas.py found under app/modules/"
else
  missing=()
  for field in "type" "title" "status" "detail" "instance"; do
    if ! grep -qE "^\\s+${field}:" "$schemas"; then
      missing+=("$field")
    fi
  done
  if [[ ${#missing[@]} -eq 0 ]]; then
    pass "type, title, status, detail, instance all present in $schemas"
  else
    fail "ProblemDetail missing fields: ${missing[*]}" "$schemas"
  fi
fi

# ─── 6. Zod schemas exist + parity hints ────────────────────────────────────
hdr "6. Zod schemas exist + parity hints (Lock L5)"
zod="$FRONTEND/src/lib/schemas.ts"
if [[ ! -f "$zod" ]]; then
  fail "src/lib/schemas.ts missing"
else
  has_object=$(grep -c "z\.object" "$zod" || true)
  has_email=$(grep -c "\.email(" "$zod" || true)
  has_int_or_coerce=$(grep -cE "z\.coerce\.number|\.int\(" "$zod" || true)
  if [[ "$has_object" -ge 1 && "$has_email" -ge 1 && "$has_int_or_coerce" -ge 1 ]]; then
    pass "z.object + .email() + int/coerce all present"
  else
    fail "Zod schemas incomplete" "object:$has_object email:$has_email int:$has_int_or_coerce"
  fi
fi

# ─── 7. 8-line traceability headers ─────────────────────────────────────────
hdr "7. 8-line traceability header on every entity-specific logic file"
missing_headers=()
# Backend logic files: under app/modules (excluding __init__.py)
while IFS= read -r f; do
  if ! head -8 "$f" 2>/dev/null | grep -q "MIGRATION TRACEABILITY"; then
    missing_headers+=("${f#$GEN/}")
  fi
done < <(find "$BACKEND/app/modules" -name '*.py' -not -name '__init__.py' 2>/dev/null)
# Frontend logic files: under src/ excluding shadcn primitives + main/App
while IFS= read -r f; do
  if ! head -8 "$f" 2>/dev/null | grep -q "MIGRATION TRACEABILITY"; then
    missing_headers+=("${f#$GEN/}")
  fi
done < <(find "$FRONTEND/src" \( -name '*.ts' -o -name '*.tsx' \) \
            -not -path '*/components/ui/*' \
            -not -name 'main.tsx' \
            -not -name 'vite-env.d.ts' 2>/dev/null)

if [[ ${#missing_headers[@]} -eq 0 ]]; then
  pass "every logic file carries the 8-line MIGRATION TRACEABILITY block"
else
  fail "${#missing_headers[@]} file(s) missing traceability header" "$(printf '%s\n      ' "${missing_headers[@]}" | head -10)"
fi

# ─── 8. No SQL string concat — SQLAlchemy parametrised only ─────────────────
hdr "8. No SQL string concat anywhere in backend"
# f-strings or +concat with FROM/WHERE/SELECT/INSERT/UPDATE/DELETE inline
hits=$(grep -rEn 'f"[^"]*\{[^}]+\}[^"]*(FROM|WHERE|SELECT|INSERT|UPDATE|DELETE)|" \+ .*(FROM|WHERE|SELECT|INSERT|UPDATE|DELETE)' "$BACKEND/app/modules" 2>/dev/null || true)
if [[ -z "$hits" ]]; then
  pass "no f-string or + concat with SQL keywords"
else
  fail "SQL string concat detected" "$hits"
fi

# ─── 9. DELETE verb purity ──────────────────────────────────────────────────
hdr "9. DELETE verb purity — no @router.get on delete paths"
# Look for any router.get whose path string mentions 'delete'
hits=$(grep -rEn '@router\.get\([^)]*delete' "$BACKEND/app/modules" 2>/dev/null || true)
if [[ -z "$hits" ]]; then
  pass "no @router.get(...) decorating a delete path"
else
  fail "@router.get used on a delete-ish path" "$hits"
fi

# ─── 10. TypeScript strict mode ─────────────────────────────────────────────
hdr "10. TypeScript strict mode enabled"
tsconfig="$FRONTEND/tsconfig.json"
if [[ ! -f "$tsconfig" ]]; then
  fail "tsconfig.json missing"
else
  if grep -q '"strict":\s*true' "$tsconfig"; then
    pass "tsconfig.json has strict: true"
  else
    fail "tsconfig.json does not set strict: true" "$tsconfig"
  fi
fi

# ─── 11. Ruff configured + reachable ────────────────────────────────────────
hdr "11. Ruff configured in pyproject.toml"
pyproject="$BACKEND/pyproject.toml"
if [[ ! -f "$pyproject" ]]; then
  fail "pyproject.toml missing"
else
  if grep -qE '^\[tool\.ruff\]|^\[tool\.ruff\.' "$pyproject"; then
    pass "[tool.ruff] block present in pyproject.toml"
  else
    fail "no [tool.ruff] block in pyproject.toml" "$pyproject"
  fi
fi

# ─── 12. Test coverage scaffold ─────────────────────────────────────────────
hdr "12. Test scaffold — unit + integration + regression all have ≥1 test"
unit_count=$(find "$BACKEND/tests/unit" -name 'test_*.py' 2>/dev/null | wc -l | tr -d ' ')
integ_count=$(find "$BACKEND/tests/integration" -name 'test_*.py' 2>/dev/null | wc -l | tr -d ' ')
regr_count=$(find "$BACKEND/tests/regression" -name 'test_*.py' 2>/dev/null | wc -l | tr -d ' ')
fe_test_count=$(find "$FRONTEND/tests" -name '*.test.t*' 2>/dev/null | wc -l | tr -d ' ')

if [[ $unit_count -ge 1 && $integ_count -ge 1 && $regr_count -ge 1 && $fe_test_count -ge 1 ]]; then
  pass "unit:$unit_count · integration:$integ_count · regression:$regr_count · frontend:$fe_test_count"
else
  fail "missing test scaffold" "unit:$unit_count integ:$integ_count regr:$regr_count fe:$fe_test_count"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
printf "\n${D}─────────────────────────────────────────────────────────────${X}\n"
TOTAL=$((PASSES + FAILS))
printf "${B}SUMMARY${X}: ${G}%d PASS${X} · ${R}%d FAIL${X} / %d total\n" "$PASSES" "$FAILS" "$TOTAL"
if [[ $FAILS -eq 0 ]]; then
  printf "${G}${B}All checks PASS.${X}\n"
  exit 0
else
  printf "${R}${B}%d check(s) failed:${X}\n" "$FAILS"
  for msg in "${FAILURES[@]}"; do
    printf "  ${R}·${X} %s\n" "$msg"
  done
  exit 1
fi
