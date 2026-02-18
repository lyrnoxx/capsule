/* ────────────────────────────────────────────────────────
   Logger – client-side: log actions, ring colour, particles
   ──────────────────────────────────────────────────────── */

// API base is injected by the template as window.LOGGER_API_BASE
// e.g. "/logger/api/items" or "/api/items" depending on url_prefix
const API_BASE = (window.LOGGER_API_BASE || "/api/items").replace(/\/+$/, "");

document.addEventListener("DOMContentLoaded", () => {
  colouriseRings();
  bindLogButtons();
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
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error("log failed");
        const data = await res.json();
        updateCard(id, data);
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
