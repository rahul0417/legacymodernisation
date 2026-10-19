#!/usr/bin/env python3
"""Pretty-print audit.jsonl events as they're appended.

Reads JSONL from stdin (one event per line), renders each as a single
colour-coded line with HH:MM:SS · event-name · key fields. Intended to
be the tmux audit pane's continuous tail target:

    tail -F runs/<ts>/audit.jsonl | audit-pretty.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime


# ANSI palette — matches the cockpit's accent colours so it feels coherent.
COLORS = {
    "engagement_created":    "\033[1;36m",   # bright cyan
    "stage_start":           "\033[36m",     # cyan
    "stage_complete":        "\033[32m",     # green
    "agent_spawn":           "\033[35m",     # magenta
    "agent_done":            "\033[34m",     # blue
    "gate_decision":         "\033[1;32m",   # bright green
    "critical_fix_applied":  "\033[33m",     # yellow
    "dual_run_fix":          "\033[33m",
    "screenshot_capture_complete": "\033[34m",
    "api_smoke_complete":    "\033[32m",
    "engagement_complete":   "\033[1;32m",
}
RESET = "\033[0m"
DIM   = "\033[2m"
BOLD  = "\033[1m"


# Which extra fields to surface inline per event kind.
INLINE_FIELDS = ["stage", "gate", "status", "verdict", "agent", "fix",
                 "fixtures", "pass", "fail", "total", "engagement",
                 "backend_tests_total", "frontend_tests_total"]


def short_ts(ts: str | None) -> str:
    if not ts:
        return "--:--:--"
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M:%S")
    except Exception:
        return ts[11:19] if len(ts) >= 19 else ts[:8]


def fmt(event: dict) -> str:
    ts = short_ts(event.get("ts"))
    ev = event.get("event", "?")
    colour = COLORS.get(ev, "")
    parts = []
    for k in INLINE_FIELDS:
        if k in event:
            v = event[k]
            if isinstance(v, (dict, list)):
                v = json.dumps(v)[:40]
            parts.append(f"{k}={v}")
        if len(parts) >= 4:
            break
    tail = " · ".join(parts)
    return f"{DIM}{ts}{RESET}  {colour}{ev:24}{RESET}  {DIM}{tail}{RESET}"


def main() -> int:
    try:
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                print(f"{DIM}[malformed]{RESET} {line[:90]}", flush=True)
                continue
            print(fmt(event), flush=True)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
