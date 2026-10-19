# Panasa Modernisation Cockpit — demo materials

Three click-through cockpits, one per real migration engagement we've run end-to-end
through the same AI-driven pipeline. Each cockpit walks customers through the same
7-stage flow (Discovery → Comprehension → Planning → CodeGen → Self-Review →
TestGen → Dual-run) using the **actual** outputs, BR counts, file inventories, and
test results from that engagement.

## Three case studies

| File | Engagement | Source | Stack delta | Headline numbers |
|---|---|---|---|---|
| **`index.html`** | FrontAccounting POC (MWU-FA-001) | dimensions/ — 13 LOC + 1500-row UI | PHP/MySQL → FastAPI/PG/React | 5 MWUs · 4 gates passed · 285/292 tests (97.6%) |
| **`shorty/index.html`** | mikecao/shorty (PNS-SHORTY-001) | 438 PHP LOC URL shortener | PHP/PDO → FastAPI/PG | 6/6 gates · 107 tests · 20/20 parity fixtures |
| **`crud/index.html`** | chapagain/crud-php-simple (PNS-CRUD-001) | 222 PHP LOC CRUD over `users` | PHP/mysqli → FastAPI/PG + **React/shadcn SPA** | 6/6 gates · 107 tests · 14/14 API smoke · 16 visual-transformation screenshots |

The chapagain cockpit is the most recent and the only one with a frontend codegen
arm — the visible "old vs new" UI transformation customers most readily understand.
Real screenshots from the dual-run live at `migrations/crud/screenshots/`, with a
composed side-by-side mosaic at `migrations/crud/screenshots/mosaic.png`.

## The FA cockpit — live Discovery mode

The polished FA cockpit (`index.html`) walks one real FrontAccounting MWU
(`dimensions/`, MWU-FA-001) end-to-end. The Discovery stage can optionally run a
**real** Claude call against the embedded PHP source and stream findings into the
activity log.

The shorty and crud cockpits are self-contained scripted playback — open the
HTML file directly and click through.

## Two modes

| Mode | URL | What runs | Needs API key? |
|---|---|---|---|
| **Scripted** (default) | `http://localhost:3737/` | All 7 stages canned, deterministic | No |
| **Live (Discovery)** | `http://localhost:3737/?live=true` | Discovery streams from Claude; stages 2–7 stay scripted | Yes |

The live-mode hand-off is invisible to a viewer: if the proxy is unreachable
or the SSE stream stalls, the cockpit silently falls back to the scripted
Discovery timeline — the demo never gets stuck.

## One-time setup

```bash
cd demo/proxy
npm install
cp .env.example .env
# edit .env and paste your ANTHROPIC_API_KEY
```

## Run the demo

```bash
cd demo/proxy
npm start
# → [cockpit-proxy] listening on http://localhost:3737
```

Then open one of:

- **Scripted only** — `http://localhost:3737/`
- **Live Discovery** — `http://localhost:3737/?live=true`

Click **Run Discovery** (or press `→`). Reset with `R` between runs.

## What "live" actually does

1. Browser opens an SSE connection to `GET /discovery`.
2. The proxy reads every `.php` / `.inc` file under `demo/source/dimensions/`
   (9 files, ~750 LOC) and embeds them into the prompt at
   `proxy/prompt-discovery.md`.
3. Proxy calls `claude-sonnet-4-6` with `messages.stream` and forwards
   model output, **line by line**, with a strict regex filter:
   `^\[DISCOVERY\] .{8,200}$`. Anything that doesn't match (preamble, code
   fences, stray prose) is silently dropped.
4. The model also emits a final JSON summary block. The proxy parses it and
   sends a `summary` SSE event; the cockpit uses it to populate the
   `doneMeta` line, governance counters, and the artefact list.

End-to-end latency: ~25–40 seconds for ~18 findings + summary.

## Files

```
demo/
  index.html              # the cockpit (3000+ lines, single-file)
  source/dimensions/      # FA source (read-only, embedded into prompt)
  proxy/
    server.js             # Express + SSE + Anthropic SDK
    prompt-discovery.md   # the curated Discovery prompt
    package.json
    .env.example
  README.md
```

## Demo-day playbook

1. **30 min before the meeting**
   - `npm start` in `demo/proxy`.
   - Open `http://localhost:3737/?live=true` in a clean browser window.
   - Click **Run Discovery** once to confirm SSE works on this network.
   - Hit **Reset (R)** to clear.

2. **During the demo**
   - Open with the engagement strip: "FrontAccounting v2.4.19 → FastAPI / React / PG 16, Day 21 of 28."
   - Press **→** to run Discovery. The activity log streams real findings.
   - Walk the relationship graph in **Comprehension** — click `add_dimension()` and `TYPE-EXCEPTION` to land the "every claim has evidence" story.
   - **Self Review** is the credibility moment — 3 items flagged for human checkpoint, named reviewer.
   - **Gate 4** at the end: MWU-FA-001 FULLY_VALIDATED.

3. **If something goes wrong**
   - Live mode failing? Reload with `?live=false` or just `/`. Scripted runs every time.
   - Proxy crashed? Activity log will show `! SSE error — falling back to scripted`. Demo continues.
   - Browser cached old JS? Hard-reload (Cmd+Shift+R).

## Tuning

- **Model** — change `MODEL=` in `proxy/.env`. Default `claude-sonnet-4-6`.
- **Source dir** — change `SOURCE_DIR=` to point at any FA module. The prompt
  is dimensions-specific, so other modules will produce less polished output
  unless you also adapt `prompt-discovery.md`.
- **Output curation** — the `COCKPIT_LINE` regex in `proxy/server.js`
  controls what reaches the UI. Tighten it if a model run emits stray prose.
- **Fallback timing** — the cockpit gives the proxy 8s to first byte and 60s
  for the full stream. Tunable in `runLiveDiscovery()` in `index.html`.

## What's *not* in this demo

- Stages 2–7 (Comprehension → Merge) are scripted. Wiring them live is a
  next step — the architecture is the same (one prompt per stage, one SSE
  endpoint).
- The fixture is one module (`dimensions/`). For multi-module narratives you'd
  add a module-picker control and a prompt per module.
- No persistence — Reset wipes everything.
