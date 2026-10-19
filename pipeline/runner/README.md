# Runner — live-demo orchestrator

Tiny Node service that ties the cockpit (HTTP/SSE), `claude -p` (subprocess),
tmux (visible terminal panes), and the audit log into one coherent run.

## Architecture

```
            POST /stage/X                      ┌──────────────┐
   cockpit ──────────────► server.js ─────────►│ stage-runner │
                              │                │  spawns      │
                              │                │  claude -p   │
            GET  /events      │                │  watches log │
   cockpit ◄═SSE══════════════┤◄═════ bus ◄════│              │
            (live captions)   │                │   ▲          │
                              │                │   │          │
                              ▼                │   ▼          │
                           audit.jsonl         │  fallback    │
                           (also tailed by     │  player      │
                            tmux pane)         └──────────────┘
                                                       │
                                                       │ writes
                                                       ▼
                                              runs/<ts>/agent-X.log
                                              (tmux current-agent pane
                                               is tailing this file)
```

## Endpoints

| Method | Path             | Purpose |
|--------|------------------|---------|
| GET    | `/healthz`       | liveness — `{ok, shape, runId}` |
| GET    | `/shape`         | shape.yaml summary (stages, locks, celebration) |
| GET    | `/state`         | current run state (which stage active, history) |
| POST   | `/stage/:id`     | trigger a single stage (`1-extract` / `2-generate` / `3-verify`) |
| POST   | `/stage/all`     | Run All button — walks 1→2→3 with the per-stage `pause_seconds` |
| POST   | `/reset`         | wipe current run, start fresh |
| GET    | `/events`        | SSE stream of every bus event (cockpit subscribes here) |
| GET    | `/*`             | static-serve the cockpit assets from `pipeline/cockpit/` |

## SSE event taxonomy

Every event has `type` and `ts`. Common types:

- `state:ready` / `state:reset` — runId lifecycle
- `stage:start` — stage just kicked off
- `stage:caption` — a caption to fade in on the banner (from script or `[CAPTION]` markers in agent output)
- `stage:token` — token-level events from the live agent (`kind: text | thinking | tool_use | tool_result`)
- `stage:settle` — claude -p exited cleanly
- `stage:fallback` — watchdog tripped; fallback player took over (cockpit shouldn't change UX)
- `stage:complete` — stage done, either live or via fallback
- `audit` — every event also written to `runs/<ts>/audit.jsonl`

## Watchdog (silent fallback)

The runner tracks three triggers per `shape.yaml`:

1. `no_tokens_for_seconds` (default 8s) — claude went silent
2. `any_error` — process emitted error / non-zero exit
3. `exceeded_max_turns` — too many tool calls

On any trigger, the runner:
- Kills the live `claude -p` child (SIGTERM)
- Emits `stage:fallback` (cockpit logs it but doesn't surface to audience)
- Plays the matching `recordings/<stage>.tokens.jsonl` at original timings
- Emits `stage:complete` at the end with `fallback_used: true`

Audience sees no break.

If the recording isn't on disk yet (Phase 7 hasn't captured it), the fallback
player synthesises a minimal completion after 30s so the demo doesn't hang.

## Configuration

| Env             | Default                    | Notes |
|-----------------|----------------------------|-------|
| `PORT`          | 8721                       | HTTP port |
| `SHAPE`         | crud                       | which `shapes/<id>/shape.yaml` to load |
| `PIPELINE_DIR`  | (parent of `runner/`)      | root of the `pipeline/` tree |
| `PNS_SESSION`   | pns-demo                   | tmux session name (must match `tmux-launch.sh`) |

## Run

```bash
cd pipeline/runner
npm install      # one-time
npm start        # or: node --watch server.js  for dev
```

You'll see:

```
[runner] shape=crud  port=8721  pipeline=/abs/path/to/pipeline
[runner] cockpit: http://127.0.0.1:8721/
[runner] events:  http://127.0.0.1:8721/events
[runner] runId:   2026-05-15T07-12-00-000Z
```

Then in a second terminal start the tmux session:

```bash
pipeline/scripts/tmux-launch.sh --rec runs/current/recordings/session.cast
```

And open the cockpit:

```
http://127.0.0.1:8721/
```

## Limits / known sharp edges

- Spawning `claude -p` requires Anthropic credentials configured for the user
  running the runner. Auth handling is delegated to the CLI.
- The runner does NOT batch / retry on rate limits — the watchdog fires fallback
  on `any_error` so a rate limit just looks like a stalled stage.
- Tool permissions are inherited from the user's `.claude/settings.json`. For
  the demo, you almost certainly want broad pre-approval on
  `pipeline/runs/current/` and `pipeline/templates/` paths.
- The `/stage/all` endpoint waits for each stage's `stage:complete` event
  before issuing the next stage trigger. If a stage hangs and the watchdog
  never fires either, Run All will hang too. Reset is always safe.
- We do not write per-stage `.tokens.jsonl` recordings ourselves yet —
  Phase 7 captures those from a successful live run.
