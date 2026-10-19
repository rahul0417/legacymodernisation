# Claude Code session replay

Renders any Claude Code session — including all spawned subagents — as a
multi-pane animated timeline in the browser. Built so background agents
that normally hide behind ctrl+o / ctrl+b become **visible by construction**:
each Agent spawn opens a new pane in the agent strip and streams its
transcript while the main thread keeps going.

## Inputs

Claude Code writes everything we need automatically:

- **Main session JSONL** — one file per session at
  `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`
- **Subagent JSONLs** — one per Agent spawn at
  `~/.claude/projects/<encoded-cwd>/<session-id>/subagents/agent-<id>.jsonl`
  (sidecar `agent-<id>.meta.json` has the type + description)

## Build the timeline

```bash
python3 build.py \
  --session ~/.claude/projects/<encoded-cwd>/<session-id>.jsonl \
  --subagents-dir ~/.claude/projects/<encoded-cwd>/<session-id>/subagents \
  --out timeline.json
```

The build script:

1. Walks the main JSONL and emits one event per assistant content part
   (text / thinking / tool_use) and per tool_result.
2. Detects every Agent tool_use, captures the agent_id from its
   tool_result, and reads the matching subagent JSONL.
3. **Dedupes by agent_id** — if an agent was continued via SendMessage,
   the same JSONL is referenced from multiple tool_use_ids and must be
   processed exactly once.
4. Tags each event with a pane (`main` or `agent-<short>`), normalises
   the timestamp to ms-from-start, and writes a flat sorted array.
5. Injects synthetic `agent_spawn` / `agent_done` events into the
   `system` pane so the player can animate pane appearances.

PNS-CRUD-001 baseline: 3,724 events, 12 agents, 30h 51m wall-clock,
3.6MB timeline.json.

## Play it

```bash
python3 -m http.server 8765
open http://127.0.0.1:8765/replay.html
```

Controls:

- `Space` — play / pause
- `R` — reset to t=0
- speed selector — 1× / 10× / 60× / 300× (default) / 1000× / instant
- skip-idle — gaps >10s of real session time compress to 500ms in playback
- scrub bar — drag to any moment; spawn ticks (✦) mark each agent's launch

## Layout

```
┌──────────────────────────────────────────────────────────┐
│  SESSION REPLAY · <session-id> · [▶ Play] [speed: 300×]  │
│  ────[ scrubber with ✦ ticks per agent spawn ]──────────  │
├─────────────────────────────────────┬────────────────────┤
│                                     │  agent-ae99b2c7    │
│  main · orchestrator                │  Discovery on…     │
│                                     │  ▸ Read file…      │
│  ▸ USER: how do we ...              │  ▸ Glob ...        │
│  💭 THINK: ...                       │                    │
│  ● CLAUDE: yes, ...                 ├────────────────────┤
│  ⚒ Bash(...)                        │  agent-aa516bc2    │
│  ↩ OK ...                           │  Comprehension     │
│  ⚒ Agent(...) → ✦ SPAWN             │  ▸ Read ...        │
│  ● CLAUDE: ...                      │  💭 thinking...     │
│                                     │  ⚒ Bash ...        │
│                                     │  ↩ OK              │
└─────────────────────────────────────┴────────────────────┘
```

When an `agent_spawn` event fires, a new pane animates in from the right.
The agent's own tool calls + tool results + text + thinking blocks stream
into that pane in real time. When its last event fires, the pane border
flips to the `done` colour.

## Recording the playback to MP4

Playwright headless can drive the page and record at the same time:

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(
        viewport={"width": 1600, "height": 900},
        record_video_dir="recordings/",
        record_video_size={"width": 1600, "height": 900},
    )
    page = ctx.new_page()
    page.goto("http://127.0.0.1:8765/replay.html")
    page.wait_for_selector('#time-total:not(:has-text("00:00:00"))')
    page.evaluate("document.getElementById('speed').value = '60'")  # 1 min wall = 1h session
    page.click('#btn-play')
    page.wait_for_function("document.getElementById('stat-events').textContent === document.getElementById('mainMeta')?.dataset.total || true", timeout=600_000)
    ctx.close()  # flushes the video
```

WebM will land in `recordings/`. Convert to MP4 if you want broader
compatibility: `ffmpeg -i in.webm -c:v libx264 -pix_fmt yuv420p out.mp4`.

## Limits / known sharp edges

- The build script truncates each text/tool result to 6,000 chars and
  each tool input field to 600 chars so `timeline.json` stays under
  ~5MB. Adjust `MAX_TEXT` / `MAX_TOOL_INPUT` in `build.py` if you want
  full fidelity (it costs file size and DOM rendering speed).
- `thinking` blocks render collapsed by default — click to expand. The
  full thinking text is in the DOM, just hidden in a `<details>`.
- One pane per agent. Agents continued via SendMessage that produce
  many separate sessions in the same JSONL are not currently split
  back out per session; the whole agent timeline is one pane.
- The scrub bar jumps INSTANTLY to its target position (re-renders all
  events up to that point). That's correct for navigation but means
  scrubbing during playback skips the animation; pause first if you
  want to scrub-then-play.
