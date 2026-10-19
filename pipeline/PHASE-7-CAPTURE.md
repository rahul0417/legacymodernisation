# Phase 7 — capture the fallback recordings

You run the live pipeline **once successfully** for each stage. The runner saves
every SSE event to `runs/<id>/recordings/<stage>.tokens.jsonl`. Then you promote
those files into `shapes/crud/recordings/` where the watchdog's fallback player
loads them on any future failure.

The recordings are **committed assets**. Once captured, every sales-call demo
plays them on watchdog trigger — no API/subscription burn unless the LIVE path
runs successfully.

## Prerequisites

| What | How |
|---|---|
| `claude` CLI | `npm i -g @anthropic-ai/claude-code` (or whatever install you use) |
| **Subscription auth** (not API) | `claude login` once. Picks your Claude.ai Pro / Max / Team account. Stored in `~/.claude/auth.json` (or platform equivalent). |
| Verify subscription auth | `unset ANTHROPIC_API_KEY  &&  claude config get-account` should show your Claude.ai email. If `ANTHROPIC_API_KEY` is set in your shell, `claude -p` may prefer it — unset it for the capture. |
| `tmux`, `asciinema`, `fswatch`, `bat` | `brew install tmux asciinema fswatch bat` |

## Cost expectation (subscription)

| Stage | Approx tokens out | Approx tokens in |
|---|---|---|
| 1 — Extract | 5K | 30K |
| 2 — Generate | 30K | 80K |
| 3 — Verify | 15K | 40K |
| **One capture run** | **~50K out** | **~150K in** |

A Pro subscription typically handles this comfortably in one weekly window. Max
handles it without thinking. The capture only happens **once per prompt
revision** — subsequent demos replay the recordings.

## Capture procedure

```bash
cd legacymodernisation/pipeline

# (1) Make sure subscription auth is the active credential, not API
unset ANTHROPIC_API_KEY
claude config get-account               # confirm: should show your Claude.ai email

# (2) Bring up the tmux session + start asciinema (one terminal)
./scripts/tmux-launch.sh --rec runs/current/recordings/session.cast

#     (asciinema will print 'recording' — leave this terminal alone)

# (3) In a second terminal: start the runner with PNS_RECORD=1
cd legacymodernisation/pipeline
PNS_RECORD=1 npm --prefix runner start

# (4) In a third terminal / browser: open the cockpit and click Run All
open http://127.0.0.1:8721/
#     → click ▶ Run All
#     → watch the 3 stages complete (~12 min total for a successful run)
#     → cockpit lands on the celebration screen when Stage 3 finishes

# (5) Stop the runner (Ctrl-C in its terminal)
#     Detach from tmux (Ctrl-B, then D) — asciinema saves session.cast

# (6) Promote the captured recordings into shapes/crud/recordings/
./scripts/promote-recordings.sh current crud

#     Output:
#       ✓ promoted 1-extract.tokens.jsonl  (NNN bytes)
#       ✓ promoted 2-generate.tokens.jsonl (NNN bytes)
#       ✓ promoted 3-verify.tokens.jsonl   (NNN bytes)
#       Promoted 3 recording(s) to: .../shapes/crud/recordings

# (7) (Optional) Also promote the asciinema cast for each stage if you
#     have one. tmux-launch.sh records the whole session as one .cast file;
#     if you want per-stage `.cast` files for richer fallback, split with
#     asciinema's --idle-time-limit option on each stage run, or use OBS
#     to capture each stage's pane separately. For first cut, the whole-
#     session cast in runs/<id>/recordings/session.cast is the artefact.
```

## Verifying the capture

After promotion, check the committed recordings:

```bash
ls -la shapes/crud/recordings/
# expect:
#   1-extract.tokens.jsonl    a few KB
#   2-generate.tokens.jsonl   tens of KB
#   3-verify.tokens.jsonl     tens of KB
```

Each file should:
- Be valid JSONL (one event per line)
- Have `stage:start` as the first event and `stage:complete` near the end
- Cover a duration that roughly matches the stage's `expected_duration_seconds`

A quick check:

```bash
for f in shapes/crud/recordings/*.tokens.jsonl; do
  total=$(wc -l < "$f")
  first=$(head -1 "$f" | python3 -c 'import sys, json; print(json.loads(sys.stdin.read()).get("type", "?"))')
  last=$(tail -1 "$f" | python3 -c 'import sys, json; print(json.loads(sys.stdin.read()).get("type", "?"))')
  echo "$(basename $f): $total events · first=$first · last=$last"
done
```

## When to re-capture

You only re-capture when something that affects the live path changes:

| Change | Re-capture needed? |
|---|---|
| Prompt edit (`shapes/crud/prompts/*.md`) | yes — agent output will differ |
| Captions edit (`shapes/crud/captions/*.json`) | no — captions play independently |
| Template change (`templates/**`) | yes — generated files will differ |
| Cockpit UI change | no |
| Runner code change | no, usually |
| New shape added | yes for that shape |

## Testing the fallback

After Phase 7 is done, you can verify the fallback works end-to-end (this is
Phase 8) by killing the runner mid-stage. The cockpit should silently switch
to the recorded replay and complete the stage normally. Audience-invisible.

```bash
# Terminal 1: start runner + cockpit + click Run All
# Terminal 2 (while Stage 2 is running): kill the runner with SIGKILL
pkill -9 -f 'node server.js'
# → cockpit detects connection drop on the next event tick
# → restart runner: PNS_RECORD=0 npm --prefix runner start
# → fallback kicks in: cockpit catches up via /events SSE and watchdog
#   triggers fallback replay for any incomplete stage
```

(Phase 8 will add an explicit "simulate failure" button to the runner for
deterministic fallback testing without killing the process.)
