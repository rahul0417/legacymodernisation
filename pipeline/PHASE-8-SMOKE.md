# Phase 8 — end-to-end smoke + simulated-failure verification

The pre-flight checklist a salesperson runs **before each sales call** to
prove the demo will stand up cleanly. Three layered checks: structural,
button-driven happy path, and silent-fallback verification.

## 1. Structural smoke (1 min · no API/subscription)

Runs the deterministic checks. Doesn't invoke `claude` or hit the network.

```bash
cd legacymodernisation/pipeline

# Self-Review script against the v1 reference tree (sanity baseline)
./scripts/self-review.sh ../migrations/crud/generated
# Expect: SUMMARY: 12 PASS · 0 FAIL

# Runner boot + endpoint sanity
cd runner && PORT=8721 npm start &
sleep 2
curl -fsS http://127.0.0.1:8721/healthz                 # → {ok:true, shape:crud}
curl -fsS http://127.0.0.1:8721/shape | head -3
curl -fsS http://127.0.0.1:8721/runs/current/audit.jsonl | head -1
kill %1 && wait
```

If any of these fails, **don't proceed to the live demo.** Fix structural
issues first.

## 2. Devtools-driven fallback verification (3 min · no API)

Confirms the silent-fallback path works **even without `claude` running**.
This is the critical sales-call safety net.

```bash
# Start runner
cd legacymodernisation/pipeline/runner && PORT=8721 npm start &
RUNNER=$!
sleep 2

# Open cockpit IN DEVTOOLS MODE
open "http://127.0.0.1:8721/?devtools=1"

# In the browser:
#  (a) Click  ▶ Run All
#  (b) Wait ~1 second after the first stage starts
#  (c) Click 🚨 Simulate failure (bottom-right devtools panel)
#  (d) Observe: 
#       - banner stays cycling scripted captions (audience-invisible)
#       - live stream shows "(simulated failure on 1-extract)" 
#         and "(fallback engaged for 1-extract: simulated via POST /simulate/fallback)"
#       - the stage dot eventually flips to amber (fallback colour)
#       - run advances to the next stage normally
#  (e) Repeat for Stage 2 and Stage 3 — all should fall back silently
#  (f) Celebration screen appears at the end, "Fallback engaged: 3 stage(s)"

kill $RUNNER && wait
```

**Pass criteria:**
- Cockpit never shows an error to the audience
- Captions keep flowing (the caption-player is independent of agent state)
- All 3 dots reach a terminal colour (done/fallback)
- Celebration screen appears
- Audit log has `stage_fallback` events per stage (`curl /runs/current/audit.jsonl`)

## 3. Live happy-path verification (15 min · burns ~50K subscription tokens)

Only do this if you've **already captured** the fallback recordings (Phase 7)
OR if you're capturing them for the first time. Otherwise skip — the
devtools fallback above is sufficient pre-call confidence.

```bash
# Same as Phase 7 capture, but verify silent fallback works mid-stage
unset ANTHROPIC_API_KEY
claude config get-account     # should show your Claude.ai email

cd legacymodernisation/pipeline
./scripts/tmux-launch.sh
PNS_RECORD=0 npm --prefix runner start &     # PNS_RECORD off → uses promoted recordings
open "http://127.0.0.1:8721/?devtools=1"

# In the browser:
#  (a) Click ▶ Run All
#  (b) During Stage 2 (the longest one), click 🚨 Simulate failure
#  (c) Observe: cockpit briefly shows fallback msg in live stream,
#       captions continue, replay from shapes/crud/recordings/ kicks in
#  (d) Stage completes via fallback, advances to Stage 3
#  (e) Stage 3 runs live → completes → celebration screen with the mosaic
```

**Pass criteria** (additional to (2)):
- Stage 1 + 3 run live (real `claude -p` output streams to tmux current-agent pane)
- Stage 2 silently switches to recorded replay mid-run
- Final celebration shows mosaic + correct numbers
- Audit log shows `fallback_used:true` only for Stage 2

## When to run each level

| Before a... | Level 1 | Level 2 | Level 3 |
|---|---|---|---|
| Daily lunch demo | ✓ | — | — |
| Internal review meeting | ✓ | ✓ | — |
| External customer call | ✓ | ✓ | ✓ |
| Marketing recording | ✓ | ✓ | ✓ |

## Common failures and fixes

| Symptom | Cause | Fix |
|---|---|---|
| Runner boot says `EADDRINUSE` | Another process on port 8721 | `lsof -i :8721` and kill, or `PORT=8722 npm start` |
| Cockpit shows "offline" / "reconnecting…" | Runner not running | Restart runner; cockpit auto-reconnects |
| Simulate failure returns 400 | No stage currently running | Click a stage button first, then simulate |
| Devtools panel doesn't appear | URL missing `?devtools=1` | Add the query param |
| Fallback player synthesises (no recording) | Phase 7 not done | Run the capture procedure in `PHASE-7-CAPTURE.md` |
| Audit log path returns 404 over HTTP | `runs/current` symlink missing | Hit `POST /reset` to re-create the symlink |
| Stage dot stuck on "running" forever | Watchdog didn't fire (rare; only with very slow tokens) | Click 🚨 Simulate failure |

## What's intentionally NOT in Phase 8

- Recording validation (PHASE-7-CAPTURE has its own verification commands)
- API-key-vs-subscription auth diagnosis (out of pipeline scope — `claude` CLI tooling)
- Network-level chaos testing (deferred to Phase N — a future "chaos mode" button could randomly drop SSE events, throttle responses, etc.)
- Multi-user / multi-engagement support (single app, single user assumption per shape.yaml)
