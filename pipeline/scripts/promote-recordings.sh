#!/usr/bin/env bash
# promote-recordings.sh — copy a successful run's fallback recordings
# (`.tokens.jsonl` + optional `.cast`) into the shape's committed
# `recordings/` directory. The watchdog's fallback player picks them up
# from there on any future demo.
#
# Usage:
#   promote-recordings.sh <run-id> [shape-id]
#
# Defaults:
#   shape-id = crud
#
# Run-id can be a timestamp (matches a directory under pipeline/runs/) or
# the literal "current" to use the latest run.

set -eu

PIPE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_ID="${1:-current}"
SHAPE_ID="${2:-crud}"

if [[ "$RUN_ID" == "current" ]]; then
  RUN_DIR="$PIPE_DIR/runs/current"
  if [[ -L "$RUN_DIR" ]]; then
    RUN_DIR="$(readlink "$RUN_DIR")"
  fi
else
  RUN_DIR="$PIPE_DIR/runs/$RUN_ID"
fi

if [[ ! -d "$RUN_DIR" ]]; then
  echo "run dir not found: $RUN_DIR" >&2
  exit 1
fi

SHAPE_REC_DIR="$PIPE_DIR/shapes/$SHAPE_ID/recordings"
SRC_REC_DIR="$RUN_DIR/recordings"

if [[ ! -d "$SRC_REC_DIR" ]]; then
  echo "no recordings/ under $RUN_DIR — did you run with PNS_RECORD=1?" >&2
  exit 1
fi

mkdir -p "$SHAPE_REC_DIR"

# Promote each <stage>.tokens.jsonl and matching <stage>.cast (if asciinema cast exists)
promoted=0
skipped=0
for src in "$SRC_REC_DIR"/*.tokens.jsonl; do
  [[ -f "$src" ]] || continue
  base="$(basename "$src" .tokens.jsonl)"
  size=$(wc -c < "$src" | tr -d ' ')
  if [[ "$size" -lt 100 ]]; then
    echo "  ✗ skipping $base — recording empty/too small ($size bytes); did the stage complete?" >&2
    skipped=$((skipped+1))
    continue
  fi
  cp "$src" "$SHAPE_REC_DIR/$base.tokens.jsonl"
  echo "  ✓ promoted $base.tokens.jsonl ($size bytes)"
  promoted=$((promoted+1))

  # asciinema cast — same basename if present
  if [[ -f "$SRC_REC_DIR/$base.cast" ]]; then
    cp "$SRC_REC_DIR/$base.cast" "$SHAPE_REC_DIR/$base.cast"
    echo "  ✓ promoted $base.cast"
  fi
done

echo ""
echo "Promoted $promoted recording(s) to: $SHAPE_REC_DIR"
if [[ $skipped -gt 0 ]]; then
  echo "Skipped $skipped (probably incomplete stages)."
  exit 2
fi

ls -la "$SHAPE_REC_DIR"
