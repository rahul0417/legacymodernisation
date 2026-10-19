#!/usr/bin/env bash
# tmux-launch.sh — sets up the 4-pane demo tmux session.
#
# Layout:
#   ┌────────────────────┬────────────────────┐
#   │  pane 0            │  pane 1            │
#   │  ORCHESTRATOR      │  CURRENT AGENT     │
#   │  (banner +         │  (claude -p stream │
#   │   captions echo)   │   per stage)       │
#   ├────────────────────┼────────────────────┤
#   │  pane 2            │  pane 3            │
#   │  AUDIT TAIL        │  FILE DIFF         │
#   │  (jsonl prettified)│  (latest write)    │
#   └────────────────────┴────────────────────┘
#
# Usage:
#   tmux-launch.sh                # set up session + print attach hint
#   tmux-launch.sh --attach       # set up + attach immediately
#   tmux-launch.sh --rec <path>   # set up + asciinema record into <path>
#
# Env:
#   PNS_SESSION  default 'pns-demo'
#   RUN_DIR      default pipeline/runs/current  (symlink the runner maintains)

set -eu

SESSION="${PNS_SESSION:-pns-demo}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIPE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUN_DIR="${RUN_DIR:-$PIPE_DIR/runs/current}"

mode="ready"
rec_path=""
case "${1:-}" in
  --attach) mode="attach" ;;
  --rec)    mode="rec"; rec_path="${2:-$RUN_DIR/recordings/session.cast}" ;;
  "")       ;;
  *)        echo "usage: $0 [--attach | --rec <path>]" >&2; exit 2 ;;
esac

# Pre-flight
command -v tmux >/dev/null || { echo "tmux not installed" >&2; exit 1; }
mkdir -p "$RUN_DIR"/recordings
[[ -f "$RUN_DIR/audit.jsonl" ]] || : > "$RUN_DIR/audit.jsonl"
mkdir -p "$RUN_DIR/generated"

# Tear down any prior session
tmux kill-session -t "$SESSION" 2>/dev/null || true

# Create + lay out (240x60 base so panes fit on a 1440p screen)
tmux new-session -d -s "$SESSION" -n main -x 240 -y 60

# Split horizontally → pane 0 (left) + pane 1 (right)
tmux split-window -h -t "$SESSION:main.0"
# Split pane 0 vertically → pane 0 (TL) + pane 2 (BL)
tmux split-window -v -t "$SESSION:main.0"
# Split pane 1 vertically → pane 1 (TR) + pane 3 (BR)
tmux split-window -v -t "$SESSION:main.1"
# Balance: 2x2 tiled
tmux select-layout -t "$SESSION:main" tiled

# Status bar + theme — minimal, demo-friendly
tmux set-option -t "$SESSION" status on
tmux set-option -t "$SESSION" status-style 'bg=#0a0d12,fg=#4dd0e1'
tmux set-option -t "$SESSION" status-left-length 40
tmux set-option -t "$SESSION" status-left ' #[bold]PNS DEMO#[default] · #S '
tmux set-option -t "$SESSION" status-right '#[fg=#6b7785]%H:%M:%S '
tmux set-option -t "$SESSION" pane-border-status top
tmux set-option -t "$SESSION" pane-active-border-style 'fg=#3aa66b'
tmux set-option -t "$SESSION" pane-border-style 'fg=#2a3441'

# Label each pane via its border title
tmux select-pane -t "$SESSION:main.0" -T 'ORCHESTRATOR'
tmux select-pane -t "$SESSION:main.1" -T 'CURRENT AGENT'
tmux select-pane -t "$SESSION:main.2" -T 'AUDIT'
tmux select-pane -t "$SESSION:main.3" -T 'FILE DIFF'

# Pane 0: orchestrator — placeholder until runner starts writing here
tmux send-keys -t "$SESSION:main.0" \
  "clear; printf '\\033[1;36m▸ Orchestrator ready.\\033[0m\\n'; printf '\\033[2mClick a stage button in the cockpit to begin.\\033[0m\\n'" Enter

# Pane 1: current-agent — placeholder; runner overwrites per stage
tmux send-keys -t "$SESSION:main.1" \
  "clear; printf '\\033[1;33m▸ No agent running.\\033[0m\\n'; printf '\\033[2mPer-stage claude -p output will appear here.\\033[0m\\n'" Enter

# Pane 2: audit tail
tmux send-keys -t "$SESSION:main.2" \
  "clear; printf '\\033[1;35m▸ Audit log\\033[0m \\033[2m(tail -F $RUN_DIR/audit.jsonl)\\033[0m\\n\\n'; tail -F '$RUN_DIR/audit.jsonl' | python3 '$SCRIPT_DIR/audit-pretty.py'" Enter

# Pane 3: file diff watcher
tmux send-keys -t "$SESSION:main.3" \
  "clear; printf '\\033[1;34m▸ File watcher\\033[0m \\033[2m($RUN_DIR/generated)\\033[0m\\n\\n'; '$SCRIPT_DIR/watch-files.sh' '$RUN_DIR/generated'" Enter

# Focus orchestrator pane on attach
tmux select-pane -t "$SESSION:main.0"

# Outcome
case "$mode" in
  attach)
    exec tmux attach -t "$SESSION"
    ;;
  rec)
    mkdir -p "$(dirname "$rec_path")"
    command -v asciinema >/dev/null || { echo "asciinema not installed (brew install asciinema / apt-get install asciinema)" >&2; exit 1; }
    echo "Recording session to $rec_path"
    exec asciinema rec --command "tmux attach -t $SESSION" "$rec_path"
    ;;
  ready)
    echo "tmux session '$SESSION' is ready."
    echo ""
    echo "  Attach:        tmux attach -t $SESSION"
    echo "  Record + run:  $0 --rec ${rec_path:-$RUN_DIR/recordings/session.cast}"
    echo "  Kill:          tmux kill-session -t $SESSION"
    ;;
esac
