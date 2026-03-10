/* ────────────────────────────────────────────────────────
   Journal – Keep / Apple Notes style CRUD
   ──────────────────────────────────────────────────────── */

const API = (window.LOGGER_API_BASE || "/api/items").replace(/items\/?$/, "notes");

let notes = window.__NOTES__ || [];
let editingId = null;

document.addEventListener("DOMContentLoaded", () => {
  renderNotes();
  bindComposer();
  buildModal();
});

/* ── Render ────────────────────────────────────────────── */

function renderNotes() {
  const pinned = notes.filter((n) => n.pinned);
  const others = notes.filter((n) => !n.pinned);

  const pinnedGrid = document.getElementById("pinned-grid");
  const othersGrid = document.getElementById("others-grid");
  const pinnedSec = document.getElementById("pinned-section");
  const othersSec = document.getElementById("others-section");
  const empty = document.getElementById("journal-empty");

  pinnedGrid.innerHTML = pinned.map(cardHTML).join("");
  othersGrid.innerHTML = others.map(cardHTML).join("");

  pinnedSec.style.display = pinned.length ? "" : "none";
  othersSec.style.display = others.length ? "" : "none";
  empty.style.display = notes.length ? "none" : "";

  // Re-bind events
  document.querySelectorAll(".note-card").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target.closest(".note-pin") || e.target.closest(".note-action-btn")) return;
      openModal(parseInt(el.dataset.id));
    });
  });
  document.querySelectorAll(".note-pin").forEach((btn) => {
    btn.addEventListener("click", () => togglePin(parseInt(btn.dataset.id)));
  });
  document.querySelectorAll(".note-delete-btn").forEach((btn) => {
    btn.addEventListener("click", () => deleteNote(parseInt(btn.dataset.id)));
  });
}

function cardHTML(n) {
  const date = new Date(n.updated_at).toLocaleDateString("en-US", {
    month: "short", day: "numeric",
  });
  const pinCls = n.pinned ? " pinned" : "";
  return `
    <div class="note-card" data-id="${n.id}" data-color="${n.color}">
      <button class="note-pin${pinCls}" data-id="${n.id}" title="${n.pinned ? "Unpin" : "Pin"}">
        <svg viewBox="0 0 24 24" fill="${n.pinned ? "currentColor" : "none"}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 17v5"/><path d="M9 11V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v7"/>
          <path d="M5 15h14l-1.5-4H6.5L5 15z"/>
        </svg>
      </button>
      ${n.title ? `<div class="note-card-title">${esc(n.title)}</div>` : ""}
      ${n.body ? `<div class="note-card-body">${esc(n.body)}</div>` : ""}
      <div class="note-card-footer">
        <span class="note-card-date">${date}</span>
        <div class="note-actions">
          <button class="note-action-btn note-delete-btn" data-id="${n.id}" title="Delete">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
              <path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
            </svg>
          </button>
        </div>
      </div>
    </div>`;
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/* ── Composer ──────────────────────────────────────────── */

function bindComposer() {
  const titleEl = document.getElementById("composer-title");
  const bodyEl = document.getElementById("composer-body");
  const saveBtn = document.getElementById("composer-save");
  const colorsEl = document.getElementById("composer-colors");
  let selectedColor = "default";

  // Auto-expand textarea
  bodyEl.addEventListener("input", () => {
    bodyEl.style.height = "auto";
    bodyEl.style.height = bodyEl.scrollHeight + "px";
  });

  // Color selection
  colorsEl.querySelectorAll(".color-dot").forEach((dot) => {
    dot.addEventListener("click", () => {
      colorsEl.querySelector(".active")?.classList.remove("active");
      dot.classList.add("active");
      selectedColor = dot.dataset.color;
    });
  });

  saveBtn.addEventListener("click", async () => {
    const title = titleEl.value.trim();
    const body = bodyEl.value.trim();
    if (!title && !body) return;

    saveBtn.disabled = true;
    saveBtn.textContent = "…";

    try {
      const res = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": window.CSRF_TOKEN },
        body: JSON.stringify({ title, body, color: selectedColor }),
      });
      if (!res.ok) throw new Error("create failed");
      const note = await res.json();
      notes.unshift(note);
      renderNotes();

      // reset
      titleEl.value = "";
      bodyEl.value = "";
      bodyEl.style.height = "auto";
      colorsEl.querySelector(".active")?.classList.remove("active");
      colorsEl.querySelector('[data-color="default"]').classList.add("active");
      selectedColor = "default";
    } catch (e) {
      console.error(e);
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = "Save";
    }
  });
}

/* ── Pin toggle ────────────────────────────────────────── */

async function togglePin(id) {
  const note = notes.find((n) => n.id === id);
  if (!note) return;

  try {
    const res = await fetch(`${API}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-CSRFToken": window.CSRF_TOKEN },
      body: JSON.stringify({ pinned: !note.pinned }),
    });
    if (!res.ok) throw new Error();
    const updated = await res.json();
    Object.assign(note, updated);
    renderNotes();
  } catch (e) { console.error(e); }
}

/* ── Delete ────────────────────────────────────────────── */

async function deleteNote(id) {
  try {
    const res = await fetch(`${API}/${id}`, { method: "DELETE", headers: { "X-CSRFToken": window.CSRF_TOKEN } });
    if (!res.ok) throw new Error();
    notes = notes.filter((n) => n.id !== id);
    renderNotes();
    closeModal();
  } catch (e) { console.error(e); }
}

/* ── Edit modal ────────────────────────────────────────── */

let overlay, modalTitle, modalBody, modalColors, modalSaveBtn, modalDeleteBtn;

function buildModal() {
  overlay = document.createElement("div");
  overlay.className = "note-modal-overlay";
  overlay.innerHTML = `
    <div class="note-modal">
      <input class="modal-title" placeholder="Title" />
      <textarea class="modal-body" placeholder="Note…"></textarea>
      <div class="modal-toolbar">
        <div class="color-picker" id="modal-colors">
          <button class="color-dot" data-color="default" title="Default"></button>
          <button class="color-dot" data-color="red" title="Red"></button>
          <button class="color-dot" data-color="orange" title="Orange"></button>
          <button class="color-dot" data-color="yellow" title="Yellow"></button>
          <button class="color-dot" data-color="green" title="Green"></button>
          <button class="color-dot" data-color="blue" title="Blue"></button>
          <button class="color-dot" data-color="purple" title="Purple"></button>
        </div>
        <div style="display:flex;gap:.4rem;">
          <button class="btn btn-sm btn-danger" id="modal-delete">Delete</button>
          <button class="btn btn-sm btn-glow" id="modal-save">Save</button>
        </div>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  modalTitle = overlay.querySelector(".modal-title");
  modalBody = overlay.querySelector(".modal-body");
  modalColors = overlay.querySelector("#modal-colors");
  modalSaveBtn = overlay.querySelector("#modal-save");
  modalDeleteBtn = overlay.querySelector("#modal-delete");

  // Close on backdrop click
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) saveAndClose();
  });

  // Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && overlay.classList.contains("open")) saveAndClose();
  });

  // Color dots
  modalColors.querySelectorAll(".color-dot").forEach((dot) => {
    dot.addEventListener("click", () => {
      modalColors.querySelector(".active")?.classList.remove("active");
      dot.classList.add("active");
    });
  });

  modalSaveBtn.addEventListener("click", () => saveAndClose());
  modalDeleteBtn.addEventListener("click", () => {
    if (editingId) deleteNote(editingId);
  });
}

function openModal(id) {
  const note = notes.find((n) => n.id === id);
  if (!note) return;
  editingId = id;

  modalTitle.value = note.title;
  modalBody.value = note.body;

  // Set modal color
  overlay.querySelector(".note-modal").dataset.color = note.color;
  modalColors.querySelector(".active")?.classList.remove("active");
  const dot = modalColors.querySelector(`[data-color="${note.color}"]`);
  if (dot) dot.classList.add("active");

  // Apply colour to modal background
  applyModalColor(note.color);

  overlay.classList.add("open");
  modalTitle.focus();
}

function applyModalColor(color) {
  const modal = overlay.querySelector(".note-modal");
  const colorMap = {
    default: "var(--surface)",
    red: "#3b1c1c",
    orange: "#3b2810",
    yellow: "#33300e",
    green: "#142a1e",
    blue: "#111f35",
    purple: "#27113b",
  };
  modal.style.background = colorMap[color] || colorMap.default;
}

async function saveAndClose() {
  if (!editingId) { closeModal(); return; }

  const title = modalTitle.value.trim();
  const body = modalBody.value.trim();
  const activeDot = modalColors.querySelector(".active");
  const color = activeDot ? activeDot.dataset.color : "default";

  try {
    const res = await fetch(`${API}/${editingId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-CSRFToken": window.CSRF_TOKEN },
      body: JSON.stringify({ title, body, color }),
    });
    if (!res.ok) throw new Error();
    const updated = await res.json();
    const idx = notes.findIndex((n) => n.id === editingId);
    if (idx !== -1) Object.assign(notes[idx], updated);
    renderNotes();
  } catch (e) { console.error(e); }

  closeModal();
}

function closeModal() {
  overlay.classList.remove("open");
  editingId = null;
}
