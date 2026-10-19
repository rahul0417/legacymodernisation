// stage-runner.js — runs ONE stage:
//   1. Compose the prompt (read shape stage spec + inputs from prior stages)
//   2. Spawn `claude -p ... --output-format stream-json` as a child process
//   3. Pipe its stdout to:
//        - a stage log file (the tmux current-agent pane is tailing this)
//        - a JSONL parser → emits stage:token bus events
//   4. Watchdog: kill child + switch to fallback if
//        - no tokens for N seconds
//        - any error
//        - max_turns exceeded
//   5. On clean exit, emit stage:settle then stage:complete

import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";

import { bus } from "./bus.js";
import { CaptionPlayer } from "./caption-player.js";
import { FallbackPlayer } from "./fallback-player.js";
import { respawnPane, sendKeys, setPaneTitle, PANES } from "./tmux.js";

export class StageRunner {
  constructor({ shape, stageId, runDir, audit }) {
    this.shape = shape;
    this.stage = shape.stage(stageId);
    this.stageId = stageId;
    this.runDir = runDir;
    this.audit = audit;
    this.child = null;
    this.captionPlayer = null;
    this.fallbackPlayer = null;
    this.watchdogTimer = null;
    this.toolUseCount = 0;
    this.tokenCount = 0;
    this.finished = false;
    this.fallbackUsed = false;
  }

  async run() {
    fs.mkdirSync(this.runDir, { recursive: true });
    const logFile = path.join(this.runDir, `agent-${this.stageId}.log`);
    // Empty the log so the tail starts fresh
    fs.writeFileSync(logFile, "");

    // ── Captions ──
    this.captionPlayer = new CaptionPlayer(this.stageId);
    const captionsPath = this.shape.resolve(this.stage.captions);
    if (captionsPath && fs.existsSync(captionsPath)) {
      this.captionPlayer.load(captionsPath);
      this.captionPlayer.start();
    }

    // ── tmux: point the current-agent pane at the new log ──
    setPaneTitle(PANES.agent, `AGENT · ${this.stage.name}`);
    respawnPane(PANES.agent, `tail -F '${logFile}'`);
    sendKeys(PANES.orchestrator,
      `printf '\\033[1;36m▸ ${this.stage.name}\\033[0m  \\033[2m(stage ${this.stageId})\\033[0m\\n'`);

    // ── stage:start + audit ──
    bus.publish("stage:start", {
      stage: this.stageId,
      name: this.stage.name,
      sub: this.stage.sub,
      model: this.stage.model,
      expected_duration_seconds: this.stage.expected_duration_seconds,
    });
    this.audit.append({
      event: "stage_start",
      stage: this.stageId,
      model: this.stage.model,
    });

    // ── Compose prompt ──
    const promptPath = this.shape.resolve(this.stage.prompt);
    if (!fs.existsSync(promptPath)) {
      return this._fail(`prompt not found: ${promptPath}`);
    }
    const prompt = fs.readFileSync(promptPath, "utf8");

    // ── Spawn claude -p ──
    // We use --output-format stream-json so each line is a JSON event we can
    // parse cleanly. The child's stderr is also captured for the log file.
    const args = [
      "-p",
      "--output-format", "stream-json",
      "--verbose",                            // include thinking/tool events
      "--max-turns", String(this.stage.max_turns || 25),
      prompt,                                 // positional: the prompt
    ];

    try {
      this.child = spawn("claude", args, {
        env: { ...process.env, FORCE_COLOR: "0" },
      });
    } catch (err) {
      return this._fail(`spawn claude failed: ${err.message}`);
    }

    this.child.on("error", (err) => {
      this._fallback(`spawn error: ${err.message}`);
    });

    this.child.stdout.setEncoding("utf8");
    this.child.stderr.setEncoding("utf8");

    let buffer = "";
    this.child.stdout.on("data", (chunk) => {
      this._kickWatchdog();
      buffer += chunk;
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) this._handleJsonLine(line, logFile);
    });
    this.child.stderr.on("data", (chunk) => {
      fs.appendFileSync(logFile, `[stderr] ${chunk}`);
    });

    this.child.on("exit", (code, signal) => {
      if (this.finished) return;
      if (code === 0) this._settle();
      else this._fallback(`claude exited code=${code} signal=${signal}`);
    });

    this._kickWatchdog();
  }

  _handleJsonLine(line, logFile) {
    const s = line.trim();
    if (!s) return;
    let evt;
    try { evt = JSON.parse(s); } catch { fs.appendFileSync(logFile, line + "\n"); return; }

    // Different claude SDK builds wrap differently. Cover the common shapes:
    //   { type: 'assistant', message: { content: [{type:'text', text:'…'}, ...] } }
    //   { type: 'tool_use', name: 'Read', input: {...} }
    //   { type: 'tool_result', tool_use_id: '…', content: [{type:'text', text:'…'}] }
    //   { type: 'system', subtype: 'init', ... }
    //   { type: 'result', subtype: 'success', total_cost_usd: 0.04, ... }
    this.tokenCount++;

    if (evt.type === "assistant") {
      const content = evt.message?.content || [];
      for (const part of content) {
        if (part.type === "text") {
          fs.appendFileSync(logFile, `${part.text}\n`);
          bus.publish("stage:token", {
            stage: this.stageId,
            kind: "text",
            text: part.text,
          });
        } else if (part.type === "thinking") {
          fs.appendFileSync(logFile, `[thinking] ${(part.thinking || "").slice(0, 200)}\n`);
          bus.publish("stage:token", {
            stage: this.stageId,
            kind: "thinking",
            text: (part.thinking || "").slice(0, 400),
          });
        } else if (part.type === "tool_use") {
          this.toolUseCount++;
          const argsBrief = JSON.stringify(part.input || {}).slice(0, 120);
          fs.appendFileSync(logFile, `⚒ ${part.name}(${argsBrief})\n`);
          bus.publish("stage:token", {
            stage: this.stageId,
            kind: "tool_use",
            tool: part.name,
            args_brief: argsBrief,
          });
        }
      }
    } else if (evt.type === "user") {
      const content = evt.message?.content || [];
      for (const part of content) {
        if (part.type === "tool_result") {
          const text = Array.isArray(part.content)
            ? part.content.map((p) => p.text || "").join(" ").slice(0, 200)
            : String(part.content || "").slice(0, 200);
          fs.appendFileSync(logFile, `↩ ${text}\n`);
          bus.publish("stage:token", {
            stage: this.stageId,
            kind: "tool_result",
            text,
            is_error: !!part.is_error,
          });
        }
      }
    } else if (evt.type === "result") {
      // claude SDK's final summary; not necessarily an error
      fs.appendFileSync(logFile, `\n[result] ${evt.subtype || "ok"} cost=$${evt.total_cost_usd || "?"}\n`);
    }

    // Watch for [CAPTION] markers in any text — promote to caption stream
    const allText = JSON.stringify(evt);
    const m = allText.match(/\[CAPTION\]\s*([^"\\]{4,200})/);
    if (m) {
      bus.publish("stage:caption", {
        stage: this.stageId,
        text: m[1].trim(),
        source: "agent",
      });
    }

    // Watchdog: max_turns guard
    if (this.toolUseCount >= (this.stage.max_turns || 25) + 2) {
      this._fallback(`max_turns exceeded: ${this.toolUseCount}`);
    }
  }

  _kickWatchdog() {
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer);
    if (this.finished) return;
    const triggers = this.shape.watchdog?.triggers || [];
    const noTokens = triggers.find((t) => t.no_tokens_for_seconds);
    const seconds = noTokens?.no_tokens_for_seconds || 8;
    this.watchdogTimer = setTimeout(() => {
      this._fallback(`no tokens for ${seconds}s`);
    }, seconds * 1000);
  }

  _settle() {
    if (this.finished) return;
    this.finished = true;
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer);
    if (this.captionPlayer) this.captionPlayer.settleNow();

    bus.publish("stage:settle", {
      stage: this.stageId,
      ok: true,
      tokens: this.tokenCount,
      tool_uses: this.toolUseCount,
    });
    this.audit.append({
      event: "stage_complete",
      stage: this.stageId,
      ok: true,
      tokens: this.tokenCount,
      tool_uses: this.toolUseCount,
      fallback_used: this.fallbackUsed,
    });
    bus.publish("stage:complete", {
      stage: this.stageId,
      ok: true,
      summary: `${this.tokenCount} events · ${this.toolUseCount} tool calls`,
      fallback_used: this.fallbackUsed,
    });
  }

  _fail(message) {
    if (this.finished) return;
    this.finished = true;
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer);
    bus.publish("stage:error", { stage: this.stageId, message });
    this.audit.append({ event: "stage_error", stage: this.stageId, message });
    // Fall through to fallback so the demo doesn't dead-end
    this._fallback(message);
  }

  _fallback(reason) {
    if (this.fallbackUsed) return;
    this.fallbackUsed = true;
    if (this.child && !this.child.killed) this.child.kill("SIGTERM");
    if (this.captionPlayer) this.captionPlayer.stop();
    bus.publish("stage:fallback", { stage: this.stageId, reason });
    this.audit.append({ event: "stage_fallback", stage: this.stageId, reason });

    const recDir = path.join(this.shape.baseDir, "recordings");
    this.fallbackPlayer = new FallbackPlayer(this.stageId, recDir);
    this.fallbackPlayer.start();
  }

  cancel() {
    if (this.finished) return;
    this.finished = true;
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer);
    if (this.child && !this.child.killed) this.child.kill("SIGTERM");
    if (this.captionPlayer) this.captionPlayer.stop();
    if (this.fallbackPlayer) this.fallbackPlayer.stop();
    bus.publish("stage:cancelled", { stage: this.stageId });
  }

  /**
   * Force the watchdog to trip immediately. Public-facing equivalent of an
   * 8-second timeout firing — used by the cockpit's "Simulate failure"
   * devtools button to verify silent fallback on demand.
   */
  simulateFailure(reason = "simulated by user") {
    if (this.finished) return false;
    this._fallback(reason);
    return true;
  }
}
