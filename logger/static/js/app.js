/* ────────────────────────────────────────────────────────
   Logger – client-side: log actions, ring colour, particles
   ──────────────────────────────────────────────────────── */

// API base is injected by the template as window.LOGGER_API_BASE
// e.g. "/logger/api/items" or "/api/items" depending on url_prefix
const API_BASE = (window.LOGGER_API_BASE || "/api/items").replace(/\/+$/, "");

document.addEventListener("DOMContentLoaded", () => {
  colouriseRings();
  bindLogButtons();
  bindVizToggles();
});

/* ── Colour helpers ─────────────────────────────────────── */

function hexToRgb(hex) {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHex([r, g, b]) {
  return "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");
}

function lerpColour(a, b, t) {
  return a.map((v, i) => Math.round(v + (b[i] - v) * t));
}

/**
 * Map progress 0‑1 to a gradient pair.
 *   0.00 → red
 *   0.50 → amber
 *   0.85 → green
 *   1.00 → gold
 */
function progressColours(p) {
  const stops = [
    { at: 0, col: hexToRgb("#f87171") },
    { at: 0.5, col: hexToRgb("#fbbf24") },
    { at: 0.85, col: hexToRgb("#34d399") },
    { at: 1.0, col: hexToRgb("#facc15") },
  ];

  let lo = stops[0],
    hi = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (p >= stops[i].at && p <= stops[i + 1].at) {
      lo = stops[i];
      hi = stops[i + 1];
      break;
    }
  }

  const t = (p - lo.at) / (hi.at - lo.at || 1);
  const c1 = rgbToHex(lerpColour(lo.col, hi.col, t));
  const c2 = rgbToHex(
    lerpColour(lo.col, hi.col, Math.min(t + 0.25, 1))
  );
  return [c1, c2];
}

/** Apply gradient colours to every ring on the page. */
function colouriseRings() {
  document.querySelectorAll(".ring-progress").forEach((circle) => {
    const p = parseFloat(circle.dataset.progress) || 0;
    const [c1, c2] = progressColours(p);

    const svg = circle.closest("svg");
    const stops = svg.querySelectorAll("[class^='ring-stop']");
    if (stops.length >= 2) {
      stops[0].style.stopColor = c1;
      stops[1].style.stopColor = c2;
    }
  });
}

/* ── Particle burst ─────────────────────────────────────── */

function spawnParticles(container, colour) {
  const COUNT = 18;
  const rect = container.getBoundingClientRect();
  const cx = rect.width / 2;
  const cy = rect.height / 2;

  for (let i = 0; i < COUNT; i++) {
    const el = document.createElement("span");
    el.className = "particle";
    const angle = (Math.PI * 2 * i) / COUNT + Math.random() * 0.3;
    const dist = 40 + Math.random() * 30;
    el.style.left = cx + "px";
    el.style.top = cy + "px";
    el.style.setProperty("--tx", Math.cos(angle) * dist + "px");
    el.style.setProperty("--ty", Math.sin(angle) * dist + "px");
    el.style.background = colour;
    el.style.width = el.style.height = 3 + Math.random() * 4 + "px";
    container.appendChild(el);
    requestAnimationFrame(() => el.classList.add("burst"));
    el.addEventListener("animationend", () => el.remove());
  }
}

/* ── Log button handler ─────────────────────────────────── */

function bindLogButtons() {
  document.querySelectorAll(".btn-log").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      btn.disabled = true;
      btn.textContent = "…";

      // check for a custom amount input
      const amountInput = document.querySelector(`.log-amount[data-id="${id}"]`);
      const body = {};
      if (amountInput && amountInput.value) {
        body.amount = parseFloat(amountInput.value);
      }

      try {
        const res = await fetch(`${API_BASE}/${id}/log`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": window.CSRF_TOKEN },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error("log failed");
        const data = await res.json();
        updateCard(id, data);
        invalidateGraphCache(id);
        // Redraw graph if it's currently visible
        const card = document.querySelector(`.item-card[data-id="${id}"]`);
        if (card && !card.querySelector(".viz-graph.hidden")) {
          loadAndDrawGraph(id);
        }
        if (amountInput) amountInput.value = "";
      } catch (e) {
        console.error(e);
      } finally {
        btn.disabled = false;
        btn.textContent = "＋ Log";
      }
    });
  });
}

/** Refresh a card (or the detail ring) with new data from the API. */
function updateCard(id, data) {
  const CIRCUMFERENCE = 534.07;
  const p = data.progress;
  const [c1, c2] = progressColours(p);

  // ── Dashboard card ──
  const card = document.querySelector(`.item-card[data-id="${id}"]`);
  if (card) {
    const svg = card.querySelector(".ring-svg");
    const ring = svg.querySelector(".ring-progress");
    const stops = svg.querySelectorAll("[class^='ring-stop']");
    const pctText = svg.querySelector(".ring-pct");
    const valText = svg.querySelector(".ring-val");
    const streak = card.querySelector(".badge-streak");

    ring.style.strokeDashoffset = CIRCUMFERENCE * (1 - p);
    ring.dataset.progress = p;
    if (stops.length >= 2) {
      stops[0].style.stopColor = c1;
      stops[1].style.stopColor = c2;
    }
    pctText.textContent = (p * 100).toFixed(1) + "%";
    valText.textContent = `${data.current_value} / ${Math.round(data.target)}`;
    if (streak) streak.textContent = "🔥 " + data.streak;

    // pulse + particles
    ring.classList.remove("pulse");
    void ring.offsetWidth;
    ring.classList.add("pulse");

    const particles = card.querySelector(".particles");
    if (particles) spawnParticles(particles, c1);
  }

  // ── Detail page ring ──
  const detailRing = document.getElementById("detail-ring");
  if (detailRing) {
    detailRing.style.strokeDashoffset = CIRCUMFERENCE * (1 - p);
    detailRing.dataset.progress = p;

    const svg = detailRing.closest("svg");
    const stops = svg.querySelectorAll("[class^='ring-stop']");
    if (stops.length >= 2) {
      stops[0].style.stopColor = c1;
      stops[1].style.stopColor = c2;
    }

    const pct = document.getElementById("detail-pct");
    const val = document.getElementById("detail-val");
    if (pct) pct.textContent = (p * 100).toFixed(1) + "%";
    if (val) val.textContent = `${data.current_value} / ${Math.round(data.target)}`;

    detailRing.classList.remove("pulse");
    void detailRing.offsetWidth;
    detailRing.classList.add("pulse");

    const particles = document.getElementById("particles-detail");
    if (particles) spawnParticles(particles, c1);

    const statValues = document.querySelectorAll(".stat-value");
    if (statValues.length >= 4) {
      statValues[3].textContent = "🔥 " + data.streak;
    }
  }
}

/* ── Viz toggle (ring ↔ graph) ──────────────────────────── */

/** Cache for fetched graph data so we don't re-fetch every toggle */
const graphCache = {};

function bindVizToggles() {
  document.querySelectorAll(".viz-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const card = btn.closest(".item-card");
      const ringPanel = card.querySelector(".viz-ring");
      const graphPanel = card.querySelector(".viz-graph");
      const iconGraph = btn.querySelector(".icon-graph");
      const iconRing = btn.querySelector(".icon-ring");

      const showingRing = !ringPanel.classList.contains("hidden");

      if (showingRing) {
        // Switch to graph
        ringPanel.classList.add("hidden");
        graphPanel.classList.remove("hidden");
        iconGraph.classList.add("hidden");
        iconRing.classList.remove("hidden");
        loadAndDrawGraph(id);
      } else {
        // Switch to ring
        graphPanel.classList.add("hidden");
        ringPanel.classList.remove("hidden");
        iconRing.classList.add("hidden");
        iconGraph.classList.remove("hidden");
      }
    });
  });
}

async function loadAndDrawGraph(id) {
  if (!graphCache[id]) {
    try {
      const res = await fetch(`${API_BASE}/${id}/history`);
      if (!res.ok) throw new Error("history fetch failed");
      graphCache[id] = await res.json();
    } catch (e) {
      console.error(e);
      return;
    }
  }
  drawGlowGraph(id, graphCache[id]);
}

/** Invalidate cache after a log so the graph refreshes next time */
function invalidateGraphCache(id) {
  delete graphCache[id];
}

/* ── Glowing line graph on <canvas> ─────────────────────── */

function drawGlowGraph(id, data) {
  const canvas = document.getElementById("graph-" + id);
  if (!canvas) return;

  const emptyMsg = canvas.parentElement.querySelector(".graph-empty");
  const points = data.points;

  if (!points || points.length === 0) {
    if (emptyMsg) emptyMsg.classList.remove("has-data");
    return;
  }
  if (emptyMsg) emptyMsg.classList.add("has-data");

  // High-DPI support
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const W = rect.width;
  const H = rect.height;
  const pad = { top: 18, right: 12, bottom: 28, left: 36 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  const target = data.target || 100;
  const maxY = Math.max(target, ...points.map((p) => p.cumulative)) * 1.05;
  const vals = points.map((p) => p.cumulative);

  // Clear
  ctx.clearRect(0, 0, W, H);

  // Get gradient colours from the current progress
  const progress = vals.length ? vals[vals.length - 1] / target : 0;
  const [c1, c2] = progressColours(Math.min(progress, 1));

  // ── Grid lines ──
  ctx.strokeStyle = "rgba(255,255,255,0.05)";
  ctx.lineWidth = 1;
  const gridLines = 4;
  for (let i = 0; i <= gridLines; i++) {
    const y = pad.top + (plotH / gridLines) * i;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(pad.left + plotW, y);
    ctx.stroke();
  }

  // ── Y-axis labels ──
  ctx.fillStyle = "rgba(255,255,255,0.3)";
  ctx.font = "9px Inter, system-ui, sans-serif";
  ctx.textAlign = "right";
  for (let i = 0; i <= gridLines; i++) {
    const y = pad.top + (plotH / gridLines) * i;
    const val = maxY - (maxY / gridLines) * i;
    ctx.fillText(val >= 10 ? Math.round(val) : val.toFixed(1), pad.left - 5, y + 3);
  }

  // ── X-axis labels (first, middle, last) ──
  ctx.textAlign = "center";
  const xLabels = [0, Math.floor(points.length / 2), points.length - 1];
  const uniqueLabels = [...new Set(xLabels)];
  uniqueLabels.forEach((i) => {
    const x = pad.left + (plotW / Math.max(points.length - 1, 1)) * i;
    ctx.fillText(points[i].date, x, H - 6);
  });

  // ── Target line ──
  const targetY = pad.top + plotH * (1 - target / maxY);
  ctx.strokeStyle = "rgba(250,204,21,0.25)";
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(pad.left, targetY);
  ctx.lineTo(pad.left + plotW, targetY);
  ctx.stroke();
  ctx.setLineDash([]);

  // ── Build path ──
  const pathPoints = vals.map((v, i) => ({
    x: pad.left + (plotW / Math.max(vals.length - 1, 1)) * i,
    y: pad.top + plotH * (1 - v / maxY),
  }));

  // ── Gradient fill under curve ──
  const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + plotH);
  grad.addColorStop(0, c1 + "40");
  grad.addColorStop(1, c1 + "00");

  ctx.beginPath();
  ctx.moveTo(pathPoints[0].x, pad.top + plotH);
  pathPoints.forEach((pt) => ctx.lineTo(pt.x, pt.y));
  ctx.lineTo(pathPoints[pathPoints.length - 1].x, pad.top + plotH);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // ── Glowing line ──
  // Outer glow
  ctx.shadowColor = c1;
  ctx.shadowBlur = 14;
  ctx.strokeStyle = c1;
  ctx.lineWidth = 2.5;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.beginPath();
  pathPoints.forEach((pt, i) => (i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y)));
  ctx.stroke();

  // Inner bright line
  ctx.shadowBlur = 6;
  ctx.shadowColor = c2;
  ctx.strokeStyle = c2;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  pathPoints.forEach((pt, i) => (i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y)));
  ctx.stroke();

  ctx.shadowBlur = 0;

  // ── Dots on data points ──
  pathPoints.forEach((pt, i) => {
    ctx.beginPath();
    ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2);
    ctx.fillStyle = i === pathPoints.length - 1 ? "#fff" : c2;
    ctx.fill();
    if (i === pathPoints.length - 1) {
      // glow on latest point
      ctx.shadowColor = c1;
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = c1;
      ctx.fill();
      ctx.shadowBlur = 0;
    }
  });
}
