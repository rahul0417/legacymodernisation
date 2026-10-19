// server.js — HTTP + SSE server for the live-demo cockpit.
//
// Endpoints:
//   GET  /events            — SSE stream of every bus event
//   GET  /shape             — current shape definition (stages, locks, celebration)
//   GET  /state             — current run state (which stage active, etc.)
//   POST /stage/:id         — trigger one stage
//   POST /stage/all         — Run All button: walks 1→2→3 with gate pauses
//   POST /reset             — wipe current run
//   GET  /healthz           — liveness
//   GET  /*                 — static file serving (cockpit assets)
//
// Run:  node server.js
// Env:  PORT=8721 SHAPE=crud PIPELINE_DIR=/abs/path/to/pipeline

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { bus } from "./bus.js";
import { loadShape } from "./shape-loader.js";
import { Audit } from "./audit.js";
import { StageRunner } from "./stage-runner.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);

// ── Config ───────────────────────────────────────────────────────────────────

const PORT         = parseInt(process.env.PORT || "8721", 10);
const PIPELINE_DIR = process.env.PIPELINE_DIR || path.resolve(__dirname, "..");
const SHAPE_ID     = process.env.SHAPE || "crud";
const COCKPIT_DIR  = path.join(PIPELINE_DIR, "cockpit");
const SHAPES_DIR   = path.join(PIPELINE_DIR, "shapes");
const RUNS_DIR     = path.join(PIPELINE_DIR, "runs");

const shape = loadShape(SHAPES_DIR, SHAPE_ID);

// ── Run state ────────────────────────────────────────────────────────────────

function makeRunId() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

const state = {
  runId: null,
  runDir: null,
  audit: null,
  currentStage: null,
  currentRunner: null,
  history: [],   // [{ stageId, ok, fallback_used, ts }]
};

function startNewRun() {
  state.runId = makeRunId();
  state.runDir = path.join(RUNS_DIR, state.runId);
  state.audit = new Audit(path.join(state.runDir, "audit.jsonl"));
  state.currentStage = null;
  state.currentRunner = null;
  state.history = [];

  // Maintain a 'current' symlink for the tmux pane tailers
  const link = path.join(RUNS_DIR, "current");
  try { fs.unlinkSync(link); } catch {}
  try { fs.symlinkSync(state.runDir, link); } catch {}

  state.audit.append({
    event: "engagement_created",
    shape: shape.id,
    run_id: state.runId,
    source_dir: shape.stages[0]?.inputs?.source_dir,
  });
  bus.publish("state:ready", { runId: state.runId });
}

function reset() {
  if (state.currentRunner) state.currentRunner.cancel();
  startNewRun();
  bus.publish("state:reset", { runId: state.runId });
}

// ── SSE clients ──────────────────────────────────────────────────────────────

const sseClients = new Set();

function sseSend(res, evt) {
  try {
    res.write(`data: ${JSON.stringify(evt)}\n\n`);
  } catch {
    sseClients.delete(res);
  }
}

bus.on("*", (evt) => {
  for (const res of sseClients) sseSend(res, evt);
});

// ── Recording mode (Phase 7 capture support) ─────────────────────────────────
//
// When PNS_RECORD=1, every event the runner publishes also gets appended to
// runs/<runId>/recordings/<stageId>.tokens.jsonl with a t-offset (ms from
// stage:start). Promoting these into shapes/<id>/recordings/ makes them
// available to the watchdog's fallback player on any future run.

const RECORD = process.env.PNS_RECORD === "1" || process.env.PNS_RECORD === "true";
const stageRecordingState = { stageId: null, startedAt: 0, fd: null };

function rotateRecording(stageId) {
  closeRecording();
  if (!RECORD) return;
  const dir = path.join(state.runDir, "recordings");
  fs.mkdirSync(dir, { recursive: true });
  const fpath = path.join(dir, `${stageId}.tokens.jsonl`);
  stageRecordingState.fd = fs.openSync(fpath, "w");
  stageRecordingState.stageId = stageId;
  stageRecordingState.startedAt = Date.now();
}

function closeRecording() {
  if (stageRecordingState.fd !== null) {
    try { fs.closeSync(stageRecordingState.fd); } catch {}
  }
  stageRecordingState.fd = null;
  stageRecordingState.stageId = null;
  stageRecordingState.startedAt = 0;
}

if (RECORD) {
  console.log("[runner] recording mode ON — events will be saved under runs/<id>/recordings/");
  bus.on("stage:start", (evt) => rotateRecording(evt.stage));
  bus.on("stage:complete", () => closeRecording());
  bus.on("stage:error", () => closeRecording());
  bus.on("*", (evt) => {
    if (stageRecordingState.fd === null) return;
    // skip the audit events that are noise during replay
    if (evt.type === "audit") return;
    const offset = Date.now() - stageRecordingState.startedAt;
    const payload = { t: offset, ...evt };
    try {
      fs.writeSync(stageRecordingState.fd, JSON.stringify(payload) + "\n");
    } catch (err) {
      console.error("[runner] failed to write recording line:", err.message);
    }
  });
}

// ── HTTP routing ─────────────────────────────────────────────────────────────

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js":   "application/javascript; charset=utf-8",
  ".css":  "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png":  "image/png",
  ".svg":  "image/svg+xml",
};

function send(res, status, body, headers = {}) {
  res.writeHead(status, { "Content-Type": "application/json", ...headers });
  res.end(typeof body === "string" ? body : JSON.stringify(body));
}

function notFound(res) { send(res, 404, { error: "not found" }); }

async function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end",  () => {
      const raw = Buffer.concat(chunks).toString();
      if (!raw) return resolve({});
      try { resolve(JSON.parse(raw)); } catch { resolve({}); }
    });
    req.on("error", reject);
  });
}

function serveStatic(res, urlPath) {
  let rel = urlPath === "/" ? "/index.html" : urlPath;
  if (rel.includes("..")) return notFound(res);

  // /runs/* maps to the runs directory so devtools can open audit.jsonl
  // and the celebration screen can <img> the mosaic.
  let rootDir = COCKPIT_DIR;
  if (rel.startsWith("/runs/")) {
    rootDir = RUNS_DIR;
    rel = rel.slice("/runs".length); // strip the prefix; keep the leading "/"
  }

  const filePath = path.join(rootDir, rel);
  fs.stat(filePath, (err, stat) => {
    if (err || !stat.isFile()) return notFound(res);
    const ext = path.extname(filePath).toLowerCase();
    const mime = MIME[ext] || "application/octet-stream";
    res.writeHead(200, { "Content-Type": mime });
    fs.createReadStream(filePath).pipe(res);
  });
}

async function handleRunStage(stageId, res) {
  if (state.currentRunner && !state.currentRunner.finished) {
    return send(res, 409, { error: `stage ${state.currentStage} already running` });
  }
  try {
    state.currentStage = stageId;
    const runner = new StageRunner({
      shape,
      stageId,
      runDir: state.runDir,
      audit:  state.audit,
    });
    state.currentRunner = runner;
    runner.run();
    send(res, 202, { ok: true, stage: stageId, runId: state.runId });
  } catch (err) {
    send(res, 500, { error: err.message });
  }
}

async function handleRunAll(res) {
  // Walk stages with gate pauses. Each stage waits for complete before next.
  send(res, 202, { ok: true, mode: "run_all", runId: state.runId });
  for (const s of shape.stages) {
    await runStageAndAwait(s.id);
    if (s.gate?.continue_button && s.gate?.pause_seconds > 0) {
      await new Promise((r) => setTimeout(r, s.gate.pause_seconds * 1000));
    }
  }
  bus.publish("run:complete", { runId: state.runId });
}

function runStageAndAwait(stageId) {
  return new Promise((resolve) => {
    handleRunStage(stageId, { writeHead() {}, end() {} }); // fire-and-forget stub res
    const done = (evt) => {
      if (evt.stage === stageId) {
        bus.off("stage:complete", done);
        resolve(evt);
      }
    };
    bus.on("stage:complete", done);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const p = url.pathname;

  // CORS for local cockpit dev
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.end();

  if (req.method === "GET" && p === "/healthz") {
    return send(res, 200, { ok: true, shape: shape.id, runId: state.runId });
  }

  if (req.method === "GET" && p === "/shape") {
    return send(res, 200, {
      id: shape.id,
      display_name: shape.displayName,
      stages: shape.stages.map((s) => ({
        id: s.id, name: s.name, sub: s.sub,
        expected_duration_seconds: s.expected_duration_seconds,
        gate: s.gate,
      })),
      locks: shape.locks,
      celebration: shape.celebration,
    });
  }

  if (req.method === "GET" && p === "/state") {
    return send(res, 200, {
      runId:        state.runId,
      currentStage: state.currentStage,
      history:      state.history,
      running:      !!(state.currentRunner && !state.currentRunner.finished),
    });
  }

  if (req.method === "POST" && p === "/reset") {
    reset();
    return send(res, 200, { ok: true, runId: state.runId });
  }

  if (req.method === "POST" && p === "/simulate/fallback") {
    if (!state.currentRunner || state.currentRunner.finished) {
      return send(res, 400, { error: "no stage currently running" });
    }
    const ok = state.currentRunner.simulateFailure("simulated via POST /simulate/fallback");
    return send(res, 200, { ok, stage: state.currentStage });
  }

  const stageMatch = p.match(/^\/stage\/(.+)$/);
  if (req.method === "POST" && stageMatch) {
    const id = decodeURIComponent(stageMatch[1]);
    if (id === "all") return handleRunAll(res);
    if (!shape.stages.find((s) => s.id === id)) {
      return send(res, 400, { error: `unknown stage: ${id}` });
    }
    return handleRunStage(id, res);
  }

  if (req.method === "GET" && p === "/events") {
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "Connection":  "keep-alive",
      "X-Accel-Buffering": "no",
    });
    res.write(`: ready\n\n`);
    sseClients.add(res);
    // Replay-on-connect: any persisted current state can be summarised here
    sseSend(res, { type: "hello", runId: state.runId, shape: shape.id });
    req.on("close", () => sseClients.delete(res));
    return;
  }

  if (req.method === "GET") return serveStatic(res, p);

  return notFound(res);
});

// Track stage completions in history
bus.on("stage:complete", (evt) => {
  state.history.push({
    stageId: evt.stage,
    ok: evt.ok,
    fallback_used: !!evt.fallback_used,
    ts: evt.ts,
  });
});

// ── Bootstrap ────────────────────────────────────────────────────────────────

startNewRun();

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[runner] shape=${shape.id}  port=${PORT}  pipeline=${PIPELINE_DIR}`);
  console.log(`[runner] cockpit: http://127.0.0.1:${PORT}/`);
  console.log(`[runner] events:  http://127.0.0.1:${PORT}/events`);
  console.log(`[runner] runId:   ${state.runId}`);
});
