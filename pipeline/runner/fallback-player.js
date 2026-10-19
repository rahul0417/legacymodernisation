// fallback-player.js — when the watchdog trips on a live stage, replay the
// pre-recorded `.tokens.jsonl` event stream at original timings so the cockpit
// still sees a complete run. Phase 7 records these `.cast` + `.tokens.jsonl`
// pairs after a known-good live run.
//
// If the recording doesn't exist yet (which is the case until Phase 7
// finishes), this player emits a warning and synthesises a minimal "stage
// would have completed" sequence so the demo doesn't get stuck.

import fs from "node:fs";
import path from "node:path";
import { bus } from "./bus.js";

export class FallbackPlayer {
  constructor(stageId, recordingDir) {
    this.stageId = stageId;
    this.recordingDir = recordingDir;
    this.timers = [];
    this.aborted = false;
  }

  start() {
    const tokensPath = path.join(this.recordingDir, `${this.stageId}.tokens.jsonl`);
    if (!fs.existsSync(tokensPath)) {
      this._synthesise();
      return;
    }

    const lines = fs.readFileSync(tokensPath, "utf8")
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);

    let baseT = null;
    const startWall = Date.now();
    for (const line of lines) {
      let evt;
      try { evt = JSON.parse(line); } catch { continue; }
      if (baseT === null) baseT = evt.t || 0;
      const offsetMs = (evt.t || 0) - baseT;
      const handle = setTimeout(() => {
        if (this.aborted) return;
        // Re-publish each recorded event to the bus
        const { t, ...rest } = evt;
        bus.publish(rest.type || "stage:token", rest);
      }, offsetMs);
      this.timers.push(handle);
    }
    // Schedule a synthetic stage:complete after last event + 1s
    const lastOffset = lines.length ? (JSON.parse(lines[lines.length - 1]).t || 0) - (baseT || 0) : 0;
    this.timers.push(setTimeout(() => {
      if (!this.aborted) {
        bus.publish("stage:complete", {
          stage: this.stageId,
          ok: true,
          summary: "Replayed from recording.",
          fallback_used: true,
        });
      }
    }, lastOffset + 1000));
  }

  _synthesise() {
    // No recording on disk yet — Phase 7 will produce these. Emit a single
    // caption + a delayed complete so the demo doesn't hang.
    console.warn(`[fallback] no recording at ${this.recordingDir}/${this.stageId}.tokens.jsonl — synthesising completion`);
    bus.publish("stage:caption", {
      stage: this.stageId,
      text: "(Fallback recording not yet captured · continuing scripted captions only.)",
      source: "fallback-synth",
    });
    this.timers.push(setTimeout(() => {
      if (this.aborted) return;
      bus.publish("stage:complete", {
        stage: this.stageId,
        ok: true,
        summary: "Synthesised (no recording yet).",
        fallback_used: true,
      });
    }, 30_000)); // give scripted captions room to finish
  }

  stop() {
    this.aborted = true;
    for (const t of this.timers) clearTimeout(t);
    this.timers = [];
  }
}
