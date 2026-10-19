#!/usr/bin/env bash
# watch-files.sh — watches a directory and prints the head of the most-recently
# modified file. Drives the "FILE DIFF" tmux pane so the audience sees each
# generated file appear in real time.
#
# Uses fswatch on macOS, inotifywait on Linux. `bat` is preferred for syntax
# highlighting; `cat`/`head` is a fallback.
#
# Usage: watch-files.sh <directory>

set -u

WATCH_DIR="${1:-}"
if [[ -z "$WATCH_DIR" ]]; then
  echo "usage: $0 <directory>" >&2
  exit 2
fi

if [[ ! -d "$WATCH_DIR" ]]; then
  mkdir -p "$WATCH_DIR"
fi

# Pick a renderer
if command -v bat >/dev/null 2>&1; then
  RENDER="bat --paging=never --color=always --style=numbers,grid --line-range :40"
elif command -v batcat >/dev/null 2>&1; then
  RENDER="batcat --paging=never --color=always --style=numbers,grid --line-range :40"
else
  RENDER="head -40"
fi

# Pick a watcher
WATCHER=""
if command -v fswatch >/dev/null 2>&1; then
  WATCHER="fswatch"
elif command -v inotifywait >/dev/null 2>&1; then
  WATCHER="inotifywait"
fi

if [[ -z "$WATCHER" ]]; then
  echo "$(tput setaf 3 2>/dev/null)no fswatch / inotifywait installed — file watcher disabled.$(tput sgr0 2>/dev/null)"
  echo "  install: brew install fswatch          (macOS)"
  echo "           apt-get install inotify-tools (Debian/Ubuntu)"
  echo ""
  echo "watching dir (no live updates): $WATCH_DIR"
  tail -f /dev/null
  exit 0
fi

show() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  # Ignore noise: node_modules, .venv, .git, lock files
  case "$file" in
    *node_modules*|*\.venv*|*\.git/*|*package-lock.json|*\.pyc) return 0 ;;
  esac
  clear
  printf "$(tput setaf 6 2>/dev/null)→$(tput sgr0 2>/dev/null) %s\n" "${file#$PWD/}"
  printf "$(tput dim 2>/dev/null)──────────────────────────────────────────────$(tput sgr0 2>/dev/null)\n"
  $RENDER "$file" 2>/dev/null || head -40 "$file" 2>/dev/null
}

case "$WATCHER" in
  fswatch)
    # -0 NUL-separates filenames; -r recursive; --event ... narrows
    fswatch -r -0 --event Created --event Updated \
      --exclude '/node_modules/' --exclude '/\.venv/' --exclude '/\.git/' \
      --exclude '/package-lock\.json' --exclude '\.pyc$' \
      "$WATCH_DIR" | while IFS= read -r -d '' path; do
        show "$path"
      done
    ;;
  inotifywait)
    inotifywait -m -r -q \
      --exclude '(node_modules|\.venv|\.git|package-lock\.json|\.pyc$)' \
      -e modify,create,close_write \
      --format '%w%f' \
      "$WATCH_DIR" | while IFS= read -r path; do
        show "$path"
      done
    ;;
esac
