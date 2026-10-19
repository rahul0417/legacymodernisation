# Cockpit — live demo UI

Single-page vanilla HTML/CSS/JS. No build step. Served by the runner at
`http://localhost:8721/` (or whatever `PORT` the runner uses).

```
index.html        ~80 lines     structure: HUD + banner + progress + controls + stream + celebration view
style.css         ~330 lines    terminal/tmux aesthetic, fade animations, progress dot states, celebration grid
cockpit.js        ~320 lines    SSE consumer, banner queue, dot state machine, celebration screen
```

## Two views

The page is two overlapping `<main>` elements; only one has `.active` at a time.

### `#run-view` (default)

```
┌────────────────────────────────────────────────────────────┐
│ AI MODERNISATION · chapagain → FastAPI       run · elapsed │
├────────────────────────────────────────────────────────────┤
│                                                            │
│   [BANNER — 38px caption, fades on each new event]         │
│                                                            │
├────────────────────────────────────────────────────────────┤
│ ● ─── ○ ─── ○   Extract  Generate  Verify     Continue 3s │
├────────────────────────────────────────────────────────────┤
│ [▶ Run All]  [Extract] [Generate] [Verify]   [⏸] [⟲]      │
├────────────────────────────────────────────────────────────┤
│ LIVE STREAM                                                │
│ ⚒ Read file_path=…                                         │
│ ↩ OK 1   # Discovery prompt …                              │
│ ⚒ Glob pattern=*.php                                       │
│ ↩ 7 PHP files matched                                      │
│ · thinking: I need to identify the entity first…           │
│ ▸ Found 'users' table with 4 columns                       │
└────────────────────────────────────────────────────────────┘
```

### `#celebrate-view` (after Stage 3 completes)

```
              ✓ MIGRATION COMPLETE
   chapagain/crud-php-simple → FastAPI + shadcn

   ┌─────────────────┬──────────────────────────────────┐
   │  OUTCOME        │  VISUAL TRANSFORMATION           │
   │  • 107/107      │                                  │
   │    tests pass   │      [side-by-side mosaic]       │
   │  • 14/14 API    │                                  │
   │  • 16 screens   │                                  │
   │  • 28 generated │                                  │
   │  • 73 reused    │                                  │
   └─────────────────┴──────────────────────────────────┘

   [Visit new app]  [Compare legacy]  [Send recap]  [Run again]
```

## SSE event handling

| Event             | Cockpit response |
|-------------------|------------------|
| `hello` / `state:ready` | populate run ID in HUD |
| `state:reset`     | clear panes, dots, elapsed timer; return to run-view |
| `stage:start`     | light up that stage's dot (running), start elapsed timer, clear stream |
| `stage:caption`   | fade out current banner, fade in new (200ms / 400ms) — unless captions paused, in which case queue last-only |
| `stage:token`     | append a row to the live stream (capped at 60 rows, oldest removed). Colour-coded by `kind`. |
| `stage:fallback`  | record into state; log to stream in magenta. **Audience-invisible** — no banner change. |
| `stage:complete`  | flip dot from running→done (or fallback colour if `fallback_used`). Show 3s "Continue?" countdown if `gate.continue_button`. If last stage: schedule celebration screen swap (1.5s). |
| `audit`           | absorb any inline numbers (`backend_tests_passed`, etc.) into state.numbers for the celebration screen. |

## Buttons

| Button       | Action |
|--------------|--------|
| ▶ Run All    | `POST /stage/all` — runner walks 1→2→3 with per-stage `pause_seconds` |
| Extract / Generate / Verify | `POST /stage/<id>` for individual stage |
| ⏸ Captions   | Local toggle. When paused: scripted captions land in a queue (latest-only) and replay on resume. |
| ⟲ Reset      | `POST /reset` |
| (Celebration) | one button per `shape.celebration.buttons[]` in `shape.yaml`. `open_url` opens in new tab; `reset` calls `/reset`; `run_script` prints an alert (TODO Phase 8). |

## Keyboard shortcuts

- `Space` — Run All
- `R` — Reset
- `P` — Pause captions
- `Esc` — Local UI reset (without server reset)

## Connection indicator

Top-right `LIVE`/`reconnecting…` dot. Driven by `EventSource` `onopen` / `onerror`.

## Mosaic path

When showing celebration, cockpit tries to load `/runs/<runId>/screenshots/mosaic.png`
(the path Stage 3's `compose-mosaic.py` writes). If 404, the fallback message
"Mosaic will appear once Stage 3 captures the 16 screenshots" stays visible.

The runner currently serves `/runs/*` via the same static handler (path traversal
guards in place). If you move the runs directory off-tree, you'll need a small
proxy in `server.js`.

## Visual aesthetic

- Background: `#0b0e14` (very dark navy)
- Accent: `#4dd0e1` (cyan) — section labels, banner highlight
- Action green: `#3aa66b` / glow `#15c277` — primary buttons, done dots
- Amber `#ffd166` — tool_use stream events, fallback dots
- Magenta `#d28cff` — system / spawn events
- Muted dim `#6b7785` — ambient text
- Monospace throughout (SF Mono / JetBrains Mono fallback)

The aesthetic deliberately matches `session-replay/` and the v1 `demo/crud/`
cockpit so the three artefacts feel coherent if shown together.
