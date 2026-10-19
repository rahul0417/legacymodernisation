// caption-player.js — replays a pre-scripted captions/<stage>.json file
// alongside whatever the live agent is doing.
//
// One instance per running stage. Calling stop() cancels pending timers.

import fs from "node:fs";
import { bus } from "./bus.js";

export class CaptionPlayer {
  constructor(stageId) {
    this.stageId = stageId;
    this.timers = [];
    this.startedAt = null;
    this.paused = false;
    this.captions = [];
    this.settle = null;
  }

  load(captionsPath) {
    const raw = JSON.parse(fs.readFileSync(captionsPath, "utf8"));
    this.captions = raw.captions || [];
    this.settle = raw.settle_caption || null;
  }

  start() {
    this.startedAt = Date.now();
    for (const c of this.captions) {
      const t = setTimeout(() => {
        if (this.paused) {
          // re-enqueue: schedule immediately when unpaused
          return;
        }
        bus.publish("stage:caption", {
          stage: this.stageId,
          text: c.text,
          at_ms: c.at_ms,
          source: "scripted",
        });
      }, c.at_ms);
      this.timers.push(t);
    }
  }

  /** Emit the final settle caption. Call from stage-runner on success. */
  settleNow() {
    if (this.settle) {
      bus.publish("stage:caption", {
        stage: this.stageId,
        text: this.settle,
        at_ms: -1,
        source: "settle",
      });
    }
  }

  stop() {
    for (const t of this.timers) clearTimeout(t);
    this.timers = [];
  }

  pause() {
    this.paused = true;
  }

  resume() {
    this.paused = false;
  }
}
