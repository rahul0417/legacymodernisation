// tmux.js — minimal wrapper around the tmux CLI.
//
// The runner uses it to:
//   - respawn the "current agent" pane to tail a stage log file
//   - push status text into the orchestrator pane
// All operations are best-effort; if tmux is unavailable the runner still
// works (you just lose the visible terminal panes).

import { execSync } from "node:child_process";

let tmuxAvailable = null;

export function hasTmux() {
  if (tmuxAvailable !== null) return tmuxAvailable;
  try {
    execSync("tmux -V", { stdio: "ignore" });
    tmuxAvailable = true;
  } catch {
    tmuxAvailable = false;
  }
  return tmuxAvailable;
}

const SESSION = process.env.PNS_SESSION || "pns-demo";

function run(args) {
  if (!hasTmux()) return false;
  try {
    execSync(`tmux ${args}`, { stdio: "ignore" });
    return true;
  } catch (err) {
    return false;
  }
}

/** Send-keys + Enter into a target pane. */
export function sendKeys(target, command) {
  // Escape single quotes for shell embedding
  const escaped = command.replace(/'/g, `'\\''`);
  return run(`send-keys -t ${SESSION}:${target} '${escaped}' Enter`);
}

/** Respawn a pane with a fresh command (kills any current process in it). */
export function respawnPane(target, command) {
  // The -k flag kills the existing pane process
  const escaped = command.replace(/'/g, `'\\''`);
  return run(`respawn-pane -k -t ${SESSION}:${target} '${escaped}'`);
}

/** Set the pane border title (used to label which agent is running). */
export function setPaneTitle(target, title) {
  const escaped = title.replace(/'/g, `'\\''`);
  return run(`select-pane -t ${SESSION}:${target} -T '${escaped}'`);
}

/** Clear a pane (sends C-l). Used between stages. */
export function clearPane(target) {
  return run(`send-keys -t ${SESSION}:${target} C-l`);
}

/** Pane indices the launcher set up. */
export const PANES = {
  orchestrator: "main.0",
  agent:        "main.1",
  audit:        "main.2",
  fileDiff:     "main.3",
};
