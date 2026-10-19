"""Build a flat replay timeline from a Claude Code session + its subagent JSONLs.

Inputs:
  - main session JSONL (the conversation between user and orchestrator-Claude)
  - subagent JSONLs (one per Agent tool_use), discovered via tool_result text

Output:
  - timeline.json — a single JSON array of events ordered by real timestamp,
    suitable for client-side animated playback in replay.html.

Each event:
  {
    "t":       <ms from session start>,
    "ts":      "<ISO8601>",
    "pane":    "main" | "agent-<short id>",
    "kind":    "user" | "text" | "thinking" | "tool_use" | "tool_result"
               | "agent_spawn" | "agent_done" | "system",
    "data":    { ... }
  }
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Iterable


AGENT_ID_RE = re.compile(r"agentId:\s*([a-f0-9]{15,})")
MAX_TEXT = 6000      # cap any single text/tool result we embed in the timeline
MAX_TOOL_INPUT = 600 # truncate large tool inputs (e.g. Write bodies) for display


def iso_to_ms(ts: str | None) -> int | None:
    if not ts:
        return None
    # session JSONL writes ts with trailing 'Z' or '+00:00'; normalize.
    cleaned = ts.replace("Z", "+00:00")
    try:
        return int(dt.datetime.fromisoformat(cleaned).timestamp() * 1000)
    except ValueError:
        return None


def short_id(agent_id: str) -> str:
    return agent_id[:8]


def load_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def truncate(s: str | None, limit: int) -> str:
    if not s:
        return ""
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n… [truncated, {len(s) - limit} more chars]"


def normalise_tool_input(name: str, inp: dict | None) -> dict:
    """Strip giant fields so the timeline.json stays small."""
    if not inp:
        return {}
    cleaned: dict[str, Any] = {}
    for k, v in inp.items():
        if isinstance(v, str) and len(v) > MAX_TOOL_INPUT:
            cleaned[k] = v[:MAX_TOOL_INPUT] + f" … (+{len(v) - MAX_TOOL_INPUT} chars)"
        elif isinstance(v, (dict, list)):
            try:
                blob = json.dumps(v)
                if len(blob) > MAX_TOOL_INPUT:
                    cleaned[k] = blob[:MAX_TOOL_INPUT] + " … (truncated)"
                else:
                    cleaned[k] = v
            except Exception:
                cleaned[k] = "<unserialisable>"
        else:
            cleaned[k] = v
    # name is useful both at top level and in input echo
    cleaned["_name"] = name
    return cleaned


def stringify_tool_result(content: Any) -> str:
    """Tool results in Claude Code JSONL come as either a string or
    a list of {type: 'text', text: ...} parts. Flatten to a string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                if p.get("type") == "text":
                    parts.append(p.get("text", ""))
                elif p.get("type") == "image":
                    parts.append("[image]")
                else:
                    parts.append(json.dumps(p)[:200])
            else:
                parts.append(str(p))
        return "\n".join(parts)
    return json.dumps(content)


def find_agent_id_in_tool_result(text: str) -> str | None:
    m = AGENT_ID_RE.search(text)
    return m.group(1) if m else None


def build_main_events(session_path: Path) -> list[dict]:
    """Walk the main session JSONL and emit a list of pane-tagged events.

    We also collect a map of tool_use_id -> agent_id so the agent-pane
    timeline knows when its parent invocation happened.
    """
    events: list[dict] = []
    tool_id_to_agent: dict[str, str] = {}

    for entry in load_jsonl(session_path):
        kind = entry.get("type")
        ts = entry.get("timestamp")
        t_ms = iso_to_ms(ts)
        if t_ms is None:
            continue

        if kind == "user":
            msg = entry.get("message", {}) or {}
            content = msg.get("content")
            # user messages may be plain text OR a list with tool_result parts
            if isinstance(content, str):
                events.append({
                    "ts": ts, "t_ms": t_ms, "pane": "main",
                    "kind": "user", "data": {"text": truncate(content, MAX_TEXT)},
                })
            elif isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    ptype = part.get("type")
                    if ptype == "tool_result":
                        result_text = stringify_tool_result(part.get("content"))
                        tool_use_id = part.get("tool_use_id")
                        # if this is an Agent-launch reply, capture the agentId
                        agent_id = find_agent_id_in_tool_result(result_text)
                        if agent_id and tool_use_id:
                            tool_id_to_agent[tool_use_id] = agent_id
                        events.append({
                            "ts": ts, "t_ms": t_ms, "pane": "main",
                            "kind": "tool_result",
                            "data": {
                                "tool_use_id": tool_use_id,
                                "is_error": bool(part.get("is_error")),
                                "text": truncate(result_text, MAX_TEXT),
                                "agent_id": agent_id,
                            },
                        })
                    elif ptype == "text":
                        events.append({
                            "ts": ts, "t_ms": t_ms, "pane": "main",
                            "kind": "user", "data": {"text": truncate(part.get("text", ""), MAX_TEXT)},
                        })

        elif kind == "assistant":
            msg = entry.get("message", {}) or {}
            content = msg.get("content") or []
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype == "text":
                    events.append({
                        "ts": ts, "t_ms": t_ms, "pane": "main",
                        "kind": "text", "data": {"text": truncate(part.get("text", ""), MAX_TEXT)},
                    })
                elif ptype == "thinking":
                    events.append({
                        "ts": ts, "t_ms": t_ms, "pane": "main",
                        "kind": "thinking",
                        "data": {"text": truncate(part.get("thinking", ""), MAX_TEXT)},
                    })
                elif ptype == "tool_use":
                    events.append({
                        "ts": ts, "t_ms": t_ms, "pane": "main",
                        "kind": "tool_use",
                        "data": {
                            "id": part.get("id"),
                            "name": part.get("name"),
                            "input": normalise_tool_input(part.get("name", ""), part.get("input")),
                        },
                    })

    return events, tool_id_to_agent


def build_agent_events(agent_jsonl: Path, agent_id: str, pane: str) -> list[dict]:
    """Translate a subagent JSONL into pane-tagged events."""
    events: list[dict] = []
    for entry in load_jsonl(agent_jsonl):
        ts = entry.get("timestamp")
        t_ms = iso_to_ms(ts)
        if t_ms is None:
            continue
        kind = entry.get("type")
        if kind == "assistant":
            msg = entry.get("message", {}) or {}
            content = msg.get("content") or []
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype == "text":
                    events.append({
                        "ts": ts, "t_ms": t_ms, "pane": pane,
                        "kind": "text",
                        "data": {"text": truncate(part.get("text", ""), MAX_TEXT)},
                    })
                elif ptype == "thinking":
                    events.append({
                        "ts": ts, "t_ms": t_ms, "pane": pane,
                        "kind": "thinking",
                        "data": {"text": truncate(part.get("thinking", ""), MAX_TEXT)},
                    })
                elif ptype == "tool_use":
                    events.append({
                        "ts": ts, "t_ms": t_ms, "pane": pane,
                        "kind": "tool_use",
                        "data": {
                            "id": part.get("id"),
                            "name": part.get("name"),
                            "input": normalise_tool_input(part.get("name", ""), part.get("input")),
                        },
                    })
        elif kind == "user":
            msg = entry.get("message", {}) or {}
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "tool_result":
                        events.append({
                            "ts": ts, "t_ms": t_ms, "pane": pane,
                            "kind": "tool_result",
                            "data": {
                                "tool_use_id": part.get("tool_use_id"),
                                "is_error": bool(part.get("is_error")),
                                "text": truncate(stringify_tool_result(part.get("content")), MAX_TEXT),
                            },
                        })
    return events


def load_agent_meta(subagents_dir: Path, agent_id: str) -> dict:
    meta_path = subagents_dir / f"agent-{agent_id}.meta.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--session",
        required=True,
        type=Path,
        help="Path to the main session JSONL (the orchestrator conversation).",
    )
    parser.add_argument(
        "--subagents-dir",
        required=True,
        type=Path,
        help="Directory holding agent-<id>.jsonl + .meta.json files.",
    )
    parser.add_argument(
        "--out",
        default=Path(__file__).resolve().parent / "timeline.json",
        type=Path,
    )
    args = parser.parse_args()

    main_events, tool_to_agent = build_main_events(args.session)

    # Build agent panes — dedupe by agent_id (an agent may have been continued
    # via SendMessage, in which case multiple tool_use_ids map to the same id
    # and we must not double-process its JSONL).
    agents_meta: dict[str, dict] = {}
    agent_events: list[dict] = []
    seen_agent_ids: set[str] = set()
    # process in order of first appearance
    first_tool_for_agent: dict[str, str] = {}
    for tool_id, agent_id in tool_to_agent.items():
        if agent_id not in first_tool_for_agent:
            first_tool_for_agent[agent_id] = tool_id
    for agent_id, tool_id in first_tool_for_agent.items():
        if agent_id in seen_agent_ids:
            continue
        seen_agent_ids.add(agent_id)
        agent_jsonl = args.subagents_dir / f"agent-{agent_id}.jsonl"
        if not agent_jsonl.exists():
            continue
        pane = f"agent-{short_id(agent_id)}"
        meta = load_agent_meta(args.subagents_dir, agent_id)
        agents_meta[pane] = {
            "agent_id": agent_id,
            "type": meta.get("agentType", "general-purpose"),
            "description": meta.get("description", "(no description)"),
            "tool_use_id": tool_id,
        }
        agent_events.extend(build_agent_events(agent_jsonl, agent_id, pane))

    # Inject synthetic agent_spawn/agent_done events based on the main pane's
    # tool_use (Agent) and matching tool_result.
    spawn_events: list[dict] = []
    for ev in main_events:
        if ev["kind"] == "tool_use" and ev["data"].get("name") == "Agent":
            tool_id = ev["data"].get("id")
            agent_id = tool_to_agent.get(tool_id)
            if agent_id:
                pane = f"agent-{short_id(agent_id)}"
                meta = agents_meta.get(pane, {})
                spawn_events.append({
                    "ts": ev["ts"], "t_ms": ev["t_ms"] + 1, "pane": "system",
                    "kind": "agent_spawn",
                    "data": {
                        "agent_pane": pane,
                        "agent_id": agent_id,
                        "type": meta.get("type"),
                        "description": meta.get("description"),
                    },
                })
        elif ev["kind"] == "tool_result" and ev["data"].get("agent_id"):
            # the Agent-launch reply itself; nothing to do here
            pass

    # An agent_done is the LAST event on its pane.
    last_per_pane: dict[str, dict] = {}
    for ev in agent_events:
        last_per_pane[ev["pane"]] = ev
    done_events: list[dict] = []
    for pane, last in last_per_pane.items():
        done_events.append({
            "ts": last["ts"], "t_ms": last["t_ms"] + 2, "pane": "system",
            "kind": "agent_done",
            "data": {"agent_pane": pane, "agent_id": agents_meta[pane]["agent_id"]},
        })

    # Merge, sort by t_ms, re-base to t = ms-from-start
    all_events = main_events + agent_events + spawn_events + done_events
    all_events.sort(key=lambda e: e["t_ms"])
    if not all_events:
        print("no events collected")
        return 1
    t0 = all_events[0]["t_ms"]
    timeline = []
    for ev in all_events:
        timeline.append({
            "t": ev["t_ms"] - t0,
            "ts": ev["ts"],
            "pane": ev["pane"],
            "kind": ev["kind"],
            "data": ev["data"],
        })

    out = {
        "session_id": args.session.stem,
        "started_at": timeline[0]["ts"],
        "ended_at": timeline[-1]["ts"],
        "duration_ms": timeline[-1]["t"],
        "agents": agents_meta,
        "events": timeline,
    }
    args.out.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    print(
        f"[build] {len(timeline)} events · {len(agents_meta)} agents · "
        f"duration {timeline[-1]['t'] // 1000}s · "
        f"out={args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
