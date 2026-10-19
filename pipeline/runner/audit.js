// audit.js — append-only audit log + automatic broadcast to the bus.
//
// Every audit event is also emitted as a bus 'audit' event so the SSE clients
// + the tmux audit pane (which tails the file) see it in the same moment.

import fs from "node:fs";
import path from "node:path";
import { bus } from "./bus.js";

export class Audit {
  constructor(filePath) {
    this.filePath = filePath;
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    if (!fs.existsSync(filePath)) {
      fs.writeFileSync(filePath, "");
    }
  }

  /** Append one structured event. */
  append(event) {
    const enriched = { ts: new Date().toISOString(), ...event };
    fs.appendFileSync(this.filePath, JSON.stringify(enriched) + "\n");
    bus.publish("audit", enriched);
    return enriched;
  }

  /** Wipe the file (used on /reset). */
  truncate() {
    fs.writeFileSync(this.filePath, "");
  }
}
