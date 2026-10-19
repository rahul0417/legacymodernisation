/* Session replay player.
 * Loads timeline.json and walks events in chronological order, rendering
 * each into its pane. Agent panes appear on agent_spawn, mark done on
 * agent_done. Skip-idle compresses gaps > 10s of real time to ~500ms.
 */

(function () {
  const $ = (id) => document.getElementById(id);
  const grid = $("grid");
  const strip = $("agents-strip");
  const paneMain = $("pane-main");
  const btnPlay = $("btn-play");
  const btnReset = $("btn-reset");
  const speedSel = $("speed");
  const skipIdleCb = $("skip-idle");
  const scrub = $("scrub");
  const scrubTicks = $("scrub-ticks");
  const timeNow = $("time-now");
  const timeTotal = $("time-total");
  const hudSession = $("hud-session");
  const statEvents = $("stat-events");
  const statAgents = $("stat-agents");
  const statPaneInfo = $("stat-pane-info");
  const mainMeta = $("main-meta");

  let timeline = null;
  let panes = { main: paneMain };
  let agentsMeta = {};
  let renderedCount = 0;
  let nextIdx = 0;
  let virtualMs = 0;             // ms of compressed time played so far
  let realMsConsumed = 0;        // ms of real session time already past
  let playing = false;
  let rafHandle = null;
  let lastRaf = 0;
  let totalRealMs = 0;
  const IDLE_GAP_MS = 10_000;    // skip-idle threshold
  const IDLE_COMPRESS_MS = 500;  // compress idle gaps to this

  // ─── Helpers ────────────────────────────────────────────────
  function fmtTime(ms) {
    if (!ms || ms < 0) ms = 0;
    const s = Math.floor(ms / 1000);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(sec).padStart(2,"0")}`;
  }

  function el(tag, cls, html) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html !== undefined) n.innerHTML = html;
    return n;
  }

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function shortenToolArgs(input) {
    if (!input || typeof input !== "object") return "";
    const order = ["file_path","path","command","query","subject","description","prompt","name","old_string","new_string","content"];
    const parts = [];
    for (const k of order) {
      if (input[k] !== undefined && k !== "_name") {
        let v = String(input[k]);
        if (v.length > 80) v = v.slice(0, 80) + "…";
        parts.push(`${k}=${v.replace(/\n/g, " ")}`);
        if (parts.length >= 2) break;
      }
    }
    if (parts.length === 0) {
      for (const k of Object.keys(input)) {
        if (k === "_name") continue;
        let v = JSON.stringify(input[k]);
        if (v.length > 80) v = v.slice(0, 80) + "…";
        parts.push(`${k}=${v}`);
        if (parts.length >= 2) break;
      }
    }
    return parts.join("  ");
  }

  function renderEvent(ev) {
    const body = panes[ev.pane] || panes.main;
    let row;
    switch (ev.kind) {
      case "user":
        row = el("div", "evt user",
          `<span class="tag">USER</span>${escapeHtml(ev.data.text || "")}`);
        break;
      case "text":
        row = el("div", "evt text",
          `<span class="tag">${ev.pane === "main" ? "CLAUDE" : ev.pane.toUpperCase()}</span>${escapeHtml(ev.data.text || "")}`);
        break;
      case "thinking":
        row = el("div", "evt thinking");
        row.innerHTML = `<span class="tag">THINK</span><details><summary>${escapeHtml((ev.data.text || "").slice(0, 80))}…</summary><pre style="white-space:pre-wrap;margin:4px 0;">${escapeHtml(ev.data.text || "")}</pre></details>`;
        break;
      case "tool_use":
        row = el("div", "evt tool_use",
          `<span class="tag">⚒ ${escapeHtml(ev.data.name)}</span><span class="args">${escapeHtml(shortenToolArgs(ev.data.input))}</span>`);
        break;
      case "tool_result": {
        const cls = ev.data.is_error ? "evt tool_result error" : "evt tool_result";
        const t = (ev.data.text || "").slice(0, 200);
        const more = (ev.data.text || "").length > 200;
        row = el("div", cls);
        row.innerHTML = `<span class="tag">${ev.data.is_error ? "✗ ERROR" : "↩ OK"}</span>${escapeHtml(t)}${more ? "…" : ""}`;
        break;
      }
      case "agent_spawn":
        row = el("div", "evt agent_spawn",
          `<span class="tag">✦ SPAWN</span>${escapeHtml(ev.data.description || ev.data.agent_pane)} <span class="args">(${escapeHtml(ev.data.type)})</span>`);
        ensureAgentPane(ev.data.agent_pane, ev.data);
        break;
      case "agent_done":
        row = el("div", "evt agent_done",
          `<span class="tag">✓ DONE</span>${escapeHtml(ev.data.agent_pane)}`);
        markAgentDone(ev.data.agent_pane);
        break;
    }
    if (!row) return;

    // system events render in main pane (spawn/done) for visibility
    const target = (ev.pane === "system") ? panes.main : body;
    target.appendChild(row);
    // keep newest in view
    target.scrollTop = target.scrollHeight;
  }

  function ensureAgentPane(paneId, meta) {
    if (panes[paneId]) return;
    const pane = el("div", "pane spawned");
    pane.dataset.pane = paneId;
    pane.innerHTML = `
      <div class="pane-head">
        <span class="pane-icon">●</span>
        <span class="pane-title">${escapeHtml(paneId)}</span>
        <span class="pane-meta">${escapeHtml(meta.type || "")} · ${escapeHtml((meta.description || "").slice(0, 60))}</span>
      </div>
      <div class="pane-body"></div>
    `;
    strip.appendChild(pane);
    panes[paneId] = pane.querySelector(".pane-body");
    updatePaneInfo();
  }

  function markAgentDone(paneId) {
    const node = strip.querySelector(`[data-pane="${paneId}"]`);
    if (node) node.classList.add("done");
  }

  function updateHUDStats() {
    statEvents.textContent = renderedCount;
    statAgents.textContent = Object.keys(panes).length - 1; // minus main
    statPaneInfo.textContent = `main: ${panes.main.children.length}`;
  }
  function updatePaneInfo() {
    statPaneInfo.textContent = `main: ${panes.main.children.length} · agents open: ${Object.keys(panes).length - 1}`;
  }

  // ─── Player loop ─────────────────────────────────────────────
  function step(dtMs) {
    if (!timeline) return;
    const speed = speedSel.value === "instant" ? Infinity : parseFloat(speedSel.value);
    const skipIdle = skipIdleCb.checked;

    if (speed === Infinity) {
      // drain all
      while (nextIdx < timeline.events.length) {
        renderEvent(timeline.events[nextIdx]);
        renderedCount++;
        nextIdx++;
      }
      virtualMs = totalRealMs;
      updateScrub();
      updateHUDStats();
      pause();
      return;
    }

    // advance virtual clock by dtMs * speed
    let toAdvance = dtMs * speed;
    while (toAdvance > 0 && nextIdx < timeline.events.length) {
      const nextEv = timeline.events[nextIdx];
      const realGapMs = nextEv.t - realMsConsumed;
      let virtualGapMs;
      if (skipIdle && realGapMs > IDLE_GAP_MS) {
        virtualGapMs = IDLE_COMPRESS_MS;
      } else {
        virtualGapMs = realGapMs / speed;
      }
      if (virtualGapMs > toAdvance) {
        virtualMs += toAdvance;
        // map back to real ms for display sync
        realMsConsumed += skipIdle && realGapMs > IDLE_GAP_MS
          ? (toAdvance / IDLE_COMPRESS_MS) * realGapMs
          : toAdvance * speed;
        toAdvance = 0;
      } else {
        virtualMs += virtualGapMs;
        realMsConsumed = nextEv.t;
        toAdvance -= virtualGapMs;
        renderEvent(nextEv);
        renderedCount++;
        nextIdx++;
      }
    }
    if (nextIdx >= timeline.events.length) {
      pause();
    }
    updateScrub();
    updateHUDStats();
  }

  function updateScrub() {
    if (totalRealMs === 0) return;
    const p = Math.min(1000, Math.round((realMsConsumed / totalRealMs) * 1000));
    scrub.value = p;
    scrub.style.setProperty("--p", `${p / 10}%`);
    timeNow.textContent = fmtTime(realMsConsumed);
  }

  function rafTick(ts) {
    if (!playing) return;
    if (!lastRaf) lastRaf = ts;
    const dt = ts - lastRaf;
    lastRaf = ts;
    step(dt);
    rafHandle = requestAnimationFrame(rafTick);
  }

  function play() {
    if (!timeline || playing) return;
    playing = true;
    btnPlay.textContent = "❚❚ Pause";
    lastRaf = 0;
    rafHandle = requestAnimationFrame(rafTick);
  }
  function pause() {
    playing = false;
    btnPlay.textContent = "▶ Play";
    if (rafHandle) cancelAnimationFrame(rafHandle);
  }
  function reset() {
    pause();
    nextIdx = 0;
    renderedCount = 0;
    virtualMs = 0;
    realMsConsumed = 0;
    paneMain.innerHTML = "";
    strip.innerHTML = "";
    panes = { main: paneMain };
    updateScrub();
    updateHUDStats();
  }
  function jumpTo(percent) {
    // jump to percent of real ms in timeline; instant-fill events up to that point
    pause();
    reset();
    const target = (percent / 1000) * totalRealMs;
    while (nextIdx < timeline.events.length && timeline.events[nextIdx].t <= target) {
      renderEvent(timeline.events[nextIdx]);
      renderedCount++;
      nextIdx++;
    }
    realMsConsumed = target;
    updateScrub();
    updateHUDStats();
  }

  // ─── Scrub ticks (one per agent_spawn) ───────────────────────
  function drawScrubTicks() {
    scrubTicks.innerHTML = "";
    timeline.events.forEach((ev) => {
      if (ev.kind !== "agent_spawn") return;
      const tick = el("span", "", "✦");
      tick.style.left = `${(ev.t / totalRealMs) * 100}%`;
      tick.title = ev.data.description || ev.data.agent_pane;
      scrubTicks.appendChild(tick);
    });
  }

  // ─── Boot ────────────────────────────────────────────────────
  fetch("./timeline.json")
    .then((r) => r.json())
    .then((tl) => {
      timeline = tl;
      agentsMeta = tl.agents || {};
      totalRealMs = tl.duration_ms || 0;
      hudSession.textContent = `${tl.session_id.slice(0, 8)} · ${tl.started_at.slice(0, 19).replace("T", " ")} UTC`;
      timeTotal.textContent = fmtTime(totalRealMs);
      mainMeta.textContent = `${tl.events.length} events · ${Object.keys(agentsMeta).length} agents · ${Math.round(totalRealMs / 60000)} min`;
      drawScrubTicks();
      updateScrub();
      updateHUDStats();
    })
    .catch((err) => {
      paneMain.innerHTML = `<div class="evt error">failed to load timeline.json: ${escapeHtml(String(err))}</div>`;
    });

  btnPlay.addEventListener("click", () => (playing ? pause() : play()));
  btnReset.addEventListener("click", reset);
  scrub.addEventListener("input", (e) => jumpTo(Number(e.target.value)));
  document.addEventListener("keydown", (e) => {
    if (e.code === "Space") { e.preventDefault(); playing ? pause() : play(); }
    if (e.code === "KeyR")  { reset(); }
  });
})();
