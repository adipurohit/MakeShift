/* ---------------------------------------------------------------
   CUBE — Scrap to Creation. Fusion-style 3-panel layout:
   left = inventory + AI "buildable now", center = 2D/3D viewer,
   right = full recipe catalog. Shared crafting sandbox for every
   AI-generated idea; the offline Robot Arm example stays isolated
   so it always works with zero network/AI.
   --------------------------------------------------------------- */

import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";

const STORAGE_KEY = "cube_mvp_state_v3";

const PALETTE_COLORS = ["#c0584a", "#3f8f5f", "#6f55c0", "#3a6fc0", "#b88a2e", "#2e9aa6"];
function colorForId(id) {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  return PALETTE_COLORS[hash % PALETTE_COLORS.length];
}
function shortFor(name) {
  const words = name.trim().split(/\s+/);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}
function slugify(name) {
  return "m_" + name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 40);
}

/* ---------------- Offline fallback idea (always available, isolated sandbox) ---------------- */
const OFFLINE_IDEA = {
  id: "offline_robot_arm",
  title: "Robot Arm",
  pitch: "Strip two broken 3D printers for motors, rails and electronics, and build a 2-joint robot arm with a gripper made from the dead nozzles.",
  offline: true,
  rawMaterials: [
    { id: "stepper", name: "Stepper Motor", qty: 4 },
    { id: "pulley", name: "Pulley", qty: 2 },
    { id: "belt", name: "Timing Belt", qty: 2 }, // 2 joints x 1 belt each; at 1 the offline demo can't finish
    { id: "extrusion", name: "Al. Extrusion", qty: 2 },
    { id: "rod", name: "Smooth Rod", qty: 2 },
    { id: "bearing", name: "Linear Bearing", qty: 2 },
    { id: "nozzle", name: "Dead Nozzle", qty: 2 },
    { id: "zip", name: "Zip Tie", qty: 2 },
    { id: "board", name: "Control Board", qty: 1 },
    { id: "psu", name: "Power Supply", qty: 1 },
    { id: "limit", name: "Limit Switch", qty: 1 },
  ],
  recipes: [
    { a: "stepper", b: "pulley", result_id: "driveunit", result_name: "Drive Unit", result_short: "DU" },
    { a: "driveunit", b: "belt", result_id: "joint", result_name: "Motorized Joint", result_short: "MJ" },
    { a: "extrusion", b: "rod", result_id: "rail", result_name: "Rail", result_short: "RL" },
    { a: "rail", b: "bearing", result_id: "armseg", result_name: "Arm Segment", result_short: "AS" },
    { a: "nozzle", b: "zip", result_id: "gripper", result_name: "Gripper Claw", result_short: "GC" },
  ],
  final_requires: [
    { id: "joint", qty: 2 },
    { id: "armseg", qty: 2 },
    { id: "gripper", qty: 1 },
    { id: "board", qty: 1 },
    { id: "psu", qty: 1 },
    { id: "limit", qty: 1 },
  ],
  assembly_steps: [
    "Mount the two Motorized Joints to the frame to form the shoulder and elbow pivots.",
    "Attach an Arm Segment to each Motorized Joint using the Linear Bearings as sliding supports.",
    "Thread the Timing Belt around each joint's pulley and tension by hand.",
    "Secure the Gripper Claw (built from salvaged nozzle tips) to the end of the final Arm Segment.",
    "Wire the Stepper Motors to the salvaged Control Board.",
    "Connect the Power Supply and the Limit Switch to the Control Board for homing.",
    "Power on, run the homing sequence, and test open/close on the Gripper Claw.",
  ],
};

/* ---------------- Persistent state ---------------- */
function defaultState() {
  return {
    items: {},        // id -> {name, short, color, raw}
    inventory: {},     // id -> qty (shared sandbox: real materials + AI-idea intermediates)
    discovered: [],    // ids ever crafted (shared sandbox)
    bench: [],         // [{uid, itemId, x, y, x3, z3}] (shared sandbox)
    offline: {         // isolated sandbox for the offline example only
      inventory: {},
      discovered: [],
      bench: [],
    },
    ideaLibrary: [],   // AI-generated ideas (phase 1, resolved)
    activeIdeaId: null,
    assemblySteps: {}, // ideaId -> [steps], cached once generated
    badges: [],
  };
}

let state = loadState();
// Bench tokens persist across reloads, so new uids must start past every saved
// one. Restarting at 1 made a fresh token share a uid with a saved token, and
// the merge check (t.uid !== movedTok.uid) then skipped the real partner.
let uidCounter = 1 + Math.max(0, ...[...state.bench, ...state.offline.bench].map((t) => t.uid || 0));

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultState();
    const parsed = JSON.parse(raw);
    if (!parsed.items || !parsed.offline) return defaultState();
    return parsed;
  } catch (e) {
    return defaultState();
  }
}
function saveState() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) {}
}

function registerItem(id, meta) {
  if (!state.items[id]) state.items[id] = meta;
}

/* ---------------- Active crafting context ----------------
   The offline idea gets its own isolated inventory/discovered/bench so it
   always works standalone with zero AI/network. Everything else shares one
   global sandbox, since real materials are genuinely shared across ideas. */
function isOfflineActive() {
  return state.activeIdeaId === OFFLINE_IDEA.id;
}
function ctx() {
  return isOfflineActive() ? state.offline : state;
}
function qty(id) { return ctx().inventory[id] || 0; }
function addQty(id, n) {
  const c = ctx();
  c.inventory[id] = (c.inventory[id] || 0) + n;
  saveState();
}

/* ---------------- Idea normalization & namespacing ---------------- */
function rawIdsForIdea(idea) {
  return idea.offline ? idea.rawMaterials.map((m) => m.id) : (idea.uses_material_ids || []);
}
function namespacedId(idea, id) {
  return rawIdsForIdea(idea).includes(id) ? id : idea.id + "__" + id;
}

// Registers an idea's intermediate items into the global metadata registry
// (and the offline idea's raw items into its own isolated inventory), and
// returns {recipes:[{a,b,result}], finalRequires:{id:qty}} with ids resolved.
function resolveIdea(idea) {
  // Recomputed every call (cheap, small N) rather than cached on the idea
  // object itself — that object can outlive a Reset, which would otherwise
  // leave items registered against a localStorage state that no longer exists.
  if (idea.offline) {
    idea.rawMaterials.forEach((m) => {
      registerItem(m.id, { name: m.name, short: shortFor(m.name), color: colorForId(m.id), raw: true });
      if (state.offline.inventory[m.id] === undefined) state.offline.inventory[m.id] = m.qty;
    });
  }

  const recipes = [];
  const finalRequires = {};
  (idea.recipes || []).forEach((r) => {
    const resultId = namespacedId(idea, r.result_id);
    registerItem(resultId, { name: r.result_name, short: r.result_short || shortFor(r.result_name), color: colorForId(resultId), raw: false });
    recipes.push({ a: namespacedId(idea, r.a), b: namespacedId(idea, r.b), result: resultId });
  });
  (idea.final_requires || []).forEach((f) => {
    finalRequires[namespacedId(idea, f.id)] = f.qty;
  });

  return { recipes, finalRequires };
}

function allIdeas() {
  return [OFFLINE_IDEA, ...state.ideaLibrary];
}
function findIdea(id) {
  return allIdeas().find((i) => i.id === id);
}

/* ---------------- Toast ---------------- */
let toastTimer = null;
function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("visible"), 2600);
}

/* ================= INVENTORY PANEL ================= */
function renderInventory() {
  const grid = document.getElementById("inventoryGrid");
  grid.innerHTML = "";
  const rawIds = Object.keys(state.items).filter(
    (id) => state.items[id].raw && Object.prototype.hasOwnProperty.call(state.inventory, id)
  );
  rawIds.forEach((id) => {
    const item = state.items[id];
    const have = state.inventory[id] || 0;
    const card = document.createElement("div");
    card.className = "item-card";
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div class="item-icon" style="background:${item.color}">${item.short}</div>
        <button class="item-remove" data-id="${id}" title="Remove">✕</button>
      </div>
      <div class="item-name">${item.name}</div>
      <div class="item-qty-row">
        <div class="item-qty">${have}</div>
        <div class="qty-controls">
          <button class="qty-btn" data-op="dec" data-id="${id}">-</button>
          <button class="qty-btn" data-op="inc" data-id="${id}">+</button>
        </div>
      </div>
    `;
    grid.appendChild(card);
  });

  document.getElementById("inventoryEmptyNote").classList.toggle("visible", rawIds.length === 0);

  grid.querySelectorAll(".qty-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const delta = btn.dataset.op === "inc" ? 1 : -1;
      if (delta < 0 && (state.inventory[id] || 0) <= 0) return;
      state.inventory[id] = (state.inventory[id] || 0) + delta;
      saveState();
      renderAllForInventoryChange();
    });
  });
  grid.querySelectorAll(".item-remove").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      delete state.items[id];
      delete state.inventory[id];
      saveState();
      renderAllForInventoryChange();
    });
  });
}

function addMaterial(name, qty0) {
  const id = slugify(name) || ("m_" + Date.now());
  registerItem(id, { name, short: shortFor(name), color: colorForId(id), raw: true });
  state.inventory[id] = (state.inventory[id] || 0) + qty0;
  saveState();
  renderAllForInventoryChange();
}

function initMaterialsForm() {
  document.getElementById("addMaterialForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const nameInput = document.getElementById("materialNameInput");
    const qtyInput = document.getElementById("materialQtyInput");
    const name = nameInput.value.trim();
    const q = Math.max(1, parseInt(qtyInput.value, 10) || 1);
    if (!name) return;
    addMaterial(name, q);
    nameInput.value = "";
    qtyInput.value = "1";
    nameInput.focus();
  });
}

function renderAllForInventoryChange() {
  renderInventory();
  renderPalette();
  renderCatalog();
  renderBuildableNow();
  renderRequirements();
}

/* ================= AI IDEA GENERATION (phase 1) ================= */
function initGenerateButtons() {
  document.getElementById("refreshIdeasBtn").addEventListener("click", () => generateIdeas());
}

async function generateIdeas() {
  const rawMaterials = Object.keys(state.items)
    .filter((id) => state.items[id].raw)
    .map((id) => ({ id, name: state.items[id].name, qty: state.inventory[id] || 0 }));

  if (rawMaterials.length === 0) {
    toast("Add or scan a material first");
    return;
  }

  const btn = document.getElementById("refreshIdeasBtn");
  btn.disabled = true;
  toast("✨ Generating build ideas...");

  try {
    const res = await fetch("/api/generate-ideas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ materials: rawMaterials }),
    });
    const data = await res.json();
    if (!res.ok) {
      toast("⚠️ " + (data.message || "Couldn't generate ideas") + " — offline example still works");
      document.getElementById("generateError").textContent = "⚠️ " + (data.message || "Couldn't generate ideas.");
      document.getElementById("generateError").classList.add("visible");
    } else {
      document.getElementById("generateError").classList.remove("visible");
      state.ideaLibrary = data.ideas || [];
      state.ideaLibrary.forEach((idea) => resolveIdea(idea));
      if (state.activeIdeaId && state.activeIdeaId !== OFFLINE_IDEA.id && !findIdea(state.activeIdeaId)) {
        state.activeIdeaId = null;
      }
      saveState();
      toast(`✨ Generated ${state.ideaLibrary.length} ideas`);
    }
  } catch (e) {
    toast("⚠️ Couldn't reach the server — offline example still works");
  }

  btn.disabled = false;
  renderBuildableNow();
  renderCatalog();
  renderRequirements();
}

/* ================= LEFT PANEL: buildable now ================= */
function matchPercent(idea) {
  const ids = rawIdsForIdea(idea);
  if (ids.length === 0) return 0;
  const have = ids.filter((id) => (idea.offline ? state.offline.inventory[id] > 0 : (state.inventory[id] || 0) > 0)).length;
  return Math.round((have / ids.length) * 100);
}

function readyPercent(idea) {
  const resolved = resolveIdea(idea);
  const entries = Object.entries(resolved.finalRequires);
  if (entries.length === 0) return 0;
  const inv = idea.offline ? state.offline.inventory : state.inventory;
  const ready = entries.filter(([id, need]) => (inv[id] || 0) >= need).length;
  return Math.round((ready / entries.length) * 100);
}

function renderBuildableNow() {
  const list = document.getElementById("buildableNowList");
  list.innerHTML = "";
  const candidates = allIdeas().filter((i) => matchPercent(i) === 100);
  document.getElementById("buildableNowEmptyNote").classList.toggle("visible", candidates.length === 0);
  candidates.forEach((idea) => list.appendChild(buildIdeaRow(idea, true)));
}

function buildIdeaRow(idea, compact) {
  const row = document.createElement("div");
  row.className = "idea-row" + (idea.id === state.activeIdeaId ? " active" : "");
  const rp = readyPercent(idea);
  let badge;
  if (idea.offline) badge = `<span class="idea-badge offline-badge">offline</span>`;
  else if (rp === 100) badge = `<span class="idea-badge ready-badge">ready!</span>`;
  else badge = `<span class="idea-badge match-badge">${rp}% ready</span>`;

  row.innerHTML = `
    <div class="idea-row-top">
      <div class="idea-row-title">${idea.title}</div>
      ${badge}
    </div>
    ${compact ? "" : `<p class="pitch">${idea.pitch}</p>`}
  `;
  row.addEventListener("click", () => setActiveIdea(idea.id));
  return row;
}

/* ================= RIGHT PANEL: full catalog ================= */
function renderCatalog() {
  const list = document.getElementById("catalogList");
  list.innerHTML = "";
  const ideas = allIdeas();
  document.getElementById("catalogCount").textContent = ideas.length ? `${ideas.length} recipes` : "";
  document.getElementById("catalogEmptyNote").classList.toggle("visible", ideas.length === 0);
  ideas.forEach((idea) => list.appendChild(buildIdeaRow(idea, false)));
}

/* ================= ACTIVE RECIPE / REQUIREMENTS ================= */
function setActiveIdea(id) {
  state.activeIdeaId = id;
  saveState();
  const idea = findIdea(id);
  document.getElementById("activeRecipeLabel").textContent = idea ? "Building: " + idea.title : "No recipe selected";
  renderPalette();
  renderBench();
  renderBuildableNow();
  renderCatalog();
  renderRequirements();
}

function renderRequirements() {
  const idea = findIdea(state.activeIdeaId);
  const emptyEl = document.getElementById("requirementsEmpty");
  const activeEl = document.getElementById("requirementsActive");
  if (!idea) {
    emptyEl.hidden = false;
    activeEl.hidden = true;
    renderHolograms(null);
    return;
  }
  emptyEl.hidden = true;
  activeEl.hidden = false;

  const resolved = resolveIdea(idea);
  const inv = idea.offline ? state.offline.inventory : state.inventory;
  const entries = Object.entries(resolved.finalRequires);
  const reqList = document.getElementById("reqList");
  reqList.innerHTML = "";
  let readyCount = 0;
  entries.forEach(([id, need]) => {
    const have = inv[id] || 0;
    const ok = have >= need;
    if (ok) readyCount++;
    const item = state.items[id];
    const li = document.createElement("li");
    li.className = "req-item " + (ok ? "green" : "red");
    li.innerHTML = `<span>${item ? item.name : id}</span><span class="req-count">${have} / ${need}</span>`;
    reqList.appendChild(li);
  });
  document.getElementById("progressFill").style.width = (entries.length ? readyCount / entries.length * 100 : 0) + "%";
  document.getElementById("progressLabel").textContent = `${readyCount} / ${entries.length} ready`;
  document.getElementById("buildBtn").disabled = entries.length === 0 || readyCount < entries.length;

  renderHolograms(idea);
}

function renderHolograms(idea) {
  const row = document.getElementById("hologramRow");
  row.innerHTML = "";
  if (idea) {
    const resolved = resolveIdea(idea);
    const inv = idea.offline ? state.offline.inventory : state.inventory;
    Object.entries(resolved.finalRequires).forEach(([id, need]) => {
      const item = state.items[id];
      const have = inv[id] || 0;
      const chip = document.createElement("div");
      chip.className = "hologram-chip" + (have >= need ? " satisfied" : "");
      chip.innerHTML = `<span class="chip-icon" style="background:${item.color}">${item.short}</span>${item.name} ${have}/${need}`;
      row.appendChild(chip);
    });
  }
  render3DHolograms(idea);
}

function initBuildButton() {
  document.getElementById("buildBtn").addEventListener("click", () => {
    const idea = findIdea(state.activeIdeaId);
    if (!idea) return;
    const resolved = resolveIdea(idea);
    const inv = idea.offline ? state.offline.inventory : state.inventory;
    Object.entries(resolved.finalRequires).forEach(([id, need]) => { inv[id] -= need; });
    saveState();
    renderPalette();
    renderRequirements();
    openAssemblyModal(idea);
  });
}

/* ================= MERGE SANDBOX (shared by 2D + 3D) ================= */
function activeRecipesFirst() {
  const idea = findIdea(state.activeIdeaId);
  const list = [];
  if (idea) list.push(...resolveIdea(idea).recipes);
  allIdeas().forEach((i) => { if (i.id !== state.activeIdeaId) list.push(...resolveIdea(i).recipes); });
  return list;
}
function findRecipe(idA, idB) {
  const recipes = isOfflineActive() ? resolveIdea(OFFLINE_IDEA).recipes : activeRecipesFirst();
  return recipes.find((r) => (r.a === idA && r.b === idB) || (r.a === idB && r.b === idA));
}

function paletteItemIds() {
  if (isOfflineActive()) return Object.keys(state.offline.inventory);
  return Object.keys(state.items).filter((id) => {
    // hide ids that only belong to the isolated offline idea
    const inGlobal = Object.prototype.hasOwnProperty.call(state.inventory, id);
    return inGlobal;
  });
}

function renderPalette() {
  const list = document.getElementById("paletteList");
  list.innerHTML = "";
  paletteItemIds().forEach((id) => {
    const item = state.items[id];
    if (!item) return;
    const available = qty(id);
    if (!item.raw && available <= 0) return;
    const chip = document.createElement("div");
    chip.className = "chip" + (available <= 0 ? " disabled" : "");
    chip.dataset.id = id;
    chip.innerHTML = `
      <span class="chip-icon" style="background:${item.color}">${item.short}</span>
      <span>${item.name}</span>
      <span class="chip-qty">${available}</span>
    `;
    if (available > 0) attachPaletteDrag(chip, id);
    list.appendChild(chip);
  });
}

function attachPaletteDrag(chipEl, id) {
  chipEl.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    const ghost = chipEl.cloneNode(true);
    ghost.style.position = "fixed";
    ghost.style.left = e.clientX - 20 + "px";
    ghost.style.top = e.clientY - 15 + "px";
    ghost.style.zIndex = 999;
    ghost.style.pointerEvents = "none";
    ghost.style.opacity = "0.9";
    ghost.style.width = chipEl.offsetWidth + "px";
    document.body.appendChild(ghost);

    function onMove(ev) {
      ghost.style.left = ev.clientX - 20 + "px";
      ghost.style.top = ev.clientY - 15 + "px";
    }
    function onUp(ev) {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      ghost.remove();
      if (qty(id) <= 0) return;

      if (currentView === "3d") {
        const canvasRect = document.getElementById("threeCanvas").getBoundingClientRect();
        if (isInsideRect(canvasRect, ev.clientX, ev.clientY)) {
          dropOntoThree(id, ev.clientX, ev.clientY);
        }
        return;
      }

      const bench = document.getElementById("bench");
      const rect = bench.getBoundingClientRect();
      const insideBench = isInsideRect(rect, ev.clientX, ev.clientY);
      if (!insideBench) return;

      const x = Math.max(0, Math.min(rect.width - 40, ev.clientX - rect.left - 20));
      const y = Math.max(0, Math.min(rect.height - 30, ev.clientY - rect.top - 15));
      addQty(id, -1);
      const newTok = { uid: uidCounter++, itemId: id, x, y: y + 40 };
      ctx().bench.push(newTok);
      persistBench();
      renderBench();
      renderPalette();
      tryMergeAt(newTok);
    }
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
  });
}

function persistBench() { saveState(); }

function renderBench() {
  renderBench2D();
  renderBench3D();
}

function renderBench2D() {
  const bench = document.getElementById("bench");
  const empty = document.getElementById("benchEmpty");
  bench.querySelectorAll(".bench-token").forEach((n) => n.remove());
  const tokens = ctx().bench;
  empty.style.display = tokens.length ? "none" : "flex";
  tokens.forEach((tok) => {
    const item = state.items[tok.itemId];
    if (!item) return;
    const el = document.createElement("div");
    el.className = "bench-token";
    el.dataset.uid = tok.uid;
    el.style.left = tok.x + "px";
    el.style.top = tok.y + "px";
    el.innerHTML = `
      <span class="chip-icon" style="background:${item.color}">${item.short}</span>
      <span>${item.name}</span>
    `;
    attachTokenDrag2D(el, tok);
    bench.appendChild(el);
  });
}

function attachTokenDrag2D(el, tok) {
  el.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    const bench = document.getElementById("bench");
    const benchRect = bench.getBoundingClientRect();
    const startX = e.clientX;
    const startY = e.clientY;
    const origX = tok.x;
    const origY = tok.y;
    el.setPointerCapture(e.pointerId);
    el.style.zIndex = 50;

    function onMove(ev) {
      const dx = ev.clientX - startX;
      const dy = ev.clientY - startY;
      tok.x = Math.max(0, Math.min(benchRect.width - 40, origX + dx));
      tok.y = Math.max(0, Math.min(benchRect.height - 30, origY + dy));
      el.style.left = tok.x + "px";
      el.style.top = tok.y + "px";
    }
    function onUp() {
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.style.zIndex = "";
      persistBench();
      tryMergeAt(tok);
    }
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
  });
}

function overlap2D(a, b) {
  return Math.abs(a.x - b.x) < 50 && Math.abs(a.y - b.y) < 36;
}

function tryMergeAt(movedTok) {
  const tokens = ctx().bench;
  const partner = tokens.find((t) => t.uid !== movedTok.uid && overlap2D(t, movedTok));
  if (!partner) { renderBench(); return; }

  const recipe = findRecipe(movedTok.itemId, partner.itemId);
  if (!recipe) {
    const el = document.querySelector(`.bench-token[data-uid="${movedTok.uid}"]`);
    if (el) { el.classList.add("shake"); setTimeout(() => el.classList.remove("shake"), 320); }
    shake3DMesh(movedTok.uid);
    return;
  }

  const c = ctx();
  c.bench = c.bench.filter((t) => t.uid !== movedTok.uid && t.uid !== partner.uid);
  const resultX = (movedTok.x + partner.x) / 2;
  const resultY = (movedTok.y + partner.y) / 2;
  addQty(recipe.result, 1);

  const firstTime = !c.discovered.includes(recipe.result);
  if (firstTime) { c.discovered.push(recipe.result); }
  saveState();
  toast((firstTime ? "✨ Discovered: " : "Crafted another: ") + state.items[recipe.result].name);

  renderBench();
  renderPalette();
  renderDiscoveries();
  renderRequirements();
  renderBuildableNow();
  renderCatalog();
}

function renderDiscoveries() {
  // discoveries are folded into the hologram/requirements view; kept as a no-op
  // hook in case a future pass wants a dedicated discovery log again.
}

function initBench() {
  document.getElementById("clearBenchBtn").addEventListener("click", () => {
    const c = ctx();
    c.bench.forEach((t) => addQty(t.itemId, 1));
    c.bench = [];
    saveState();
    renderBench();
    renderPalette();
  });
}

/* ================= VIEW TOGGLE (2D / 3D) ================= */
let currentView = "2d";
function initViewToggle() {
  document.querySelectorAll(".view-toggle-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".view-toggle-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentView = btn.dataset.view;
      document.querySelectorAll(".viewer-pane").forEach((p) => p.classList.remove("active"));
      document.getElementById("viewer" + currentView).classList.add("active");
      if (currentView === "3d") {
        initThreeIfNeeded();
        resizeThree();
        renderBench3D();
        render3DHolograms(findIdea(state.activeIdeaId));
      }
    });
  });
}

/* ================= 3D VIEWER (Three.js) ================= */
let three = null; // { renderer, scene, camera, controls, groundPlane, meshByUid, holoGroup }

function makeTextSprite(text, color) {
  const canvas = document.createElement("canvas");
  canvas.width = 256; canvas.height = 64;
  const ctx2d = canvas.getContext("2d");
  ctx2d.fillStyle = "rgba(0,0,0,0)";
  ctx2d.fillRect(0, 0, canvas.width, canvas.height);
  ctx2d.font = "bold 32px -apple-system, sans-serif";
  ctx2d.fillStyle = color || "#1c1e1b";
  ctx2d.textAlign = "center";
  ctx2d.textBaseline = "middle";
  ctx2d.fillText(text, canvas.width / 2, canvas.height / 2);
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(1.6, 0.4, 1);
  return sprite;
}

function meshGeometryFor(item) {
  return item.raw
    ? new THREE.BoxGeometry(0.7, 0.7, 0.7)
    : new THREE.IcosahedronGeometry(0.5, 0);
}

function initThreeIfNeeded() {
  if (three) return;
  const canvas = document.getElementById("threeCanvas");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
  camera.position.set(7, 7, 9);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.target.set(0, 0.5, 0);

  scene.add(new THREE.AmbientLight(0xffffff, 0.7));
  const dir = new THREE.DirectionalLight(0xffffff, 0.9);
  dir.position.set(6, 10, 4);
  scene.add(dir);

  const grid = new THREE.GridHelper(16, 16, 0x8a8f86, 0xd8d4c8);
  scene.add(grid);

  const groundPlane = new THREE.Mesh(
    new THREE.PlaneGeometry(200, 200),
    new THREE.MeshBasicMaterial({ visible: false })
  );
  groundPlane.rotation.x = -Math.PI / 2;
  scene.add(groundPlane);

  const holoGroup = new THREE.Group();
  scene.add(holoGroup);

  three = { renderer, scene, camera, controls, groundPlane, meshByUid: new Map(), holoGroup };

  initThreeDrag();

  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();
}

function resizeThree() {
  if (!three) return;
  const el = document.getElementById("viewer3d");
  const w = el.clientWidth || 400;
  const h = el.clientHeight || 400;
  three.renderer.setSize(w, h, false);
  three.camera.aspect = w / h;
  three.camera.updateProjectionMatrix();
}
window.addEventListener("resize", () => { if (currentView === "3d") resizeThree(); });

function layoutIndexFor(tokens, uid) {
  return tokens.findIndex((t) => t.uid === uid);
}

function renderBench3D() {
  if (!three) return;
  const tokens = ctx().bench;
  const seen = new Set();

  tokens.forEach((tok, i) => {
    seen.add(tok.uid);
    const item = state.items[tok.itemId];
    if (!item) return;
    if (tok.x3 === undefined) {
      tok.x3 = (i % 4 - 1.5) * 1.6;
      tok.z3 = Math.floor(i / 4) * 1.6 - 1;
    }
    let mesh = three.meshByUid.get(tok.uid);
    if (!mesh) {
      const geo = meshGeometryFor(item);
      const mat = new THREE.MeshStandardMaterial({ color: item.color, roughness: 0.5, metalness: 0.1 });
      mesh = new THREE.Mesh(geo, mat);
      mesh.userData.uid = tok.uid;
      const label = makeTextSprite(item.short, "#ffffff");
      label.position.set(0, 0.7, 0);
      mesh.add(label);
      three.scene.add(mesh);
      three.meshByUid.set(tok.uid, mesh);
    }
    mesh.position.set(tok.x3, 0.4, tok.z3);
  });

  for (const [uid, mesh] of three.meshByUid.entries()) {
    if (!seen.has(uid)) {
      three.scene.remove(mesh);
      three.meshByUid.delete(uid);
    }
  }
}

function render3DHolograms(idea) {
  if (!three) return;
  three.holoGroup.clear();
  if (!idea) return;
  const resolved = resolveIdea(idea);
  const inv = idea.offline ? state.offline.inventory : state.inventory;
  const entries = Object.entries(resolved.finalRequires);
  entries.forEach(([id, need], i) => {
    const item = state.items[id];
    if (!item) return;
    const have = inv[id] || 0;
    const satisfied = have >= need;
    const geo = meshGeometryFor(item);
    const mat = new THREE.MeshBasicMaterial({
      color: item.color,
      wireframe: !satisfied,
      transparent: true,
      opacity: satisfied ? 0.85 : 0.4,
    });
    const mesh = new THREE.Mesh(geo, mat);
    const x = (i % 4 - 1.5) * 1.6;
    const z = Math.floor(i / 4) * 1.6 - 1;
    mesh.position.set(x, 2.4, z);
    const label = makeTextSprite(`${item.short} ${have}/${need}`, "#1c1e1b");
    label.position.set(0, 0.7, 0);
    mesh.add(label);
    three.holoGroup.add(mesh);
  });
}

function isInsideRect(rect, x, y) {
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

// Drops a brand-new palette item directly onto the 3D stage (raycast against
// the ground plane at the drop point), mirroring the 2D palette-to-bench drop.
function dropOntoThree(id, clientX, clientY) {
  if (!three) return;
  const canvas = three.renderer.domElement;
  const rect = canvas.getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((clientX - rect.left) / rect.width) * 2 - 1,
    -((clientY - rect.top) / rect.height) * 2 + 1
  );
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(ndc, three.camera);
  const hit = raycaster.intersectObject(three.groundPlane, false)[0];
  if (!hit) return;

  addQty(id, -1);
  const newTok = { uid: uidCounter++, itemId: id, x: 40, y: 40, x3: hit.point.x, z3: hit.point.z };
  ctx().bench.push(newTok);
  persistBench();
  renderBench();
  renderPalette();
  tryMergeAt3D(newTok.uid);
}

function shake3DMesh(uid) {
  if (!three) return;
  const mesh = three.meshByUid.get(uid);
  if (!mesh) return;
  const origColor = mesh.material.color.clone();
  mesh.material.color.set("#c0392b");
  setTimeout(() => mesh.material.color.copy(origColor), 300);
}

function initThreeDrag() {
  const canvas = three.renderer.domElement;
  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let draggingUid = null;

  function setNdc(e) {
    const rect = canvas.getBoundingClientRect();
    ndc.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    ndc.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
  }

  canvas.addEventListener("pointerdown", (e) => {
    setNdc(e);
    raycaster.setFromCamera(ndc, three.camera);
    const meshes = Array.from(three.meshByUid.values());
    const hits = raycaster.intersectObjects(meshes, false);
    if (hits.length === 0) return;
    draggingUid = hits[0].object.userData.uid;
    three.controls.enabled = false;
  });

  canvas.addEventListener("pointermove", (e) => {
    if (draggingUid === null) return;
    setNdc(e);
    raycaster.setFromCamera(ndc, three.camera);
    const hit = raycaster.intersectObject(three.groundPlane, false)[0];
    if (!hit) return;
    const mesh = three.meshByUid.get(draggingUid);
    if (!mesh) return;
    mesh.position.x = hit.point.x;
    mesh.position.z = hit.point.z;
    const tok = ctx().bench.find((t) => t.uid === draggingUid);
    if (tok) { tok.x3 = hit.point.x; tok.z3 = hit.point.z; }
  });

  window.addEventListener("pointerup", () => {
    if (draggingUid === null) return;
    three.controls.enabled = true;
    const uid = draggingUid;
    draggingUid = null;
    persistBench();
    tryMergeAt3D(uid);
  });
}

function tryMergeAt3D(uid) {
  const tokens = ctx().bench;
  const movedTok = tokens.find((t) => t.uid === uid);
  if (!movedTok) return;
  const partner = tokens.find((t) => {
    if (t.uid === uid) return false;
    const dx = (t.x3 || 0) - (movedTok.x3 || 0);
    const dz = (t.z3 || 0) - (movedTok.z3 || 0);
    return Math.sqrt(dx * dx + dz * dz) < 1.1;
  });
  if (!partner) return;

  const recipe = findRecipe(movedTok.itemId, partner.itemId);
  if (!recipe) {
    shake3DMesh(uid);
    return;
  }

  const c = ctx();
  c.bench = c.bench.filter((t) => t.uid !== movedTok.uid && t.uid !== partner.uid);
  addQty(recipe.result, 1);
  const firstTime = !c.discovered.includes(recipe.result);
  if (firstTime) c.discovered.push(recipe.result);
  saveState();
  toast((firstTime ? "✨ Discovered: " : "Crafted another: ") + state.items[recipe.result].name);

  renderBench();
  renderPalette();
  renderRequirements();
  renderBuildableNow();
  renderCatalog();
}

/* ================= ASSEMBLY MODAL (steps generated on demand) ================= */
let stepsDone = new Set();
let assemblyIdea = null;

async function openAssemblyModal(idea) {
  assemblyIdea = idea;
  stepsDone = new Set();
  document.getElementById("assemblyModal").classList.add("visible");
  document.getElementById("photoPreview").hidden = true;
  document.getElementById("photoInput").value = "";
  document.getElementById("completeBtn").disabled = true;
  document.getElementById("stepsList").innerHTML = "";

  let steps = idea.offline ? idea.assembly_steps : state.assemblySteps[idea.id];
  if (!steps) {
    document.getElementById("stepsLoading").hidden = false;
    document.getElementById("assemblyStatus").textContent = "Asking the AI for assembly steps for " + idea.title + "...";
    try {
      const resolved = resolveIdea(idea);
      const brief = {
        title: idea.title,
        pitch: idea.pitch,
        sub_assemblies: Object.values(resolved.recipes.reduce((acc, r) => {
          acc[r.result] = state.items[r.result].name;
          return acc;
        }, {})),
        final_parts: Object.entries(resolved.finalRequires).map(([id, q]) => `${state.items[id].name} x${q}`),
      };
      const res = await fetch("/api/generate-steps", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idea: brief }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || "Couldn't generate steps");
      steps = data.assembly_steps;
      state.assemblySteps[idea.id] = steps;
      saveState();
    } catch (e) {
      steps = ["Couldn't generate assembly steps automatically — improvise from the parts you've built, or close this and try Build again."];
    }
    document.getElementById("stepsLoading").hidden = true;
  }
  document.getElementById("assemblyStatus").textContent = "Follow the steps in order. Check each one off.";

  const list = document.getElementById("stepsList");
  list.innerHTML = "";
  steps.forEach((text, i) => {
    const li = document.createElement("li");
    li.className = "step-item";
    li.innerHTML = `<input type="checkbox" data-idx="${i}"><span>${text}</span>`;
    list.appendChild(li);
  });
  list.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
    cb.addEventListener("change", () => {
      const idx = cb.dataset.idx;
      const li = cb.closest(".step-item");
      if (cb.checked) { stepsDone.add(idx); li.classList.add("done"); }
      else { stepsDone.delete(idx); li.classList.remove("done"); }
      updateCompleteButton(steps.length);
    });
  });
  window._cubeCurrentSteps = steps;
}

function updateCompleteButton(totalSteps) {
  const allSteps = stepsDone.size === totalSteps;
  const hasPhoto = !document.getElementById("photoPreview").hidden;
  document.getElementById("completeBtn").disabled = !(allSteps && hasPhoto);
}

function initAssemblyModal() {
  document.getElementById("photoInput").addEventListener("change", (e) => {
    const file = e.target.files[0];
    const preview = document.getElementById("photoPreview");
    if (!file) { preview.hidden = true; updateCompleteButton((window._cubeCurrentSteps || []).length); return; }
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
    updateCompleteButton((window._cubeCurrentSteps || []).length);
  });

  document.getElementById("closeModalBtn").addEventListener("click", () => {
    document.getElementById("assemblyModal").classList.remove("visible");
  });

  document.getElementById("completeBtn").addEventListener("click", () => {
    document.getElementById("assemblyModal").classList.remove("visible");
    const badgeId = "built_" + assemblyIdea.id;
    if (!state.badges.some((b) => b.id === badgeId)) {
      state.badges.push({ id: badgeId, title: assemblyIdea.title });
      saveState();
      renderBadges();
    }
    document.getElementById("completeTitle").textContent = assemblyIdea.title + " Built";
    document.getElementById("completeModal").classList.add("visible");
    launchConfetti();
  });

  document.getElementById("closeCompleteBtn").addEventListener("click", () => {
    document.getElementById("completeModal").classList.remove("visible");
    stopConfetti();
  });
}

/* ================= BADGES ================= */
function renderBadges() {
  const row = document.getElementById("badgeRow");
  row.innerHTML = "";
  state.badges.forEach((b) => {
    const pill = document.createElement("span");
    pill.className = "badge-pill";
    pill.textContent = "🏆 " + b.title;
    row.appendChild(pill);
  });
}

/* ================= CONFETTI ================= */
let confettiRAF = null;
function launchConfetti() {
  const canvas = document.getElementById("confettiCanvas");
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  canvas.style.display = "block";
  const ctx2d = canvas.getContext("2d");
  const colors = PALETTE_COLORS;
  const pieces = Array.from({ length: 140 }, () => ({
    x: Math.random() * canvas.width,
    y: -20 - Math.random() * canvas.height * 0.3,
    w: 6 + Math.random() * 6,
    h: 8 + Math.random() * 8,
    vy: 2 + Math.random() * 3,
    vx: -1.5 + Math.random() * 3,
    rot: Math.random() * 360,
    vr: -6 + Math.random() * 12,
    color: colors[Math.floor(Math.random() * colors.length)],
  }));
  let frame = 0;
  function tick() {
    frame++;
    ctx2d.clearRect(0, 0, canvas.width, canvas.height);
    pieces.forEach((p) => {
      p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      ctx2d.save();
      ctx2d.translate(p.x, p.y);
      ctx2d.rotate((p.rot * Math.PI) / 180);
      ctx2d.fillStyle = p.color;
      ctx2d.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx2d.restore();
    });
    if (frame < 240) confettiRAF = requestAnimationFrame(tick);
    else stopConfetti();
  }
  tick();
}
function stopConfetti() {
  if (confettiRAF) cancelAnimationFrame(confettiRAF);
  document.getElementById("confettiCanvas").style.display = "none";
}

/* ================= CAMERA SCAN ================= */
let scanStream = null;

function initScan() {
  document.getElementById("scanBtn").addEventListener("click", openScanModal);
  document.getElementById("closeScanBtn").addEventListener("click", closeScanModal);
  document.getElementById("captureBtn").addEventListener("click", captureScan);
  document.getElementById("scanManualBtn").addEventListener("click", () => showScanStep("manual"));
  document.getElementById("manualBackBtn").addEventListener("click", () => showScanStep("camera"));
  document.getElementById("scanRetryBtn").addEventListener("click", () => showScanStep("camera"));
  document.getElementById("scanConfirmBtn").addEventListener("click", () => {
    const name = document.getElementById("scanNameInput").value.trim();
    const q = Math.max(1, parseInt(document.getElementById("scanQtyInput").value, 10) || 1);
    if (!name) return;
    addMaterial(name, q);
    toast(`📸 Added "${name}" to inventory`);
    closeScanModal();
  });
  document.getElementById("manualConfirmBtn").addEventListener("click", () => {
    const name = document.getElementById("manualNameInput").value.trim();
    const q = Math.max(1, parseInt(document.getElementById("manualQtyInput").value, 10) || 1);
    if (!name) return;
    addMaterial(name, q);
    toast(`Added "${name}" to inventory`);
    closeScanModal();
  });
}

async function openScanModal() {
  document.getElementById("scanModal").classList.add("visible");
  showScanStep("camera");
  try {
    scanStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    document.getElementById("scanVideo").srcObject = scanStream;
    document.getElementById("scanStatus").textContent = "Point your camera at the item and capture.";
  } catch (e) {
    document.getElementById("scanStatus").textContent = "Camera unavailable (" + e.message + ") — type the material in instead.";
    showScanStep("manual");
  }
}

function closeScanModal() {
  document.getElementById("scanModal").classList.remove("visible");
  if (scanStream) { scanStream.getTracks().forEach((t) => t.stop()); scanStream = null; }
}

function showScanStep(step) {
  document.getElementById("scanCameraWrap").hidden = step !== "camera";
  document.getElementById("scanActionsCapture").hidden = step !== "camera";
  document.getElementById("scanPreview").hidden = true;
  document.getElementById("scanResult").hidden = step !== "result";
  document.getElementById("manualAddPanel").hidden = step !== "manual";
  if (step === "manual") {
    document.getElementById("manualNameInput").value = "";
    document.getElementById("manualQtyInput").value = "1";
    document.getElementById("manualNameInput").focus();
  }
}

async function captureScan() {
  const video = document.getElementById("scanVideo");
  const canvas = document.getElementById("scanCanvas");
  canvas.width = video.videoWidth || 640;
  canvas.height = video.videoHeight || 480;
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL("image/jpeg", 0.85);

  const flash = document.getElementById("scanFlash");
  flash.classList.remove("flash"); void flash.offsetWidth; flash.classList.add("flash");

  const preview = document.getElementById("scanPreview");
  preview.src = dataUrl;
  preview.hidden = false;
  document.getElementById("scanCameraWrap").hidden = true;
  document.getElementById("scanActionsCapture").hidden = true;
  document.getElementById("scanStatus").textContent = "Identifying...";

  try {
    const res = await fetch("/api/identify-material", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: dataUrl }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || "Couldn't identify the material");
    document.getElementById("scanNameInput").value = data.name;
    document.getElementById("scanQtyInput").value = "1";
    document.getElementById("scanStatus").textContent = data.confidence === "low"
      ? "Not totally sure — please check this before adding."
      : "Here's what CUBE thinks this is:";
    showScanStep("result");
    preview.hidden = false;
  } catch (e) {
    document.getElementById("scanStatus").textContent = "⚠️ " + e.message + " — type it in instead.";
    showScanStep("manual");
  }
}

/* ================= RESET ================= */
function initReset() {
  const btn = document.getElementById("resetBtn");
  let armed = false;
  let armTimer = null;

  btn.addEventListener("click", () => {
    if (!armed) {
      armed = true;
      btn.textContent = "Click again to confirm";
      armTimer = setTimeout(() => { armed = false; btn.textContent = "↺ Reset Demo"; }, 4000);
      return;
    }
    clearTimeout(armTimer);
    armed = false;
    btn.textContent = "↺ Reset Demo";

    state = defaultState();
    saveState();
    if (three) {
      for (const mesh of three.meshByUid.values()) three.scene.remove(mesh);
      three.meshByUid.clear();
      three.holoGroup.clear();
    }
    renderAll();
    toast("Demo reset");
  });
}

/* ================= BOOT ================= */
function renderAll() {
  renderInventory();
  renderPalette();
  renderBench();
  renderBuildableNow();
  renderCatalog();
  renderRequirements();
  renderBadges();
  document.getElementById("activeRecipeLabel").textContent = state.activeIdeaId
    ? "Building: " + (findIdea(state.activeIdeaId) || {}).title
    : "No recipe selected — pick one from the catalog →";
}

function init() {
  // make sure the offline idea's own metadata is registered (but not its
  // quantities, which stay isolated in state.offline)
  resolveIdea(OFFLINE_IDEA);

  initMaterialsForm();
  initGenerateButtons();
  initViewToggle();
  initBench();
  initBuildButton();
  initAssemblyModal();
  initScan();
  initReset();
  renderAll();
}

document.addEventListener("DOMContentLoaded", init);
