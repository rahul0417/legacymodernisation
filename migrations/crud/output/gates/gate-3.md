# Gate 3 — Planning review

**Date:** 2026-05-14
**Reviewer:** Rahul Chandra (HITL)
**Stage:** Planning (`output/planning/planning-001.md`)
**Status:** ✅ **APPROVED**

## Summary

1480-line plan covering 91 files across two codebases:
- **Backend** (38 files, 14 logic-carrying): FastAPI 0.110 + SQLAlchemy 2.x async + PG 16
- **Frontend** (53 files, 9 custom logic + 11 shadcn-copied primitives + 7 tests + scaffold): React 18 + TS + shadcn/ui + Tailwind + Vite + TanStack Query + RHF + Zod

**Self-check matrix: 37/37 PASS** (11 BR-Cs + 8 RFs + 6 locks).

## OQ-P resolutions

| OQ | Decision |
|---|---|
| OQ-P-001 openapi-typescript auto-gen | **Defer to Phase 5.** Hand-written User type is sufficient. |
| OQ-P-002 Cockpit per-file diff | **Defer to Stage 8 design.** |
| OQ-P-003 UserUpdate body-side `id` strictness | **Keep `extra="forbid"`** (REST hygiene). |

## Locked items CodeGen must honour

1. **Traceability headers mandatory** — 8-line block on every Python AND TSX file.
2. **`key={editingUser?.id ?? "add"}` on `<AddEditDialog>`** — prevents stale-form leak (Gate-2 priority).
3. **`UserService.update_user` self-collision logic** — distinguish AC-11c (same user → 200) from AC-11b (other user → 409). Algorithm in §6.4.
4. **Zod ↔ Pydantic message parity** — §9.5 table is verbatim source.
5. **DELETE verb purity** — only `@router.delete` registered; regression test asserts.
6. **No `dangerouslySetInnerHTML` anywhere** — RF-003/004 auto-resolution depends on it.
7. **Visual transformation is the demo's load-bearing artefact** — 16 screenshots (8 legacy + 8 new) at Stage 7.

---

**Next stage:** Stage 4 CodeGen. Subagent: `general-purpose` (Opus). Produces both backend and frontend codebases under `migrations/crud/generated/`.
