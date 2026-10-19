// bus.js — single global EventEmitter that the rest of the runner uses to
// move events between modules and out to the cockpit (via SSE).
//
// Event taxonomy (every event has a `type` field):
//
//   state:ready            — server up; cockpit can subscribe
//   state:reset            — current run wiped; cockpit clears panes
//   stage:start            — { id, name, sub }
//   stage:caption          — { id, text, at_ms }     (from caption-player or live agent)
//   stage:token            — { id, kind, text }      (kind: text|thinking|tool_use|tool_result)
//   stage:settle           — { id, ok, summary }     (claude -p exited cleanly)
//   stage:fallback         — { id, reason }          (watchdog tripped; fallback player kicks in)
//   stage:complete         — { id, ok, summary, fallback_used }
//   stage:error            — { id, message }
//   audit                  — { ts, event, ... }       (also appended to audit.jsonl)

import { EventEmitter } from "node:events";

class Bus extends EventEmitter {
  constructor() {
    super();
    this.setMaxListeners(50); // SSE clients + internal listeners; small upper bound
  }

  /** Emit a typed event. */
  publish(type, payload = {}) {
    const evt = { type, ts: new Date().toISOString(), ...payload };
    this.emit("*", evt);
    this.emit(type, evt);
    return evt;
  }
}

export const bus = new Bus();
