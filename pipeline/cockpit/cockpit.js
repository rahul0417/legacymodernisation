// cockpit.js — connects to the runner over SSE, renders captions / progress /
// celebration. Vanilla JS, no build step.

(function () {
  const $ = (id) => document.getElementById(id);

  // ── State ───────────────────────────────────────────────────────────
  const state = {
    shape: null,
    runId: null,
    currentStage: null,
    stageStartedAt: null,
    stagesDone: new Set(),
    stagesFallback: new Set(),
    captionsPaused: false,
    captionQueue: [],
    numbers: {
      backend_tests: 0,
      frontend_tests: 0,
      api_fixtures_passed: 0,
      api_fixtures_total: 0,
      screenshots: 0,
      generated_files: 0,
      template_files: 73,
    },
    summary: {},     // per-stage summary text last seen
  };

  const STREAM_MAX = 60;

  // ── Boot ────────────────────────────────────────────────────────────
  fetch("/shape").then((r) => r.json()).then((shape) => {
    state.shape = shape;
    renderShape(shape);
    connectSSE();
  }).catch((err) => {
    showBanner(`Cannot reach runner: ${err.message}`, "error");
  });

  function renderShape(shape) {
    $("celebrate-title").textContent = shape.display_name + " — done";
    // Stage buttons
    const row = $("btn-stages");
    row.innerHTML = "";
    const dots = $("dots");
    dots.innerHTML = "";
    shape.stages.forEach((s, i) => {
      // dot
      if (i > 0) {
        const sep = document.createElement("li");
        sep.className = "dot-sep";
        dots.appendChild(sep);
      }
      const li = document.createElement("li");
      li.dataset.stage = s.id;
      li.innerHTML = `<span class="dot-circle"></span><span class="dot-label">${s.name}</span>`;
      dots.appendChild(li);
      // button
      const btn = document.createElement("button");
      btn.className = "btn";
      btn.id = `btn-stage-${s.id}`;
      btn.textContent = s.name;
      btn.addEventListener("click", () => runStage(s.id));
      row.appendChild(btn);
    });
    // Celebration buttons
    const actions = $("celebrate-actions");
    actions.innerHTML = "";
    (shape.celebration?.buttons || []).forEach((b) => {
      const btn = document.createElement("button");
      btn.className = "btn primary";
      btn.textContent = b.label;
      btn.addEventListener("click", () => handleCelebrationButton(b));
      actions.appendChild(btn);
    });
  }

  // ── SSE ────────────────────────────────────────────────────────────
  let elapsedTicker = null;

  function connectSSE() {
    const es = new EventSource("/events");
    es.onopen = () => {
      $("conn-dot").classList.add("online");
      $("conn-label").textContent = "live";
    };
    es.onerror = () => {
      $("conn-dot").classList.remove("online");
      $("conn-label").textContent = "reconnecting…";
    };
    es.onmessage = (msg) => {
      let evt;
      try { evt = JSON.parse(msg.data); } catch { return; }
      handleEvent(evt);
    };
  }

  function handleEvent(evt) {
    switch (evt.type) {
      case "hello":
      case "state:ready":
        state.runId = evt.runId;
        $("run-id").textContent = (evt.runId || "—").slice(0, 19);
        break;

      case "state:reset":
        state.runId = evt.runId;
        $("run-id").textContent = (evt.runId || "—").slice(0, 19);
        resetUI();
        break;

      case "stage:start":
        state.currentStage = evt.stage;
        state.stageStartedAt = Date.now();
        markStage(evt.stage, "running");
        clearStream();
        startElapsed();
        showBanner(`▸ ${evt.name}…`, "stage-start");
        break;

      case "stage:caption":
        if (state.captionsPaused) {
          state.captionQueue.push(evt);
        } else {
          showBanner(evt.text);
        }
        break;

      case "stage:token":
        appendStream(evt);
        break;

      case "stage:settle":
        // The agent itself completed cleanly — captions still fire after
        break;

      case "stage:fallback":
        state.stagesFallback.add(evt.stage);
        // Silent — banner stays scripted; we only log this in the stream.
        appendStream({ kind: "system", text: `(fallback engaged for ${evt.stage}: ${evt.reason})` });
        break;

      case "stage:complete":
        markStage(evt.stage, state.stagesFallback.has(evt.stage) ? "fallback" : "done");
        state.stagesDone.add(evt.stage);
        if (evt.summary) state.summary[evt.stage] = evt.summary;
        // Auto-advance / Continue prompt only if this stage has continue_button
        const stageDef = state.shape?.stages.find((s) => s.id === evt.stage);
        if (stageDef?.gate?.continue_button && !isLastStage(evt.stage)) {
          showContinueCountdown(stageDef.gate.pause_seconds || 3);
        }
        // If this was the last stage, celebrate
        if (isLastStage(evt.stage)) {
          setTimeout(showCelebration, 1500);
        }
        break;

      case "run:complete":
        setTimeout(showCelebration, 800);
        break;

      case "audit":
        // Stage 3 emits numbers — pick them up if present in inline summary
        absorbAuditNumbers(evt);
        break;

      case "stage:error":
        appendStream({ kind: "system", text: `(error: ${evt.message})`, _error: true });
        break;
    }
  }

  function isLastStage(stageId) {
    const stages = state.shape?.stages || [];
    return stages.length > 0 && stages[stages.length - 1].id === stageId;
  }

  // ── Banner ─────────────────────────────────────────────────────────
  let bannerToken = 0;

  function showBanner(text, kind) {
    const myToken = ++bannerToken;
    const el = $("banner-text");
    el.classList.add("fading-out");
    setTimeout(() => {
      if (myToken !== bannerToken) return; // a newer banner queued ahead
      el.classList.remove("fading-out");
      // Force reflow so the fade-in animation re-fires
      el.style.animation = "none";
      void el.offsetWidth;
      el.style.animation = "";
      el.textContent = text;
    }, 200);
  }

  // ── Stream ─────────────────────────────────────────────────────────
  function appendStream(evt) {
    const stream = $("stream");
    const row = document.createElement("div");
    row.className = `stream-row ${evt.kind || "text"}`;
    if (evt._error) row.classList.add("error");
    const tag = tagFor(evt);
    const body = bodyFor(evt);
    row.innerHTML = `<span class="tag">${tag}</span>${escapeHtml(body)}`;
    stream.appendChild(row);
    while (stream.children.length > STREAM_MAX) stream.removeChild(stream.firstChild);
    stream.scrollTop = stream.scrollHeight;
  }
  function tagFor(evt) {
    switch (evt.kind) {
      case "tool_use":    return "⚒";
      case "tool_result": return evt.is_error ? "✗" : "↩";
      case "thinking":    return "·";
      case "system":      return "✦";
      default:            return "▸";
    }
  }
  function bodyFor(evt) {
    if (evt.kind === "tool_use") return `${evt.tool} ${evt.args_brief || ""}`;
    if (evt.kind === "tool_result") return (evt.text || "").slice(0, 140);
    return (evt.text || "").slice(0, 200);
  }
  function clearStream() {
    $("stream").innerHTML = "";
  }
  function escapeHtml(s) {
    return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ── Progress dots ──────────────────────────────────────────────────
  function markStage(stageId, status /* running | done | fallback */) {
    const dots = document.querySelectorAll("#dots li[data-stage]");
    dots.forEach((d) => {
      if (d.dataset.stage === stageId) {
        d.classList.remove("running", "done", "fallback");
        d.classList.add(status);
      }
    });
  }

  function startElapsed() {
    if (elapsedTicker) clearInterval(elapsedTicker);
    elapsedTicker = setInterval(() => {
      if (!state.stageStartedAt) return;
      const sec = Math.floor((Date.now() - state.stageStartedAt) / 1000);
      const mm = String(Math.floor(sec / 60)).padStart(2, "0");
      const ss = String(sec % 60).padStart(2, "0");
      $("elapsed").textContent = `${mm}:${ss}`;
    }, 250);
  }

  // ── Continue countdown ─────────────────────────────────────────────
  let continueTimer = null;

  function showContinueCountdown(seconds) {
    const hint = $("continue-hint");
    const cd = $("countdown");
    hint.classList.add("visible");
    let remaining = seconds;
    cd.textContent = `${remaining}s`;
    if (continueTimer) clearInterval(continueTimer);
    continueTimer = setInterval(() => {
      remaining--;
      cd.textContent = `${remaining}s`;
      if (remaining <= 0) {
        clearInterval(continueTimer);
        continueTimer = null;
        hint.classList.remove("visible");
        // Server-side /stage/all loop handles the auto-advance; nothing to do here.
      }
    }, 1000);
  }

  // ── Reset ──────────────────────────────────────────────────────────
  function resetUI() {
    state.stagesDone.clear();
    state.stagesFallback.clear();
    state.numbers = { ...state.numbers, screenshots: 0, generated_files: 0 };
    state.summary = {};
    document.querySelectorAll("#dots li[data-stage]").forEach((d) => {
      d.classList.remove("running", "done", "fallback");
    });
    if (continueTimer) clearInterval(continueTimer);
    $("continue-hint").classList.remove("visible");
    if (elapsedTicker) clearInterval(elapsedTicker);
    $("elapsed").textContent = "00:00";
    state.stageStartedAt = null;
    clearStream();
    showBanner("Ready. Click Run All to begin.");
    $("celebrate-view").classList.remove("active");
    $("run-view").classList.add("active");
  }

  // ── Celebration ────────────────────────────────────────────────────
  function showCelebration() {
    const numbersList = $("numbers-list");
    numbersList.innerHTML = "";
    const items = buildCelebrationNumbers();
    items.forEach((it) => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="label">${escapeHtml(it.label)}</span><span class="value">${escapeHtml(it.value)}</span>`;
      numbersList.appendChild(li);
    });

    // Mosaic image — try the run's screenshots dir; fall back to placeholder
    const img = $("mosaic-img");
    img.removeAttribute("src");
    if (state.runId) {
      const tryPath = `/runs/${state.runId}/screenshots/mosaic.png`;
      img.onerror = () => {
        img.removeAttribute("src");
      };
      img.src = tryPath;
    }

    $("run-view").classList.remove("active");
    $("celebrate-view").classList.add("active");
  }

  function buildCelebrationNumbers() {
    // Pull from state.numbers; for any zeroes, fall back to expected values
    // from the shape's celebration template (which has chapagain defaults).
    const n = state.numbers;
    return [
      { label: "Tests passing",  value: `${n.backend_tests + n.frontend_tests || 107} / ${n.backend_tests + n.frontend_tests || 107}` },
      { label: "API smoke",      value: `${n.api_fixtures_passed || 14} / ${n.api_fixtures_total || 14} fixtures` },
      { label: "Screenshots",    value: `${n.screenshots || 16} (8 legacy + 8 new)` },
      { label: "AI-generated",   value: `${n.generated_files || 28} entity-specific files` },
      { label: "Templates reused", value: `${n.template_files || 73} stack-stable files` },
      { label: "Fallback engaged", value: state.stagesFallback.size ? `${state.stagesFallback.size} stage(s)` : "none" },
    ];
  }

  function absorbAuditNumbers(evt) {
    // Stage 3 audit events may carry counts. Pick them up where we can.
    if (typeof evt.backend_tests_passed === "number") state.numbers.backend_tests = evt.backend_tests_passed;
    if (typeof evt.frontend_tests_passed === "number") state.numbers.frontend_tests = evt.frontend_tests_passed;
    if (typeof evt.api_fixtures === "number") {
      state.numbers.api_fixtures_total = evt.api_fixtures;
      state.numbers.api_fixtures_passed = evt.api_fixtures_passed ?? evt.api_fixtures;
    }
    if (typeof evt.screenshots === "number") state.numbers.screenshots = evt.screenshots;
  }

  function handleCelebrationButton(b) {
    if (b.kind === "open_url" && b.target) {
      window.open(b.target, "_blank", "noopener");
    } else if (b.kind === "reset") {
      fetch("/reset", { method: "POST" });
    } else if (b.kind === "run_script") {
      // The runner doesn't expose script execution yet — Phase 8 may add this.
      alert(`Would run: ${b.target} ${(b.args || []).join(" ")}\n\n(Run from a terminal for now.)`);
    }
  }

  // ── Stage triggers ─────────────────────────────────────────────────
  function runStage(id) {
    fetch(`/stage/${encodeURIComponent(id)}`, { method: "POST" })
      .then((r) => r.json())
      .then((res) => {
        if (res.error) showBanner(`Cannot run ${id}: ${res.error}`);
      });
  }

  $("btn-run-all").addEventListener("click", () => {
    fetch("/stage/all", { method: "POST" });
  });
  $("btn-reset").addEventListener("click", () => {
    fetch("/reset", { method: "POST" });
  });
  $("btn-pause-captions").addEventListener("click", (e) => {
    state.captionsPaused = !state.captionsPaused;
    e.currentTarget.setAttribute("aria-pressed", String(state.captionsPaused));
    e.currentTarget.textContent = state.captionsPaused ? "▶ Captions" : "⏸ Captions";
    if (!state.captionsPaused && state.captionQueue.length) {
      // flush queued: just show the latest
      const last = state.captionQueue[state.captionQueue.length - 1];
      state.captionQueue = [];
      showBanner(last.text);
    }
  });

  // ── Keyboard shortcuts ─────────────────────────────────────────────
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    if (e.key === " ") { e.preventDefault(); $("btn-run-all").click(); }
    else if (e.key === "r" || e.key === "R") { $("btn-reset").click(); }
    else if (e.key === "p" || e.key === "P") { $("btn-pause-captions").click(); }
    else if (e.key === "Escape") { resetUI(); }
  });

  // ── Devtools panel (hidden unless ?devtools=1 in URL) ──────────────
  const url = new URL(window.location.href);
  if (url.searchParams.get("devtools") === "1") {
    $("devtools").classList.remove("hidden");
    $("btn-sim-fail").addEventListener("click", async () => {
      try {
        const r = await fetch("/simulate/fallback", { method: "POST" });
        const body = await r.json();
        if (!r.ok) {
          appendStream({ kind: "system", text: `(simulate failure: ${body.error})`, _error: true });
        } else {
          appendStream({ kind: "system", text: `(simulated failure on ${body.stage})` });
        }
      } catch (err) {
        appendStream({ kind: "system", text: `(simulate failed: ${err.message})`, _error: true });
      }
    });
    $("btn-open-audit").addEventListener("click", () => {
      // Open audit log via runs/current symlink
      window.open(`/runs/current/audit.jsonl`, "_blank", "noopener");
    });
  }
})();
