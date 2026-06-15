/** Archive Detective — Evidence Cabinet board (gradio.Server + @gradio/client) */
import { callApi, callApiQueued, onQueueStatus } from "./api.js";
import {
  renderBeatCase,
  renderEvidenceCabinet,
  updateGenerationBadge,
} from "./render.js";
import * as state from "./state.js";
import { $, DEBUG, escapeHtml } from "./util.js";

const ARCHIVIST_LINES = {
  case: [
    "Pulling case file from the stacks…",
    "Cross-referencing newspaper indices…",
    "Stamping the dossier tab…",
    "Laying artifacts on the tray…",
  ],
  generate: [
    "Reading the clipping under lamp light…",
    "MiniCPM-V transcribing the scan…",
    "MiniCPM building the Evidence Cabinet…",
    "Sorting leads by suspicion…",
    "Wax-sealing locked artifacts…",
    "Pinning evidence cards to cork…",
  ],
  generate_cached: [
    "Pulling pre-built cabinet from the stacks…",
    "Cross-checking dossier against the clipping…",
    "Laying artifacts on the tray…",
    "Stamping leads by suspicion…",
  ],
  generate_modal: [
    "Waking the Modal GPU (cold start can take several minutes)…",
    "MiniCPM-V reading the clipping on A10G…",
    "Unloading vision weights…",
    "MiniCPM5 drafting cabinet JSON…",
    "Validating artifacts and leads…",
    "Almost there — sealing the dossier…",
  ],
  generate_upload: [
    "Waking the Modal GPU (cold start can take several minutes)…",
    "MiniCPM5 drafting cabinet JSON from your OCR…",
    "Validating artifacts and leads…",
    "Sorting leads by suspicion…",
    "Wax-sealing locked artifacts…",
    "Almost there — sealing the dossier…",
  ],
  lead: ["Following the thread…", "Unlocking linked artifacts…"],
  search: ["Scanning unlocked text layers…"],
  deduction: ["Checking your conclusion against the record…"],
  reveal: ["Cross-checking Library of Congress holdings…"],
};

function showError(msg) {
  const el = $("error");
  el.hidden = false;
  el.textContent = msg;
}

function clearError() {
  $("error").hidden = true;
}

function stopElapsedClock() {
  if (state.elapsedTimer) {
    clearInterval(state.elapsedTimer);
    state.setElapsedTimer(null);
  }
  const elapsedEl = $("archivist-elapsed");
  if (elapsedEl) {
    elapsedEl.hidden = true;
    elapsedEl.textContent = "";
  }
}

function startElapsedClock(cached = false, customHint = null) {
  stopElapsedClock();
  const elapsedEl = $("archivist-elapsed");
  if (!elapsedEl) return;
  const started = Date.now();
  const hint =
    customHint ??
    (cached
      ? "pre-built cabinet — usually under a few seconds"
      : "cold starts can take several minutes");
  elapsedEl.hidden = false;
  elapsedEl.textContent = `Elapsed 0:00 · ${hint}`;
  state.setElapsedTimer(
    setInterval(() => {
      const sec = Math.floor((Date.now() - started) / 1000);
      const mm = Math.floor(sec / 60);
      const ss = String(sec % 60).padStart(2, "0");
      elapsedEl.textContent = `Elapsed ${mm}:${ss} · ${hint}`;
    }, 1000),
  );
}

function stopArchivistLines() {
  if (state.archivistTimer) {
    clearInterval(state.archivistTimer);
    state.setArchivistTimer(null);
  }
}

function startArchivistLines(mode, firstLine) {
  stopArchivistLines();
  const lines = ARCHIVIST_LINES[mode] || ARCHIVIST_LINES.case;
  state.setArchivistLineIdx(0);
  const lineEl = $("archivist-line");
  const bar = $("archivist-bar-fill");
  if (lineEl) lineEl.textContent = firstLine || lines[0];
  if (bar) bar.style.width = "12%";
  const intervalMs =
    mode === "generate_modal" || mode === "generate_upload" ? 4500 : 1400;
  state.setArchivistTimer(
    setInterval(() => {
      const idx = state.bumpArchivistLineIdx(lines.length);
      if (lineEl) lineEl.textContent = lines[idx];
      if (bar) {
        const pct = 12 + ((idx + 1) / lines.length) * 72;
        bar.style.width = `${Math.min(pct, 88)}%`;
      }
    }, intervalMs),
  );
}

function setBusy(on, label = "Working…", mode = "case", elapsedHint = null) {
  state.setBusyState(on);
  const overlay = $("archivist-overlay");
  if (on) {
    overlay.hidden = false;
    overlay.setAttribute("aria-busy", "true");
    startArchivistLines(mode, label);
    if (mode === "generate_modal" || mode === "generate_upload") {
      startElapsedClock(false, elapsedHint);
    } else if (mode === "generate" || mode === "generate_cached") {
      startElapsedClock(mode === "generate_cached", elapsedHint);
    } else {
      stopElapsedClock();
    }
  } else {
    overlay.hidden = true;
    overlay.setAttribute("aria-busy", "false");
    stopArchivistLines();
    stopElapsedClock();
    const bar = $("archivist-bar-fill");
    if (bar) bar.style.width = "0%";
  }
}

function prepareGeneratingUI(title, detail, { cached = false, modal = false, hasOcr = false } = {}) {
  clearError();
  showBoard();
  $("case-title").textContent = title;
  $("case-tagline").textContent = detail;
  if (cached) {
    $("case-intro").textContent =
      "Opening a pre-built Evidence Cabinet from the archive stacks. Use Regenerate for a fresh Modal GPU run.";
  } else if (modal && hasOcr) {
    $("case-intro").textContent =
      "Pasted OCR skips the GPU vision read — MiniCPM5 is drafting cabinet JSON on Modal GPU (usually 1–3 minutes on Space).";
  } else if (modal) {
    $("case-intro").textContent =
      "Live OpenBMB models are reading the clipping image and drafting cabinet JSON on Modal GPU (often 3–5 minutes; keep this tab open).";
  } else {
    $("case-intro").textContent =
      "Live models are reading the clipping and drafting cabinet JSON…";
  }
  $("status-badge").textContent = cached ? "FROM STACKS" : "GENERATING";
  $("status-badge").className = "status-stamp warm";
  $("cabinet-layout").hidden = true;
  $("beat-layout").hidden = true;
  $("btn-regenerate").hidden = true;
  const boardBadge = $("board-generation-badge");
  if (boardBadge) boardBadge.hidden = true;
}

function showLanding() {
  document.body.classList.add("mode-landing");
  document.body.classList.remove("mode-investigation");
  $("landing-hub").hidden = false;
  $("landing-hero")?.removeAttribute("hidden");
  $("board").hidden = true;
  $("btn-back-desk").hidden = true;
  $("case-picker-bar").hidden = true;
  updateGenerationBadge(state.currentState?.generation || null);
}

function showBoard() {
  document.body.classList.remove("mode-landing");
  document.body.classList.add("mode-investigation");
  $("landing-hub").hidden = true;
  $("landing-hero")?.setAttribute("hidden", "");
  $("board").hidden = false;
  $("btn-back-desk").hidden = false;
  $("case-picker-bar").hidden = true;
}

function mysteryTier(score) {
  if (score >= 0.65) return "hot";
  if (score >= 0.45) return "warm";
  return "cold";
}

function pulseCaseOpen() {
  const sheet = $("dossier-sheet");
  const stamp = $("case-open-stamp");
  if (!sheet) return;
  sheet.classList.remove("case-opening");
  void sheet.offsetWidth;
  sheet.classList.add("case-opening");
  if (stamp) {
    stamp.classList.remove("stamp-slam");
    void stamp.offsetWidth;
    stamp.classList.add("stamp-slam");
  }
}

function flashTrayUnlock() {
  const tray = $("artifact-tray");
  if (!tray) return;
  tray.classList.remove("unlock-burst");
  void tray.offsetWidth;
  tray.classList.add("unlock-burst");
}

function wireSpotlight() {
  const spot = $("desk-spotlight");
  if (!spot) return;
  spot.style.opacity = "1";
  document.addEventListener(
    "pointermove",
    (e) => {
      spot.style.setProperty("--sx", `${e.clientX}px`);
      spot.style.setProperty("--sy", `${e.clientY}px`);
    },
    { passive: true },
  );
}

function setLandingTab(tab) {
  const isGallery = tab === "gallery";
  $("tab-gallery").classList.toggle("is-active", isGallery);
  $("tab-gallery").setAttribute("aria-selected", String(isGallery));
  $("tab-featured").classList.toggle("is-active", !isGallery);
  $("tab-featured").setAttribute("aria-selected", String(!isGallery));
  $("panel-gallery").classList.toggle("is-active", isGallery);
  $("panel-gallery").hidden = !isGallery;
  $("panel-gallery").setAttribute("aria-hidden", String(!isGallery));
  if ("inert" in $("panel-gallery")) {
    $("panel-gallery").inert = !isGallery;
  }
  $("panel-featured").classList.toggle("is-active", !isGallery);
  $("panel-featured").hidden = isGallery;
  $("panel-featured").setAttribute("aria-hidden", String(isGallery));
  if ("inert" in $("panel-featured")) {
    $("panel-featured").inert = isGallery;
  }
  $("case-picker-bar").hidden = true;
}

function startTicker(items) {
  const track = $("ticker-track");
  if (!track || !items.length) return;
  const bits = items.map((item) => {
    const date = item.date || "undated";
    const head = (item.headline || "mystery clipping").slice(0, 72);
    return `${date} · ${head}`;
  });
  const loop = [...bits, ...bits];
  track.innerHTML = loop.map((line) => `<span class="wire-item">${escapeHtml(line)}</span>`).join("");
}

function updateDeskStats() {
  const clipEl = $("stat-clips");
  const caseEl = $("stat-cases");
  if (clipEl) clipEl.textContent = String(state.galleryItems.length || 10);
  if (caseEl) caseEl.textContent = String(state.catalog.length || 6);
  if (state.galleryItems.length) {
    const years = state.galleryItems
      .map((i) => (i.date || "").slice(0, 4))
      .filter((y) => /^\d{4}$/.test(y))
      .sort();
    const yearEl = $("stat-years");
    if (yearEl && years.length) {
      yearEl.textContent =
        years[0] === years[years.length - 1] ? years[0] : `${years[0]}–${years[years.length - 1]}`;
    }
  }
}

function renderState(sess, { animate = true } = {}) {
  clearError();
  state.setCurrentState(sess);
  showBoard();
  setBusy(false);

  $("case-title").textContent = sess.title;
  $("case-tagline").textContent = sess.tagline;

  const handlers = { onLead, onSelectArtifact };
  if (sess.mode === "evidence_cabinet") {
    renderEvidenceCabinet(sess, { animate, ...handlers });
  } else {
    renderBeatCase(sess, { animate, onLead });
  }

  const debugPanel = $("model-reading");
  if (debugPanel) {
    if (DEBUG) {
      debugPanel.hidden = false;
      debugPanel.textContent = JSON.stringify(sess, null, 2);
    } else {
      debugPanel.hidden = true;
      debugPanel.textContent = "";
    }
  }

  if (animate) {
    $("board").classList.remove("enter");
    void $("board").offsetWidth;
    $("board").classList.add("enter");
    pulseCaseOpen();
  }
}

async function loadModelInfo() {
  try {
    const info = await callApi("model_info");
    state.setModelInfo(info);
    const banner = $("model-banner");
    if (!banner) return;
    if (info.modal_enabled || info.hf_enabled) {
      banner.hidden = false;
      banner.classList.remove("model-missing");
      if (info.stack === "openbmb") {
        banner.textContent = `OpenBMB · one Modal GPU: ${info.ocr_model} reads → ${info.cabinet_model} builds the cabinet`;
        const uploadFold = document.querySelector(".upload-fold");
        if (uploadFold) uploadFold.open = true;
        const uploadWarn = $("upload-space-hint");
        if (uploadWarn && info.upload_requires_ocr) {
          uploadWarn.hidden = false;
          uploadWarn.textContent =
            info.upload_hint ||
            "On this Space, paste OCR text — image-only uploads time out before GPU vision finishes.";
        }
      } else {
        const ocrLine =
          info.ocr_mode === "modal"
            ? `${info.ocr_model} on Modal GPU reads the clipping, then`
            : info.ocr_mode === "vision"
              ? `${info.ocr_model} reads the clipping image, then`
              : `${info.ocr_model} refines archive OCR, then`;
        banner.textContent = `Every gallery pick: ${ocrLine} ${info.cabinet_model || info.text_model} builds the Evidence Cabinet`;
      }
    } else {
      banner.hidden = false;
      banner.classList.add("model-missing");
      banner.textContent =
        "Modal or HF_TOKEN missing — set MODAL_TOKEN_ID/SECRET (OpenBMB) or HF_TOKEN for gallery generation.";
    }
  } catch {
    /* non-fatal */
  }
}

async function loadCatalog() {
  state.setCatalog(await callApi("catalog"));
  const sel = $("case-select");
  sel.innerHTML = "";
  for (const c of state.catalog) {
    const opt = document.createElement("option");
    opt.value = c.id;
    const modeTag = c.mode === "evidence_cabinet" ? " · cabinet" : "";
    opt.textContent = c.hero ? `★ ${c.title}${modeTag}` : `${c.title}${modeTag}`;
    opt.title = c.tagline || c.title;
    sel.appendChild(opt);
  }
  renderHeroCases();
}

function renderHeroCases() {
  const grid = $("hero-case-grid");
  if (!grid) return;
  grid.innerHTML = "";
  const heroes = state.catalog.filter((c) => c.hero);
  const items = heroes.length ? heroes : state.catalog.slice(0, 4);
  if (!items.length) {
    grid.innerHTML = '<p class="empty-state">No featured cases in data/cases/</p>';
    return;
  }
  for (const c of items) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "hero-case-card";
    btn.setAttribute("role", "listitem");
    const mode = c.mode === "evidence_cabinet" ? "Evidence Cabinet" : "Beat case";
    btn.setAttribute("aria-label", `Open ${c.title} — ${mode}`);
    btn.innerHTML = `
      <span class="hero-case-mode">${escapeHtml(mode)}</span>
      <span class="hero-case-title">${escapeHtml(c.title)}</span>
      <span class="hero-case-tag">${escapeHtml(c.tagline || "Open the file")}</span>
      <span class="hero-case-cta">Open file →</span>
    `;
    btn.addEventListener("click", () => startCase(c.id));
    grid.appendChild(btn);
  }
}

async function loadGallery() {
  const items = await callApi("gallery_catalog");
  state.setGalleryItems(items);
  startTicker(items);
  updateDeskStats();
  const grid = $("gallery-grid");
  grid.innerHTML = "";
  if (!items.length) {
    grid.innerHTML = '<p class="empty-state">No gallery clippings bundled.</p>';
    return;
  }
  items.forEach((item, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    const tier = mysteryTier(item.mystery_score || 0);
    btn.className = `gallery-card polaroid tier-${tier}`;
    btn.style.setProperty("--tilt", `${((i % 7) - 3) * 1.1}deg`);
    btn.style.setProperty("--i", String(i));
    btn.setAttribute("role", "listitem");
    btn.setAttribute("aria-label", item.headline);
    btn.title = item.headline;
    const thumb = item.thumb_url
      ? `<img src="${escapeHtml(item.thumb_url)}" alt="" class="gallery-thumb" loading="lazy" />`
      : '<span class="gallery-thumb placeholder">?</span>';
    btn.innerHTML = `
      <span class="polaroid-pin" aria-hidden="true"></span>
      ${thumb}
      <span class="gallery-meta">${escapeHtml(item.date || "")}</span>
      <span class="gallery-headline">${escapeHtml(item.headline)}</span>
      <span class="gallery-score tier-badge">${tier} · ${Math.round((item.mystery_score || 0) * 100)}%</span>
      <span class="gallery-cta">Investigate →</span>
    `;
    btn.addEventListener("click", () => {
      btn.classList.add("polaroid-lift");
      onGenerateGallery(item.id, false);
    });
    grid.appendChild(btn);
  });
}

function onRandomClip() {
  if (!state.galleryItems.length || state.busy) return;
  const pick = state.galleryItems[Math.floor(Math.random() * state.galleryItems.length)];
  const cards = document.querySelectorAll(".gallery-card");
  cards.forEach((c) => c.classList.remove("shuffle-pick"));
  const idx = state.galleryItems.indexOf(pick);
  const card = cards[idx];
  if (card) {
    card.classList.add("shuffle-pick");
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  window.setTimeout(() => onGenerateGallery(pick.id, false), 420);
}

async function onGenerateGallery(clippingId, regenerate) {
  if (state.busy) return;
  state.setActiveClippingId(clippingId);
  const clip = state.galleryItems.find((g) => g.id === clippingId);
  const hasCache = Boolean(clip?.has_cache) && !regenerate;
  const modal = state.modelInfo?.stack === "openbmb" && !hasCache;
  const mode = hasCache ? "generate_cached" : modal ? "generate_modal" : "generate";
  const label = hasCache
    ? "Opening pre-built cabinet from the stacks…"
    : modal
      ? regenerate
        ? "Regenerating on Modal GPU (OpenBMB)…"
        : "OpenBMB on Modal GPU — first run may take several minutes…"
      : regenerate
        ? "Regenerating via hosted model…"
        : "Building Evidence Cabinet…";
  prepareGeneratingUI(
    regenerate ? "Regenerating Evidence Cabinet…" : "Generating Evidence Cabinet…",
    clip?.headline || "Reading clipping from the murder board…",
    { cached: hasCache },
  );
  setBusy(true, label, mode);
  try {
    const sess = await callApiQueued("generate_from_gallery", [clippingId, regenerate], onQueueStatus);
    state.setSessionId(sess.session_id);
    renderState(sess);
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function onRegenerateCabinet() {
  const clippingId = state.currentState?.generation?.clipping_id || state.activeClippingId;
  if (!clippingId || state.busy) return;
  await onGenerateGallery(clippingId, true);
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function onUploadGenerate(event) {
  event.preventDefault();
  if (state.busy) return;
  const fileInput = $("upload-image");
  const file = fileInput.files?.[0];
  if (!file) return;
  const rawOcr = $("upload-ocr").value.trim();
  const info = state.modelInfo;
  const modal = info?.stack === "openbmb";
  if (info?.upload_requires_ocr && !rawOcr) {
    const uploadFold = document.querySelector(".upload-fold");
    if (uploadFold) uploadFold.open = true;
    const ocrField = $("upload-ocr");
    ocrField?.focus();
    showError(
      info.upload_hint ||
        "Paste OCR text from Chronicling America before building — image-only uploads time out on this Space.",
    );
    return;
  }
  state.setActiveClippingId(null);
  const title = $("upload-title").value.trim() || "Uploaded clipping";
  const hasOcr = rawOcr.length >= 20;
  const elapsedHint = modal
    ? hasOcr
      ? "pasted OCR skips GPU read — usually 1–3 min on Space"
      : "GPU cold start + vision read — often 3–5 min"
    : hasOcr
      ? "refining pasted OCR, then building cabinet"
      : "reading image, then building cabinet";
  prepareGeneratingUI(
    "Generating from upload…",
    title,
    { modal, hasOcr },
  );
  setBusy(
    true,
    modal
      ? hasOcr
        ? "OpenBMB on Modal GPU — building cabinet from pasted OCR…"
        : "OpenBMB on Modal GPU — reading upload & building cabinet…"
      : "Reading upload & generating cabinet…",
    modal ? (hasOcr ? "generate_upload" : "generate_modal") : "generate",
    elapsedHint,
  );
  try {
    const b64 = await fileToBase64(file);
    const sess = await callApiQueued(
      "generate_from_upload",
      [b64, title, rawOcr, true],
      onQueueStatus,
    );
    state.setSessionId(sess.session_id);
    renderState(sess);
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function startCase(caseId) {
  if (state.busy) return;
  setBusy(true, "Opening case file…", "case");
  for (const id of ["reveal-panel", "beat-reveal-panel"]) {
    const revealPanel = $(id);
    if (revealPanel) {
      revealPanel.hidden = true;
      revealPanel.classList.remove("visible");
      revealPanel.innerHTML = "";
    }
  }
  try {
    const sess = await callApi("start_case", caseId);
    state.setSessionId(sess.session_id);
    state.setActiveClippingId(null);
    renderState(sess);
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function onLead(leadId) {
  if (!state.sessionId || state.busy) return;
  const prevUnlocked = state.currentState?.unlocked_artifacts?.length || 0;
  setBusy(true, "Following the thread…", "lead");
  try {
    const sess = await callApi("choose_lead", state.sessionId, leadId);
    const nextUnlocked = sess.unlocked_artifacts?.length || 0;
    renderState(sess);
    if (nextUnlocked > prevUnlocked) flashTrayUnlock();
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function onSelectArtifact(artifactId) {
  if (!state.sessionId || state.busy) return;
  setBusy(true, "Opening artifact…", "case");
  try {
    const sess = await callApi("select_artifact", state.sessionId, artifactId);
    renderState(sess, { animate: false });
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function onSearch(event) {
  event.preventDefault();
  if (!state.sessionId || state.busy) return;
  const query = $("search-input").value;
  setBusy(true, "Searching evidence…", "search");
  try {
    const sess = await callApi("search_case", state.sessionId, query);
    renderState(sess, { animate: false });
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function onDeduction(event) {
  event.preventDefault();
  if (!state.sessionId || state.busy) return;
  const form = event.target;
  const answers = {};
  for (const field of form.elements) {
    if (field.name) answers[field.name] = field.value;
  }
  setBusy(true, "Checking deduction…", "deduction");
  try {
    const sess = await callApi("submit_deduction", state.sessionId, answers);
    renderState(sess, { animate: false });
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function onReveal() {
  if (!state.sessionId || state.busy) return;
  setBusy(true, "Cross-checking archive…", "reveal");
  try {
    const sess = await callApi("reveal", state.sessionId);
    renderState(sess, { animate: false });
    const panel = $("reveal-panel") || $("beat-reveal-panel");
    if (panel && !panel.hidden) {
      panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

function wireDropZone() {
  const zone = $("drop-zone");
  const input = $("upload-image");
  const nameEl = $("drop-filename");
  if (!zone || !input) return;

  const showFile = (file) => {
    if (!file) return;
    nameEl.hidden = false;
    nameEl.textContent = file.name;
    zone.classList.add("has-file");
  };

  $("btn-browse")?.addEventListener("click", () => input.click());
  zone.addEventListener("click", (e) => {
    if (e.target.id === "btn-browse") return;
    input.click();
  });
  zone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      input.click();
    }
  });
  input.addEventListener("change", () => showFile(input.files?.[0]));
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("drag-over");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    showFile(file);
  });
}

async function init() {
  try {
    await loadModelInfo();
    await loadCatalog();
    await loadGallery();
    updateDeskStats();
    const sel = $("case-select");
    $("btn-open-case")?.addEventListener("click", () => startCase(sel.value));
    $("btn-back-desk")?.addEventListener("click", () => {
      state.setSessionId(null);
      state.setCurrentState(null);
      updateGenerationBadge(null);
      setBusy(false);
      showLanding();
      for (const id of ["reveal-panel", "beat-reveal-panel"]) {
        const panel = $(id);
        if (panel) {
          panel.hidden = true;
          panel.classList.remove("visible");
          panel.innerHTML = "";
        }
      }
    });
    $("tab-gallery")?.addEventListener("click", () => setLandingTab("gallery"));
    $("tab-featured")?.addEventListener("click", () => setLandingTab("featured"));
    $("btn-random-clip")?.addEventListener("click", onRandomClip);
    $("btn-reveal").addEventListener("click", onReveal);
    $("btn-beat-reveal").addEventListener("click", onReveal);
    $("btn-regenerate")?.addEventListener("click", onRegenerateCabinet);
    $("search-form").addEventListener("submit", onSearch);
    $("deduction-form").addEventListener("submit", onDeduction);
    $("upload-form").addEventListener("submit", onUploadGenerate);
    wireDropZone();
    wireSpotlight();
    setBusy(false);
    if (!state.catalog.length) {
      showError("No case files found in data/cases/");
    }
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

init();
