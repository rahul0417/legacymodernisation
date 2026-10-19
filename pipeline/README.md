# Modernisation pipeline — v2 (optimised, button-driven, sales-call companion)

The v1 pipeline that produced `migrations/crud/` was right for FA-scale enterprise
migrations (5 MWUs, multi-company, money precision, JWT design) but carried that
baggage into a 222-LOC chapagain CRUD that needed none of it. This is the v2
strip: same 7-stage spirit collapsed to 3 stages, stack-stable code pre-vendored,
Self-Review-as-script, contract-first generation, button-driven cockpit.

## Status

| Phase | Status |
|---|---|
| 1. Hand-curate templates | ✅ Done |
| 2. Write 3 contract-first prompts (Extract, Generate, Verify) | ⏳ Next |
| 3. Self-Review as a 12-check bash script | ⏳ Pending |
| 4. tmuxrc + 4-pane layout | ⏳ Pending |
| 5. Runner service (Node, SSE + tmux send-keys) | ⏳ Pending |
| 6. Cockpit (live SSE, buttons, captions, fallback) | ⏳ Pending |
| 7. Capture fallback recordings (3× `.cast` + `.tokens.jsonl`) | ⏳ Pending |
| 8. End-to-end smoke + ship | ⏳ Pending |

## Layout

```
pipeline/
├── shapes/crud/            ← the only shape supported in v2; future shapes peer here
│   ├── prompts/            ← Extract, Generate, Verify (one per stage)
│   ├── captions/           ← pre-scripted JSON; played alongside live agent runs
│   ├── recordings/         ← .cast + .tokens.jsonl fallback per stage
│   ├── shape.yaml          ← stage list + model routing + tool allowlist + gates
│   └── manifest.md         ← what's stack-stable (templates/) vs entity-specific (codegen)
├── templates/              ← never regenerated; copied per engagement into runs/<ts>/generated/
│   ├── backend-skeleton/   ← FastAPI shell, conftest, db, main, exception handlers (23 files)
│   ├── frontend-skeleton/  ← shadcn primitives, configs, hooks scaffold (38 files)
│   └── dual-run-template/  ← compose, Dockerfiles, runners (with all 8 v1 fixes baked in)
├── scripts/                ← self-review.sh, post-call.sh, tmuxrc
├── runner/                 ← Node service: HTTP + SSE + tmux orchestration
├── cockpit/                ← live UI: buttons, captions, panes, progress
└── runs/                   ← gitignored; one subdir per demo run (working dir + recordings)
```

## Demo flow (for the salesperson)

1. `cd pipeline && npm --prefix runner start` → starts Node service + attaches tmux session
2. Open `http://localhost:8721/` → cockpit appears
3. Click **▶ Run All** → 3 stages auto-advance with a 3s "Continue?" prompt between each
4. Final screen: 3-up (numbers + mosaic + "Visit new app" / "Send recap" buttons)
5. Click **Send recap** → `scripts/post-call.sh` muxes session.cast + browser.webm → MP4 → email/Slack

## Reliability for live demos

Each stage has a fallback `.cast` + `.tokens.jsonl` recorded from a known-good run.
The runner's watchdog silently switches to the fallback if the live `claude -p` call:

- Emits no tokens for 8s
- Errors out
- Exceeds budgeted max_turns

Audience sees no break — the cockpit + tmux output look identical because the
fallback is the original transcript replayed at the original tempo.

## What's *not* in v2

- v1 lives untouched at `migrations/crud/`. Use the session-replay player at
  `legacymodernisation/session-replay/` to compare v1 vs v2 timelines.
- Multi-shape support (auth-bearing CRUD, complex business logic, multi-module).
  `shapes/` directory is set up for it but only `shapes/crud/` is populated.
- HITL gates between stages. v2 auto-advances. Manually-driven engagements
  should still use v1.
